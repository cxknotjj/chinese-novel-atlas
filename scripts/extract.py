#!/usr/bin/env python3
"""extract.py — 按批调用模型，把章节抽成 out/batch-XX.json。

设计原则：

1. **可断点续跑**：每批一个文件，已存在且章节号对得上就跳过
2. **可预算熔断**：累计花费达到 --max-cost 就不再提交新批次
3. **上下文一致**：每批都带上"已登场实体目录 + 已确认境界体系 + 未回收伏笔"，
   避免同一个人在不同批次被起成不同 id、境界被各自编号、回收的坑没人认领
4. **每批自检**：JSON 结构 / 枚举 / 引用 / 长度不合法就重试，仍失败写 .failed.json 留证

支持任何 OpenAI 兼容接口（DeepSeek / 通义 / OpenAI / 自建）。

用法：
    python scripts/extract.py --dir output/凡人修仙传/ --dry-run
    python scripts/extract.py --dir output/凡人修仙传/ --concurrency 4 --max-cost 2
    python scripts/extract.py --dir output/凡人修仙传/ --provider deepseek --batch-size 10

环境变量：DEEPSEEK_API_KEY / QWEN_API_KEY / OPENAI_API_KEY
或 data/config.json：{"api_key":"…","base_url":"…","model":"…","price_in":1,"price_out":2}
"""

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "scripts" / "prompts" / "extract_batch.md"

PROVIDERS = {
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                 "env": "DEEPSEEK_API_KEY", "json_mode": True,
                 "price_in": 1.0, "price_out": 2.0},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "model": "qwen-plus", "env": "QWEN_API_KEY", "json_mode": False,
             "price_in": 2.0, "price_out": 6.0},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "env": "OPENAI_API_KEY", "json_mode": True,
               "price_in": 1.0, "price_out": 3.0},
}

RELATION_TYPES = {"kinship", "marriage", "romance", "service",
                  "mentorship", "alliance", "conflict", "social"}
ENTITY_TYPES = {"character", "org", "item", "creature"}
HOOK_TYPES = {"悬念", "反转", "冲突", "危机", "爽点", "无"}
EMOTIONS = {"爽", "压抑", "紧张", "温情", "悲", "平"}
CONCEPT_KINDS = {"worldview", "golden_finger", "technique",
                 "item_grade", "organization_rule", "prophecy"}


# ---------------------------------------------------------------- config

def load_config(args):
    cfg = {}
    cfg_path = ROOT / "data" / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{cfg_path} 不是合法 JSON：{e}")

    provider = args.provider
    if provider in (None, "auto"):
        if args.api_key or cfg.get("api_key"):
            provider = "custom"
        else:
            provider = next((p for p in ("deepseek", "qwen", "openai")
                             if os.environ.get(PROVIDERS[p]["env"])), None)
    if provider is None:
        provider = "deepseek"

    base = PROVIDERS.get(provider, {})
    out = {
        "provider": provider,
        "api_key": (args.api_key
                    or os.environ.get(base.get("env", ""), "")
                    or cfg.get("api_key", "")),
        "base_url": args.base_url or cfg.get("base_url") or base.get("base_url", ""),
        "model": args.model or cfg.get("model") or base.get("model", ""),
        "json_mode": bool(cfg.get("json_mode", base.get("json_mode", False))),
        "price_in": args.price_in if args.price_in is not None
                    else float(cfg.get("price_in", base.get("price_in", 1.0))),
        "price_out": args.price_out if args.price_out is not None
                     else float(cfg.get("price_out", base.get("price_out", 2.0))),
        "max_tokens": int(cfg.get("max_tokens", 8192)),
        "timeout": int(cfg.get("timeout", 240)),
    }
    return out


# ---------------------------------------------------------------- data

def load_meta(root):
    p = root / "chunk-meta.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def load_chapters(root, meta, ch_range=None):
    ch_dir = root / "chapters"
    if not ch_dir.exists():
        raise SystemExit(f"找不到 {ch_dir}，请先跑 scripts/chunk.py")
    meta_ch = {r["ch"]: r for r in meta.get("chapters", [])}
    out = []
    for f in sorted(ch_dir.glob("ch-*.txt")):
        m = re.search(r"ch-(\d+)", f.name)
        if not m:
            continue
        ch = int(m.group(1))
        if ch_range and not (ch_range[0] <= ch <= ch_range[1]):
            continue
        body = f.read_text(encoding="utf-8", errors="replace").strip()
        if not body:
            continue
        r = meta_ch.get(ch, {})
        out.append({"ch": ch, "title": r.get("title") or f"第{ch}章",
                    "vol": r.get("vol"), "words": r.get("words") or len(body),
                    "body": body})
    return out


def load_realms(root):
    p = root / "realms.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return raw.get("realms", []) if isinstance(raw, dict) else raw


def split_batches(chapters, batch_size, max_chars):
    batches, cur, chars = [], [], 0
    for c in chapters:
        size = len(c["body"])
        if cur and (len(cur) >= batch_size or chars + size > max_chars):
            batches.append(cur)
            cur, chars = [], 0
        cur.append(c)
        chars += size
    if cur:
        batches.append(cur)
    return batches


def compact_catalog(catalog):
    lines = []
    for e in catalog.values():
        al = "/".join(e.get("aliases") or [])
        lines.append(f"{e['id']}｜{e['name']}｜{e.get('type','character')}"
                     + (f"｜{al}" if al else ""))
    return "\n".join(lines) if lines else "（暂无）"


def compact_realms(realms):
    if not realms:
        return "（本书尚未确认境界体系，按原文实际出现的等级词填写，realms 可为空数组）"
    rows = []
    for r in realms:
        st = "、".join(r.get("stages") or [])
        rows.append(f"{r['id']}｜{r['name']}｜order={r['order']}"
                    + (f"｜小阶段：{st}" if st else ""))
    return "\n".join(rows)


def compact_open_fores(fores):
    rows = [f"{f['id']}｜{f.get('content','')}｜埋于 ch{f.get('plant_ch')}"
            for f in fores if f.get("payoff_ch") is None and f.get("status") != "dropped"]
    return "\n".join(rows) if rows else "（暂无）"


# ---------------------------------------------------------------- client

class Client:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = cfg["base_url"].rstrip("/")
        if not self.base.endswith("/v1") and "/v1" not in self.base:
            self.base += "/v1"
        self.url = self.base + "/chat/completions"

    def call(self, prompt):
        body = {
            "model": self.cfg["model"],
            "messages": [
                {"role": "system", "content": "你是严谨的中文网文结构化抽取器，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": self.cfg["max_tokens"],
            "stream": False,
        }
        if self.cfg.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.cfg['api_key']}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.cfg["timeout"]) as r:
            payload = json.loads(r.read().decode("utf-8"))
        usage = payload.get("usage") or {}
        content = payload["choices"][0]["message"]["content"]
        return content, usage


def parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("返回值里找不到 JSON 对象")
    return json.loads(text[start:end + 1])


# ---------------------------------------------------------------- checks

def check_batch(data, expected_chs, known_ids, realm_ids, known_fs_ids):
    errs, warns = [], []

    if not isinstance(data, dict):
        return ["顶层不是 JSON 对象"], []
    for k in ("entities", "relations", "chapters", "foreshadows"):
        if not isinstance(data.get(k), list):
            errs.append(f"缺少数组字段 {k}")

    ents = data.get("entities") or []
    ids = set()
    for e in ents:
        i = e.get("id")
        if not i or not str(i).startswith("e_"):
            errs.append(f"实体 id 不合法：{i}")
            continue
        if i in ids:
            errs.append(f"批内实体 id 重复：{i}")
        ids.add(i)
        if e.get("type") not in ENTITY_TYPES:
            errs.append(f"{i} 的 type 越界：{e.get('type')}")
        if not e.get("name"):
            errs.append(f"{i} 缺 name")
        if not e.get("group"):
            warns.append(f"{i} 缺 group")
        if not isinstance(e.get("first_ch"), int):
            errs.append(f"{i} 缺 first_ch")
        elif e["first_ch"] not in expected_chs and e["first_ch"] > max(expected_chs):
            warns.append(f"{i} first_ch={e['first_ch']} 不在本批范围")
        if len(e.get("desc") or "") > 100:
            warns.append(f"{e.get('name')} 简介超过 100 字")
        ph = e.get("power_history") or []
        for j, p in enumerate(ph):
            if realm_ids and p.get("realm") not in realm_ids:
                errs.append(f"{e.get('name')} 的境界 {p.get('realm')} 不在权威体系")
            if j and not isinstance(p.get("ch"), int):
                errs.append(f"{e.get('name')} power_history 缺 ch")
            if j and isinstance(p.get("ch"), int) and isinstance(ph[j - 1].get("ch"), int):
                if p["ch"] <= ph[j - 1]["ch"]:
                    errs.append(f"{e.get('name')} power_history 章号未递增")

    rels = data.get("relations") or []
    for r in rels:
        if r.get("type") not in RELATION_TYPES:
            errs.append(f"关系类型越界：{r.get('type')}")
        for k in ("s", "t"):
            if r.get(k) not in ids and r.get(k) not in known_ids:
                errs.append(f"关系 {k}={r.get(k)} 不在本批实体/目录里")
        if r.get("s") == r.get("t"):
            errs.append(f"自环关系：{r.get('s')}")
        w = r.get("weight")
        if not isinstance(w, (int, float)) or not 0 <= w <= 1:
            errs.append(f"weight 应在 0-1：{w}")

    chs = [c.get("ch") for c in data.get("chapters") or []]
    if len(set(chs)) != len(chs):
        errs.append(f"章节号重复：{chs}")
    if sorted(set(chs)) != sorted(expected_chs):
        errs.append(f"章节号不匹配：应 {expected_chs}，实际 {chs}")
    for c in data.get("chapters") or []:
        if len(c.get("summary") or "") > 80:
            errs.append(f"ch{c.get('ch')} 摘要超过 80 字")
        if len(c.get("hook") or "") > 30:
            errs.append(f"ch{c.get('ch')} 钩子超过 30 字")
        if not isinstance(c.get("tension"), (int, float)) or not 0 <= c["tension"] <= 1:
            errs.append(f"ch{c.get('ch')} tension 应在 0-1")
        if c.get("hook_type") not in HOOK_TYPES:
            errs.append(f"ch{c.get('ch')} hook_type 越界：{c.get('hook_type')}")
        if c.get("emotion") not in EMOTIONS:
            errs.append(f"ch{c.get('ch')} emotion 越界：{c.get('emotion')}")
        for eid in c.get("new_entities") or []:
            if eid not in ids and eid not in known_ids:
                errs.append(f"ch{c.get('ch')} new_entities 引用不存在：{eid}")
        for fid in c.get("new_foreshadows") or []:
            if fid not in {f.get("id") for f in data.get("foreshadows") or []} \
                    and fid not in known_fs_ids:
                warns.append(f"ch{c.get('ch')} new_foreshadows 引用未知：{fid}")

    for f in data.get("foreshadows") or []:
        if not str(f.get("id") or "").startswith("f_"):
            errs.append(f"伏笔 id 不合法：{f.get('id')}")
        if not isinstance(f.get("plant_ch"), int):
            errs.append(f"伏笔 {f.get('id')} 缺 plant_ch")
        if len(f.get("content") or "") > 50:
            errs.append(f"伏笔 {f.get('id')} content 超过 50 字")
        w = f.get("importance")
        if not isinstance(w, (int, float)) or not 0 <= w <= 1:
            errs.append(f"伏笔 {f.get('id')} importance 应在 0-1")

    for r in data.get("realms") or []:
        if not isinstance(r.get("order"), int):
            errs.append(f"境界 {r.get('name')} 缺 order")
        if realm_ids and r.get("id") not in realm_ids:
            errs.append(f"境界 {r.get('id')} 不在权威体系，不要自建")

    for p in data.get("places") or []:
        if not str(p.get("id") or "").startswith("p_"):
            errs.append(f"地点 id 不合法：{p.get('id')}")
    for c in data.get("concepts") or []:
        if not str(c.get("id") or "").startswith("c_"):
            errs.append(f"设定 id 不合法：{c.get('id')}")
        if c.get("kind") not in CONCEPT_KINDS:
            errs.append(f"设定 {c.get('id')} kind 越界：{c.get('kind')}")

    return errs, warns


# ---------------------------------------------------------------- cost

class Cost:
    def __init__(self, cfg, max_cost):
        self.cfg = cfg
        self.max_cost = max_cost
        self.spent = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.lock = threading.Lock()

    def add(self, usage, fallback_in=0, fallback_out=0):
        pin = usage.get("prompt_tokens") or fallback_in
        pout = usage.get("completion_tokens") or fallback_out
        cost = (pin / 1e6 * self.cfg["price_in"]
                + pout / 1e6 * self.cfg["price_out"])
        with self.lock:
            self.spent += cost
            self.prompt_tokens += pin
            self.completion_tokens += pout
        return cost

    def exhausted(self):
        with self.lock:
            return self.spent >= self.max_cost


# ---------------------------------------------------------------- run

def build_prompt(tpl, batch, catalog, realms, open_fores):
    lines = []
    for c in batch:
        lines.append(f"\n### 第{c['ch']}章 {c['title']}\n{c['body']}")
    return (tpl.replace("{{REALMS}}", compact_realms(realms))
            .replace("{{CATALOG}}", compact_catalog(catalog))
            .replace("{{OPEN_FORESHADOWS}}", compact_open_fores(open_fores))
            .replace("{{CH_START}}", str(batch[0]["ch"]))
            .replace("{{CH_END}}", str(batch[-1]["ch"]))
            .replace("{{CHAPTERS}}", "\n".join(lines)))


def run_batch(bi, total, batch, args, cfg, client, cost, catalog, realms,
              open_fores, prompt_tpl, out_dir, log_lock):
    expected = [c["ch"] for c in batch]
    name = f"batch-{bi:02d}.json"
    out_path = out_dir / name
    max_ch = expected[-1]
    # 只把"本批之前已登场"的实体和"本批之前已埋"的伏笔给模型，避免剧透式污染
    cat = {k: v for k, v in catalog.items()
           if (v.get("first_ch") or 0) <= max_ch} or catalog
    of = [f for f in open_fores if (f.get("plant_ch") or 0) <= max_ch]
    known_ids = set(cat.keys())
    realm_ids = {r.get("id") for r in realms}
    known_fs = {f.get("id") for f in of}

    chars = sum(len(c["body"]) for c in batch)
    prompt = build_prompt(prompt_tpl, batch, cat, realms, of)
    t0 = time.time()
    last_errs = []
    raw = ""

    for attempt in range(1, args.retries + 2):
        if attempt > 1:
            prompt = (build_prompt(prompt_tpl, batch, cat, realms, of)
                      + "\n\n上一次输出没有通过校验，问题如下，请修正后重发**完整 JSON**：\n- "
                      + "\n- ".join(last_errs[:12]))
        try:
            raw, usage = client.call(prompt)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, KeyError) as e:
            last_errs = [f"接口调用失败：{e}"]
            if attempt <= args.retries:
                time.sleep(2 * attempt)
            continue

        cost.add(usage, fallback_in=int(len(prompt) / 1.6),
                 fallback_out=int(len(raw) / 2))
        try:
            data = parse_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            last_errs = [f"JSON 解析失败：{e}"]
            continue

        errs, warns = check_batch(data, expected, known_ids, realm_ids, known_fs)
        if not errs:
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(out_path)
            if warns:
                print(f"  ! {name} {len(warns)} 条警告（如 {warns[0]}）")
            with log_lock:
                with (out_dir / "_extract_log.jsonl").open("a", encoding="utf-8") as lf:
                    lf.write(json.dumps({
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "batch": name, "ch": [expected[0], expected[-1]],
                        "attempt": attempt, "chars": chars,
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "cost_cny": round(cost.spent, 4), "elapsed": round(time.time() - t0, 1),
                        "errors": [], "warnings": warns,
                    }, ensure_ascii=False) + "\n")
            return {"ok": True, "name": name, "ch": expected,
                    "elapsed": time.time() - t0, "attempts": attempt,
                    "entities": len(data.get("entities") or []),
                    "relations": len(data.get("relations") or []),
                    "cost": cost.spent}
        last_errs = errs

    failed = {"batch": name, "ch": expected, "errors": last_errs, "raw": raw}
    (out_dir / (name.replace(".json", ".failed.json"))).write_text(
        json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    with log_lock:
        with (out_dir / "_extract_log.jsonl").open("a", encoding="utf-8") as lf:
            lf.write(json.dumps({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "batch": name, "ch": [expected[0], expected[-1]], "status": "failed",
                "errors": last_errs[:8], "chars": chars,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
    return {"ok": False, "name": name, "ch": expected,
            "elapsed": time.time() - t0, "errors": last_errs}


def existing_ok(out_dir, batch):
    """已存在的批次文件是否**正好**覆盖本批全部章号（不多不少）。"""
    expected = {c["ch"] for c in batch}
    for f in out_dir.glob("batch-*.json"):
        if f.name.endswith(".failed.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if {c.get("ch") for c in d.get("chapters") or []} == expected:
            return f
    return None


def collect_catalog(root, out_dir, realm_ids):
    """已登场实体 + 已抽批次里的实体，用于给模型复用 id。"""
    cat = {}
    data_p = root / "data.json"
    if data_p.exists():
        try:
            d = json.loads(data_p.read_text(encoding="utf-8"))
            for e in d.get("entities") or []:
                if e.get("id"):
                    cat[e["id"]] = e
        except json.JSONDecodeError:
            pass
    for f in sorted(out_dir.glob("batch-*.json")):
        if f.name.endswith(".failed.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for e in d.get("entities") or []:
            if e.get("id"):
                cat.setdefault(e["id"], e)
    return cat


def collect_open_fores(root, out_dir):
    root_p = root / "data.json"
    fores = []
    if root_p.exists():
        try:
            fores = (json.loads(root_p.read_text(encoding="utf-8"))
                     .get("foreshadows") or [])
        except json.JSONDecodeError:
            fores = []
    seen = {f.get("id") for f in fores}
    for f in sorted(out_dir.glob("batch-*.json")):
        if f.name.endswith(".failed.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for x in d.get("foreshadows") or []:
            if x.get("id") not in seen and not x.get("payoff_ch"):
                fores.append(x)
                seen.add(x.get("id"))
    return fores


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="书目录（含 chapters/ chunk-meta.json）")
    ap.add_argument("--out-dir", default="", help="默认 <dir>/out")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--max-batch-chars", type=int, default=36000)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-cost", type=float, default=5.0, help="元；到线即停止提交新批次")
    ap.add_argument("--chapter-range", default="", help="如 1-100")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "deepseek", "qwen", "openai", "custom"])
    ap.add_argument("--api-key", default="")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--price-in", type=float)
    ap.add_argument("--price-out", type=float)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--force", action="store_true", help="重抽已有批次")
    ap.add_argument("--limit-batches", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.dir)
    out_dir = Path(args.out_dir) if args.out_dir else root / "out"
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ch_range = None
    if args.chapter_range:
        m = re.match(r"(\d+)\s*-\s*(\d+)", args.chapter_range)
        if not m:
            raise SystemExit("--chapter-range 格式应为 1-100")
        ch_range = (int(m.group(1)), int(m.group(2)))

    meta = load_meta(root)
    chapters = load_chapters(root, meta, ch_range)
    if not chapters:
        raise SystemExit("没有可抽取的章节，检查 --chapter-range 或 chapters/ 目录")
    batches = split_batches(chapters, args.batch_size, args.max_batch_chars)
    if args.limit_batches:
        batches = batches[:args.limit_batches]

    realms = load_realms(root)
    realm_ids = {r.get("id") for r in realms}
    catalog = collect_catalog(root, out_dir, realm_ids)
    open_fores = collect_open_fores(root, out_dir)
    cfg = load_config(args)
    cost = Cost(cfg, args.max_cost)

    existing, todo = [], []
    for i, b in enumerate(batches, 1):
        hit = None if args.force else existing_ok(out_dir, b)
        if hit:
            existing.append((i, hit))
        else:
            todo.append((i, b))

    chars_total = sum(len(c["body"]) for _, b in todo for c in b)
    est_in = int(chars_total / 1.6) + len(todo) * 2500
    est_out = len(todo) * (1500 + args.batch_size * 60)
    est_cost = est_in / 1e6 * cfg["price_in"] + est_out / 1e6 * cfg["price_out"]

    print(f"书目录      {root}")
    print(f"章节        {len(chapters)}（第 {chapters[0]['ch']}–{chapters[-1]['ch']} 章）")
    print(f"分批        {len(batches)} 批 × ≤{args.batch_size} 章 / ≤{args.max_batch_chars} 字")
    print(f"已是成品    {len(existing)} 批（跳过）")
    print(f"待抽取      {len(todo)} 批 · {chars_total:,} 字")
    print(f"模型        {cfg['provider']} / {cfg['model']} @ {cfg['base_url']}")
    print(f"预算        {args.max_cost} 元 · 预计 {est_cost:.2f} 元"
          f"（输入≈{est_in / 1e4:.1f}万 token，输出≈{est_out / 1e3:.1f}k）")
    if est_cost > args.max_cost:
        print("  ⚠ 预计超预算，会按 --max-cost 熔断；可提高 --max-cost 或缩小 --chapter-range")

    if args.dry_run:
        print("dry-run：未调用模型")
        return 0

    if not todo:
        print("没有待抽取批次")
        return 0
    if not cfg["api_key"]:
        raise SystemExit(f"没有 API key：设置 {PROVIDERS.get(cfg['provider'], {}).get('env', 'API key')} "
                         f"或 data/config.json，或传 --api-key")
    if not PROMPT_PATH.exists():
        raise SystemExit(f"找不到提示词 {PROMPT_PATH}")

    prompt_tpl = PROMPT_PATH.read_text(encoding="utf-8")
    client = Client(cfg)
    log_lock = threading.Lock()
    results = []
    t_start = time.time()
    done = 0

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futs = {}
        pending = todo[:]
        while pending or futs:
            while pending and len(futs) < args.concurrency and not cost.exhausted():
                i, b = pending.pop(0)
                futs[pool.submit(run_batch, i, len(batches), b, args, cfg, client,
                                 cost, catalog, realms, open_fores, prompt_tpl,
                                 out_dir, log_lock)] = (i, b)
            if not futs:
                break
            for fut in as_completed(list(futs), timeout=None):
                i, b = futs.pop(fut)
                r = fut.result()
                results.append(r)
                done += 1
                mark = "✓" if r["ok"] else "✗"
                extra = (f"实体+{r['entities']} 关系+{r['relations']}" if r["ok"]
                         else f"失败：{r['errors'][0][:60]}")
                print(f"[{done}/{len(todo)}] {mark} {r['name']} "
                      f"ch{b[0]['ch']}-{b[-1]['ch']} · {extra} · "
                      f"累计 {cost.spent:.2f} 元 · {time.time() - t_start:.1f}s")
                break
            if cost.exhausted():
                if pending:
                    print(f"⚠ 预算熔断：已花 {cost.spent:.2f} 元，剩余 {len(pending)} 批未提交")
                pending = []

    ok = sum(1 for r in results if r["ok"])
    bad = len(results) - ok
    print(f"\n完成 {ok}/{len(todo)} 批，失败 {bad}")
    print(f"花费 {cost.spent:.2f} 元 · token 输入 {cost.prompt_tokens:,} / 输出 {cost.completion_tokens:,}"
          f" · 耗时 {time.time() - t_start:.0f}s")
    print(f"输出 {out_dir}")
    if bad:
        print("失败批次见 out/batch-*.failed.json，修好后重跑会只补失败批次")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
