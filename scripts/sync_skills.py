#!/usr/bin/env python3
"""sync_skills.py — 把 CLI 与渲染资源同步进各 skill 目录，让 skill 装完即用。

为什么要有这个脚本：

`npx skills add` 只拷贝 `skills/<name>/` 这一个目录。如果 SKILL.md 里写
`python scripts/chunk.py`，而 `scripts/` 留在仓库根，用户装完就找不到脚本。
所以脚本必须复制进 skill 本体。

但复制会带来第二个问题：副本与源码必然发散。有人改了 `scripts/merge.py`
却忘了同步，用户装到的就是旧逻辑。所以本脚本同时提供 `--check`：
CI 用它做契约检查，源码与副本不一致就直接失败。

用法：
    python scripts/sync_skills.py            # 同步（默认）
    python scripts/sync_skills.py --check    # 只检查，漂移则退出码 1
    python scripts/sync_skills.py --prune    # 同步时删掉副本里多余的文件
    python scripts/sync_skills.py --list     # 看每个 skill 该带什么
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# 副本里不需要的编译产物与空目录
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}

# 仓库维护工具，不是 skill 的运行时依赖，不随副本分发。
# 留在副本里会误导 agent 去「重新同步」一个不存在的仓库。
NEVER_VENDOR = {"sync_skills.py"}

# 每个 skill 自带什么。
#
# scripts: "all" = 整棵 scripts/ 树（含 novel_atlas 包）；list = 只带指定文件
# template: True = 带 viewer 源码 + 模板真正引用的 23 张素材
# references / atlas_kit: 额外的按需资源
#
# 只有一个 skill：六个流程（拆书/问答/疑点/对比/导出/地图）共用一套脚本与模板，
# 拆成六个 skill 时每个都要带一份 300KB 的 scripts/，装齐要 5MB 且六份副本互相发散。
# 现在 SKILL.md 只做路由，具体流程放 references/*.md，按需读取。
VENDOR = {
    "novel-atlas": {
        "scripts": "all",
        "template": True,
        "references": ["schema.md", "place-taxonomy.md"],
        "atlas_kit": ["manifest.json"],
    },
}

# skill 自有文件：不参与同步，也绝不能被 prune 删掉。
# audit.py / atlas_map.py 是 skill 自己维护的包装脚本，源码不在 scripts/ 下；
# references/*.md 是六个流程的说明，.md 一律视为自有（见 is_own）。
OWN_REL = {"SKILL.md", "_VENDORED.md", "scripts/audit.py", "scripts/atlas_map.py"}


def is_own(dst_root: Path, f: Path) -> bool:
    """判断副本里的文件是否属于 skill 自己（而非同步进来的）。"""
    if f.suffix == ".md":            # SKILL.md、references/*.md、_VENDORED.md
        return True
    return f.relative_to(dst_root).as_posix() in OWN_REL


BANNER = """<!-- 由 scripts/sync_skills.py 生成，请勿手改。 -->
<!-- 改逻辑请改仓库根的 scripts/ 或 template/，然后重跑同步脚本。 -->
"""


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def iter_files(src: Path, skip_vendor_tools: bool = True):
    """按稳定顺序遍历目录，跳过编译产物。

    skip_vendor_tools=True 用于扫描**源**：仓库维护脚本不参与分发。
    扫描**副本**时必须传 False，否则残留的 sync_skills.py 会被这里遮住，
    永远查不出来也删不掉。
    """
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIX:
            continue
        if skip_vendor_tools and p.name in NEVER_VENDOR:
            continue
        yield p


def plan(skill: str) -> list[tuple[Path, Path]]:
    """返回该 skill 需要内置的 (源文件, 目标文件) 列表。"""
    spec = VENDOR[skill]
    dst_root = SKILLS / skill
    out: list[tuple[Path, Path]] = []

    sc = spec.get("scripts")
    if sc == "all":
        for f in iter_files(ROOT / "scripts"):
            out.append((f, dst_root / "scripts" / f.relative_to(ROOT / "scripts")))
    elif isinstance(sc, list):
        for name in sc:
            out.append((ROOT / "scripts" / name, dst_root / "scripts" / name))

    if spec.get("template"):
        tpl = ROOT / "template"
        for name in ("viewer.html", "viewer.css", "viewer.js"):
            out.append((tpl / name, dst_root / "template" / name))
        for f in iter_files(tpl / "viewer"):
            out.append((f, dst_root / "template" / "viewer" / f.relative_to(tpl / "viewer")))
        # 只有被 __ASSET__: 真正引用的素材才需要，其余 90MB 是素材库
        assets = tpl / "assets" / "map" / "atlas"
        for f in iter_files(assets):
            out.append((f, dst_root / "template" / "assets" / "map" / "atlas" / f.name))

    for name in spec.get("references") or []:
        out.append((ROOT / "references" / name, dst_root / "references" / name))

    for name in spec.get("atlas_kit") or []:
        out.append((ROOT / "atlas-kit" / name, dst_root / "atlas-kit" / name))

    return out


def check(skill: str, verbose: bool) -> tuple[int, int, int]:
    """比较源与副本。返回 (缺失, 过期, 多余)。"""
    pairs = plan(skill)
    dst_root = SKILLS / skill
    missing = outdated = extra = 0
    expected = {d for _, d in pairs}

    for src, dst in pairs:
        if not src.exists():
            print(f"  ✗ 源文件不存在：{src.relative_to(ROOT)}", file=sys.stderr)
            missing += 1
            continue
        if not dst.exists():
            missing += 1
            if verbose:
                print(f"  缺  {dst.relative_to(SKILLS)}")
        elif digest(src) != digest(dst):
            outdated += 1
            if verbose:
                print(f"  旧  {dst.relative_to(SKILLS)}")

    for f in iter_files(dst_root, skip_vendor_tools=False):
        if f in expected or is_own(dst_root, f):
            continue
        extra += 1
        if verbose:
            print(f"  余  {f.relative_to(SKILLS)}")

    return missing, outdated, extra


def sync(skill: str, prune: bool) -> tuple[int, int]:
    pairs = plan(skill)
    dst_root = SKILLS / skill
    written = 0
    for src, dst in pairs:
        if not src.exists():
            print(f"  ✗ 源文件不存在：{src.relative_to(ROOT)}", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and digest(src) == digest(dst):
            continue
        shutil.copy2(src, dst)
        written += 1

    (dst_root / "_VENDORED.md").write_text(BANNER, encoding="utf-8")

    pruned = 0
    if prune:
        expected = {d for _, d in pairs}
        for f in list(iter_files(dst_root, skip_vendor_tools=False)):
            if f in expected or is_own(dst_root, f):
                continue
            f.unlink()
            pruned += 1
        for d in sorted(dst_root.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    return written, pruned


def manifest_digest() -> str:
    """所有内置文件的整体指纹，写进 _VENDORED.md 便于人工核对。"""
    h = hashlib.sha256()
    for skill in sorted(VENDOR):
        for src, _ in plan(skill):
            if src.exists():
                h.update(src.relative_to(ROOT).as_posix().encode())
                h.update(src.read_bytes())
    return h.hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description="把 CLI 同步进 skill 目录")
    ap.add_argument("--check", action="store_true", help="只检查漂移，不写入")
    ap.add_argument("--prune", action="store_true", help="删掉副本里已不存在的文件")
    ap.add_argument("--list", action="store_true", help="列出每个 skill 内置哪些文件")
    ap.add_argument("--verbose", action="store_true", help="打印每个文件")
    ap.add_argument("skill", nargs="*", help="只处理指定 skill（默认全部）")
    args = ap.parse_args()

    targets = args.skill or sorted(VENDOR)
    unknown = [t for t in targets if t not in VENDOR]
    if unknown:
        print(f"未知 skill：{', '.join(unknown)}", file=sys.stderr)
        print(f"可用的：{', '.join(sorted(VENDOR))}", file=sys.stderr)
        return 2

    if args.list:
        for skill in targets:
            pairs = plan(skill)
            size = sum(s.stat().st_size for s, _ in pairs if s.exists())
            print(f"{skill:16s} {len(pairs):3d} 个文件  {size / 1024:7.0f} KB")
            for src, _ in pairs:
                if args.verbose:
                    print(f"    {src.relative_to(ROOT)}")
        return 0

    if args.check:
        total = 0
        for skill in targets:
            m, o, e = check(skill, args.verbose)
            drift = m + o + e
            total += drift
            flag = "OK  " if drift == 0 else "漂移"
            print(f"{flag} {skill:16s} 缺 {m} · 旧 {o} · 余 {e}")
            if drift and not args.verbose:
                print(f"     修正：python scripts/sync_skills.py {skill}")
        if total:
            print(f"\n共 {total} 处漂移。skill 与源码不一致。", file=sys.stderr)
            return 1
        print(f"\n{len(targets)} 个 skill 与源码一致（指纹 {manifest_digest()}）")
        return 0

    for skill in targets:
        w, p = sync(skill, args.prune)
        note = f"，清理 {p} 个多余文件" if p else ""
        if w or p:
            print(f"同步 {skill:16s} 写入 {w} 个{note}")
        else:
            print(f"同步 {skill:16s} 已是最新")
    print(f"\n指纹 {manifest_digest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
