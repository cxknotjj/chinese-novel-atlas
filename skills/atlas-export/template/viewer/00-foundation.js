/* Novel Atlas viewer · 数据、截断、颜色与公共小工具
   职责：FULL_D / D / 阅读进度 / 调色板 / 实体索引 */
  const FULL_D = window.ATLAS_DATA;
  if (!FULL_D) {
    document.body.innerHTML = '<p style="padding:40px">未找到数据文件 samples/fictional/data.js</p>';
    return;
  }

  /* ================= 读者进度 ================= */
  function maxChapter(data) {
    return Math.max(
      ...(data.chapters || []).map(c => c.ch),
      ((data.meta.coverage || {}).chapters_done) || 0,
      1
    );
  }
  function titleKey(data) {
    return 'novel-atlas.cutoff.' + (data.meta.title || 'untitled');
  }
  function readCutoff(data) {
    const max = maxChapter(data);
    let value = null;
    try { value = localStorage.getItem(titleKey(data)); } catch (e) {}
    const q = new URLSearchParams(location.search).get('cutoff');
    if (q !== null && q !== '') value = Number(q);
    value = Number(value);
    if (!Number.isFinite(value) || value <= 0) value = max;
    return Math.max(1, Math.min(Math.round(value), max));
  }
  function cutForReader(full, cutoff) {
    const copy = JSON.parse(JSON.stringify(full));
    const c = Math.max(1, Math.min(cutoff, maxChapter(full)));
    const meta = full.meta || {};
    const done = (meta.coverage && meta.coverage.chapters_done) || maxChapter(full);
    const visibleEntity = e => typeof e.first_ch === 'number' && e.first_ch > 0 && e.first_ch <= c;
    const entityIds = new Set((full.entities || []).filter(visibleEntity).map(e => e.id));

    copy.entities = (full.entities || []).filter(visibleEntity).map(e => {
      const x = JSON.parse(JSON.stringify(e));
      x.power_history = (x.power_history || []).filter(p => typeof p.ch === 'number' && p.ch <= c);
      if (typeof x.last_ch === 'number' && x.last_ch > c) x.last_ch = null;
      return x;
    });
    copy.relations = (full.relations || []).filter(r =>
      typeof r.first_ch !== 'number' || (r.first_ch <= c && entityIds.has(r.s) && entityIds.has(r.t)));
    copy.chapters = (full.chapters || []).filter(ch => ch.ch <= c).map(ch => {
      const x = JSON.parse(JSON.stringify(ch));
      x.battles = (x.battles || []).filter(b => entityIds.has(b.a) && entityIds.has(b.b));
      return x;
    });

    copy.foreshadows = (full.foreshadows || []).filter(f =>
      typeof f.plant_ch === 'number' && f.plant_ch <= c).map(f => {
      const x = JSON.parse(JSON.stringify(f));
      if (typeof x.payoff_ch === 'number' && x.payoff_ch > c) {
        x.payoff_ch = null; x.payoff_quote = null;
      }
      if (typeof x.last_mention_ch === 'number' && x.last_mention_ch > c) x.last_mention_ch = null;
      return x;
    });

    copy.knowledge = (full.knowledge || []).filter(k => {
      const truth = typeof k.truth_ch === 'number' ? k.truth_ch : 0;
      const known = typeof k.reader_known_ch === 'number' ? k.reader_known_ch : truth;
      return truth > 0 && truth <= c && known <= c;
    }).map(k => {
      const x = JSON.parse(JSON.stringify(k));
      x.known_by = (x.known_by || []).filter(v =>
        typeof v.ch === 'number' && v.ch <= c && entityIds.has(v.entity));
      return x;
    });

    const placeIds = new Set((full.places || []).filter(p =>
      typeof p.first_ch === 'number' && p.first_ch <= c).map(p => p.id));
    copy.places = (full.places || []).filter(p => placeIds.has(p.id));
    copy.spatial_relations = (full.spatial_relations || []).filter(r =>
      placeIds.has(r.s) && placeIds.has(r.t) &&
      (typeof r.first_ch !== 'number' || r.first_ch <= c) &&
      (!r.evidence || typeof r.evidence.ch !== 'number' || r.evidence.ch <= c));
    copy.concepts = (full.concepts || []).filter(x =>
      typeof x.first_ch !== 'number' || x.first_ch <= c);
    copy.volumes = full.volumes || [];

    if (copy.map_layout && typeof copy.map_layout === 'object') {
      const ml = copy.map_layout;
      ml.nodes = (ml.nodes || []).filter(n => placeIds.has(n.place));
      ml.regions = (ml.regions || []).filter(r => !r.layer || placeIds.has(r.layer));
      const regionIds = new Set(ml.regions.map(r => r.id));
      ml.routes = (ml.routes || []).filter(r => placeIds.has(r.s) && placeIds.has(r.t));
      if (ml.terrain && typeof ml.terrain === 'object') {
        const keepRegion = x => !x.region || regionIds.has(x.region);
        ml.terrain = {
          ridges: (ml.terrain.ridges || []).filter(keepRegion),
          rivers: (ml.terrain.rivers || []).filter(keepRegion),
          lakes: (ml.terrain.lakes || []).filter(keepRegion),
          islets: ml.terrain.islets || []
        };
      }
      if (ml.atlas && typeof ml.atlas === 'object') {
        ml.atlas.stamps = (ml.atlas.stamps || []).filter(s =>
          (!s.attach || placeIds.has(s.attach)) && (!s.layer || placeIds.has(s.layer)));
        if (ml.atlas.markers) {
          ml.atlas.markers = Object.fromEntries(
            Object.entries(ml.atlas.markers).filter(([id]) => placeIds.has(id)));
        }
      }
    }

    const evCh = ev => {
      const m = String((ev && ev.coordinate) || '').match(/^ch(\d+)/);
      return m ? Number(m[1]) : null;
    };
    copy.anomalies = (full.anomalies || []).filter(a => {
      const rng = a.chapter_range || [];
      const end = rng.length > 1 ? Number(rng[1]) : Number(rng[0] || 0);
      if (end && end > c) return false;
      return (a.evidence || []).every(e => {
        const ch = evCh(e);
        return ch === null || ch <= c;
      });
    });

    copy._reader = {
      cutoff_ch: c,
      cut: c,
      analyzed_ch: done,
      chapter_max: maxChapter(full),
      total_chapters: meta.chapters || 0,
      analysis_complete: !!(meta.chapters && done >= meta.chapters),
      is_spoiler_safe: c < maxChapter(full)
    };
    return copy;
  }

  const CUTOFF = readCutoff(FULL_D);
  const D = cutForReader(FULL_D, CUTOFF);
  window.ATLAS_DATA = D;

  /* ================= 数据适配 ================= */
  const CHAPTERS = D.chapters || [];
  const REALMS = (D.realms || []).slice().sort((a, b) => a.order - b.order);
  const FORESHADOWS = D.foreshadows || [];
  const CURRENT_CH = (D._reader && D._reader.cutoff_ch) || Math.max(
    ...CHAPTERS.map(c => c.ch),
    (D.meta.coverage && D.meta.coverage.chapters_done) || 0,
    1
  );
  // 阈值与 scripts/merge.py、validate.py、export.py 保持一致：
  // 以「已分析到的章数」为跨度基准，下限 50 章。
  // 不能全用全书章数——只拆前 200 章时，2443 章的 15% 是 366，
  // 会让所有坑永远无法触发告警，功能形同失效。
  const FS_SPAN = Math.max(CURRENT_CH, 1);
  const FS_THRESHOLD = Math.max(50, Math.round(FS_SPAN * 0.15));

  // 阵营配色：按出现顺序动态分配，任何书都能用
  const PALETTE = ['#A6314A', '#3D6B7D', '#6B4A7A', '#B8925A', '#5A7A5E',
                   '#7A6A5A', '#7A8A9A', '#9A9488'];
  const GROUP_COLOR = {};
  [...new Set(D.entities.map(e => e.group))].forEach((g, i) => {
    GROUP_COLOR[g] = PALETTE[i % PALETTE.length];
  });
  // 每个境界用不同色相；同境界内再由浅到深表示小阶成长，突破后换色重新变浅。
  const REALM_COLOR = ['#4F7C8A', '#5C8A63', '#B08A4E', '#8C5470',
                       '#A64B45', '#6B6D8F', '#8A6A46', '#4F7F7A'];
  const REL_STYLE = {
    kinship:    { color: '#C9C2B2', width: 1.2, dash: [] },
    marriage:   { color: '#C0A06E', width: 1.8, dash: [] },
    romance:    { color: '#C97A8C', width: 1.6, dash: [5, 4] },
    service:    { color: '#D8D2C4', width: 1.0, dash: [2, 3] },
    mentorship: { color: '#9FB3BC', width: 1.2, dash: [6, 3] },
    alliance:   { color: '#A8B79C', width: 1.3, dash: [] },
    conflict:   { color: '#C25A5A', width: 1.6, dash: [1, 3] },
    social:     { color: '#D5CFC2', width: 0.9, dash: [] }
  };
  const REL_CN = {
    kinship: '血亲', marriage: '婚姻', romance: '情感', service: '主从',
    mentorship: '师承', alliance: '同盟', conflict: '敌对', social: '交游'
  };

  /* 实体类型图标：人物 / 势力 / 器物 / 妖兽，线稿 SVG 随文字颜色走 */
  const TYPE_NAME = { character: '人物', org: '势力', item: '器物', creature: '妖兽' };
  const ENTITY_ICON = {
    character: `<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <circle cx="10" cy="6.2" r="2.8"></circle>
      <path d="M4.6 16.8c.4-3.8 2.5-5.8 5.4-5.8s5 2 5.4 5.8"></path>
    </svg>`,
    org: `<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M3.4 8.2 10 3.8l6.6 4.4"></path>
      <path d="M5.1 8.4v7.4M14.9 8.4v7.4M8 15.8v-4h4v4"></path>
      <path d="M3.6 17.6h12.8"></path>
    </svg>`,
    item: `<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M12.5 3.2 16.8 7.5 8.7 15.6H5.2v-3.5l7.3-7.3z"></path>
      <path d="M10.6 5.1 14.9 9.4"></path>
      <path d="M4 16.8 6.5 14.3"></path>
    </svg>`,
    creature: `<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M6.1 12.2c-1.2 0-2.1.9-2.1 2 0 1.4 1.2 2 2.7 2h6.6c1.5 0 2.7-.6 2.7-2 0-1.1-.9-2-2.1-2H6.1z"></path>
      <circle cx="5.6" cy="7.1" r="1.5"></circle>
      <circle cx="9.8" cy="5.2" r="1.6"></circle>
      <circle cx="14.4" cy="7.1" r="1.5"></circle>
    </svg>`
  };
  function entityIcon(type, cls) {
    if (!ENTITY_ICON[type]) return '';
    const extra = cls ? ' ' + cls : '';
    return `<span class="entity-icon entity-icon-${type}${extra}" title="${TYPE_NAME[type] || type}">${ENTITY_ICON[type]}</span>`;
  }
  const STATUS_META = {
    overdue: { cn: '已超期', color: '#C0392B', bg: '#FDF1EF' },
    planted: { cn: '待回收', color: '#B8925A', bg: '#FBF5EA' },
    paid:    { cn: '有回收章', color: '#5A7A5E', bg: '#EFF5EE' },
    dropped: { cn: '已放弃', color: '#9A9488', bg: '#F2EFE7' }
  };
  const EMOTION_COLOR = {
    '爽': '#C0533F', '压抑': '#7A7A85', '紧张': '#B8925A',
    '温情': '#C98B9E', '悲': '#6B7A8F', '平': '#B4B2A9'
  };

  /* 伏笔状态：派生，不信任存储值 */
  /** 距最后一次提及过了多久；没有提及数据时退回埋设章 */
  function fsSilent(f) {
    const last = f.last_mention_ch || f.plant_ch;
    return CURRENT_CH - last;
  }
  function fsStatus(f) {
    if (f.payoff_ch !== null && f.payoff_ch !== undefined && f.payoff_ch !== f.plant_ch) return 'paid';
    if (f.status === 'dropped') return 'dropped';
    return fsSilent(f) > FS_THRESHOLD ? 'overdue' : 'planted';
  }

  /* ================= 建索引 ================= */
  const byId = new Map();
  D.entities.forEach(e => byId.set(e.id, e));
  const allById = new Map();
  D.entities.forEach(e => allById.set(e.id, Object.assign({ _kind: 'entity' }, e)));
  D.places.forEach(p => allById.set(p.id, Object.assign({ _kind: 'place' }, p)));
  D.concepts.forEach(c => allById.set(c.id, Object.assign({ _kind: 'concept' }, c)));
  const realmById = new Map(REALMS.map(r => [r.id, r]));

  /* ---------- 地点 / 势力索引 ---------- */
  const PLACES = D.places || [];
  const placeById = new Map(PLACES.map(p => [p.id, p]));
  const chapterByCh = new Map(CHAPTERS.map(c => [c.ch, c]));
  const orgEntities = D.entities.filter(e => e.type === 'org');
  const keyName = s => String(s || '').replace(/\s+/g, '').trim();
  const escHtml = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const orgByName = new Map();
  orgEntities.forEach(o => {
    [o.name, ...(o.aliases || [])].forEach(n => {
      const k = keyName(n);
      if (k && !orgByName.has(k)) orgByName.set(k, o);
    });
  });

  const orgRootCache = new Map();
  function orgRootOf(o) {
    if (!o || o.type !== 'org') return null;
    if (orgRootCache.has(o.id)) return orgRootCache.get(o.id);
    let cur = o;
    const seen = new Set();
    while (cur && cur.parent && !seen.has(cur.id)) {
      seen.add(cur.id);
      const parent = byId.get(cur.parent);
      if (!parent || parent.type !== 'org') break;
      cur = parent;
    }
    orgRootCache.set(o.id, cur);
    return cur;
  }

  function explicitPlaceOwner(p) {
    const attrs = p.attrs || {};
    for (const key of ['所属势力', '门派', '势力', '所属']) {
      const hit = orgByName.get(keyName(attrs[key]));
      if (hit) return { org: hit, key, value: attrs[key] };
    }
    return null;
  }

  const placeOwnerCache = new Map();
  function placeOwnerInfo(p) {
    if (placeOwnerCache.has(p.id)) return placeOwnerCache.get(p.id);
    const attrs = p.attrs || {};
    const desc = p.desc || '';
    let info = { roots: [], direct: null, special: null, disputed: false, basis: '' };

    const explicit = explicitPlaceOwner(p);
    if (explicit) {
      info.direct = explicit.org;
      info.roots = [orgRootOf(explicit.org)];
      info.basis = `attrs.${explicit.key} = ${explicit.value}`;
    } else if (/交界|争议/.test(desc)) {
      // 只在描述明确写「交界」时，把提到的势力都列为争议方，不靠猜
      const found = [];
      orgEntities.forEach(o => {
        const names = [o.name, ...(o.aliases || [])].filter(Boolean);
        if (names.some(n => desc.includes(n))) {
          const root = orgRootOf(o);
          if (root && !found.includes(root)) found.push(root);
        }
      });
      if (found.length > 1) {
        info.roots = found;
        info.disputed = true;
        info.basis = '描述明确为交界之地，列出双方而非单方归属';
      }
    }

    if (!info.roots.length && !info.special && p.parent) {
      const parent = placeById.get(p.parent);
      if (parent) {
        const pinfo = placeOwnerInfo(parent);
        if (pinfo.roots.length) {
          info.roots = pinfo.roots;
          info.disputed = pinfo.disputed;
          info.basis = `继承自父地点「${parent.name}」：${pinfo.basis}`;
        } else if (pinfo.special) {
          info.special = pinfo.special;
          info.basis = `继承自父地点「${parent.name}」：${pinfo.special}`;
        }
      }
    }

    if (!info.roots.length && !info.special && /共管/.test(desc)) {
      info.special = '七派共管';
      info.basis = '描述明确为多派共管，不强行归给单一势力';
    }

    placeOwnerCache.set(p.id, info);
    return info;
  }

  const placeChildren = new Map();
  const placeRoots = [];
  PLACES.forEach(p => {
    if (p.parent && placeById.has(p.parent)) {
      if (!placeChildren.has(p.parent)) placeChildren.set(p.parent, []);
      placeChildren.get(p.parent).push(p);
    } else {
      placeRoots.push(p);
    }
  });
  const byFirstCh = (a, b) => (a.first_ch || 9999) - (b.first_ch || 9999) || a.name.localeCompare(b.name, 'zh');
  placeRoots.sort(byFirstCh);
  placeChildren.forEach(list => list.sort(byFirstCh));

  const GEO_STAGES = [
    { label: '山门一带', max: 40, color: '#2A5666', note: '第 1–40 章' },
    { label: '门内深处与下山', max: 143, color: '#4E7C8F', note: '第 41–143 章' },
    { label: '黄枫谷', max: 178, color: '#B8925A', note: '第 144–178 章' },
    { label: '秘境', max: 9999, color: '#A6314A', note: '第 179 章以后' }
  ];
  function placeStage(p) {
    const ch = p.first_ch || 0;
    return GEO_STAGES.find(s => ch <= s.max) || GEO_STAGES[GEO_STAGES.length - 1];
  }

  function placeDepth(p) {
    let n = 0, cur = p, seen = new Set();
    while (cur && cur.parent && placeById.has(cur.parent) && !seen.has(cur.id)) {
      seen.add(cur.id); cur = placeById.get(cur.parent); n++;
    }
    return n;
  }
  function placePath(p) {
    const path = [];
    let cur = p, seen = new Set();
    while (cur && !seen.has(cur.id)) {
      seen.add(cur.id); path.unshift(cur);
      cur = cur.parent ? placeById.get(cur.parent) : null;
    }
    return path;
  }

  const deg = new Map();
  D.relations.forEach(r => {
    deg.set(r.s, (deg.get(r.s) || 0) + 1);
    deg.set(r.t, (deg.get(r.t) || 0) + 1);
  });

  function realmIndex(id) {
    const r = realmById.get(id);
    return r ? r.order : 0;
  }
  function powerAt(id) {
    const e = byId.get(id);
    const h = (e && e.power_history) || [];
    if (!h.length) return null;
    let cur = h[0];
    h.forEach(p => { if (p.ch <= CURRENT_CH) cur = p; });
    return cur;
  }
  /** 指定章号时的修为（取该章或之前最后一条） */
  function powerAtCh(id, ch) {
    const e = byId.get(id);
    const h = (e && e.power_history) || [];
    let cur = null;
    h.forEach(p => { if (p.ch <= ch) cur = p; });
    return cur || h[0] || null;
  }
  function powerFull(p) {
    if (!p) return '—';
    const r = realmById.get(p.realm);
    return (r ? r.name : p.realm) + (p.stage ? '·' + p.stage : '');
  }
  /** 综合等级数：境界序 ×100 + 层数序，用于跨境界与同境界内比较 */
  function levelNum(p) {
    if (!p) return 0;
    const r = realmById.get(p.realm);
    const st = (r && r.stages) || [];
    const i = st.indexOf(p.stage);
    return (r ? r.order : 0) * 100 + (i >= 0 ? i : 0);
  }
  /** 把等级差换算成可读文案：同境界内说「X 层」，跨境界说「X 级」 */
  function fbLayer(diff) {
    const a = Math.abs(diff);
    return a >= 100 ? `${Math.floor(a / 100)} 级` : `${a} 层`;
  }
  /** 境界内的层数比例 0..1，用于同境界内部的色阶渐变；无细分时按初入浅色处理 */
  function stageFrac(p) {
    if (!p) return 0;
    const r = realmById.get(p.realm);
    const st = (r && r.stages) || [];
    if (!st.length) return 0;
    const i = st.indexOf(p.stage);
    return i < 0 ? 0 : (st.length > 1 ? i / (st.length - 1) : 0);
  }
  /** 境界基色：每个境界一个色相，按 order 取色，超出后循环 */
  function realmBaseColor(realmId) {
    const ri = Math.max(realmIndex(realmId), 1);
    return REALM_COLOR[(ri - 1) % REALM_COLOR.length];
  }
  /** 境界内色阶：frac 0=初入浅色，1=巅峰深色；80% → 40% 保证在米色轨道上可辨 */
  function realmTone(realmId, frac) {
    const base = realmBaseColor(realmId);
    const f = Math.max(0, Math.min(1, Number(frac) || 0));
    return shade(base, 80 - f * 40);
  }
  /** 境界基色 + 层数明度：练气一层浅、九层深，一眼看出成长 */
  function realmColorOf(p) {
    return realmTone(p && p.realm, stageFrac(p));
  }
  function shade(hex, lightness) {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    const max = Math.max(r, g, b) / 255, min = Math.min(r, g, b) / 255;
    let h = 0, s = 0;
    const L0 = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = L0 > 0.5 ? d / (2 - max - min) : d / (max + min);
      h = max === r / 255 ? ((g / 255 - b / 255) / d + (g < b ? 6 : 0))
        : max === g / 255 ? ((b / 255 - r / 255) / d + 2)
        : ((r / 255 - g / 255) / d + 4);
      h *= 60;
    }
    return `hsl(${h.toFixed(0)}, ${(s * 100).toFixed(0)}%, ${lightness.toFixed(0)}%)`;
  }

  /* ================= 顶栏 ================= */
  const overdueCnt = FORESHADOWS.filter(f => fsStatus(f) === 'overdue').length;
  const analyzedCh = (D.meta.coverage && D.meta.coverage.chapters_done) || D.chapters.length;
  const isPartial = analyzedCh < D.meta.chapters;
  const cutoff = CURRENT_CH;
  document.getElementById('title').textContent = D.meta.title;
  document.getElementById('tag').textContent =
    [D.meta.genre, D.meta.platform, D.meta.status].filter(Boolean).join(' · ') +
    (isPartial ? ` · 已分析 ${analyzedCh} 章` : ' · 全书');
  document.getElementById('stats').innerHTML =
    `<span class="cov"><b>${cutoff}</b> / ${D.meta.chapters} 章可读</span>` +
    `<span class="book"><b>${(D.meta.chars / 10000).toFixed(0)}</b> 万字</span>` +
    `<span><b>${D.entities.filter(e => e.type === 'character').length}</b> 角色</span>` +
    `<span class="entities"><b>${D.entities.length}</b> 实体</span>`;
  if (overdueCnt) {
    const dot = document.getElementById('fsDot');
    dot.hidden = false;
    dot.title = overdueCnt + ' 个伏笔在当前进度已超期';
  }

  /* ---------- 阅读进度控件 ---------- */
  function renderReaderBar() {
    const max = maxChapter(FULL_D);
    const range = document.getElementById('cutoff');
    const label = document.getElementById('cutoffLabel');
    const hint = document.getElementById('readerHint');
    if (!range || !label || !hint) return;
    range.min = 1;
    range.max = max;
    range.value = cutoff;
    label.textContent = `第 ${cutoff} / ${max} 章`;
    const allBtn = document.getElementById('cutoffAll');
    if (allBtn) allBtn.disabled = cutoff >= max;
    const nextBtn = document.getElementById('cutoffNext');
    if (nextBtn) nextBtn.disabled = cutoff >= max;
    const done = (FULL_D.meta.coverage && FULL_D.meta.coverage.chapters_done) || max;
    const total = FULL_D.meta.chapters || max;
    if (cutoff < max) {
      hint.className = 'reader-hint is-future';
      hint.textContent = `只显示第 1–${cutoff} 章；第 ${cutoff + 1} 章后默认锁定`;
    } else if (done < total) {
      hint.className = 'reader-hint';
      hint.textContent = `档案覆盖到第 ${max} 章（全书 ${total} 章；后续尚未分析）`;
    } else {
      hint.className = 'reader-hint';
      hint.textContent = '全书已解锁 · 可拖动进度回看任意章节';
    }
  }
  function goCutoff(n) {
    const max = maxChapter(FULL_D);
    const next = Math.max(1, Math.min(max, Math.round(n)));
    try { localStorage.setItem(titleKey(FULL_D), String(next)); } catch (e) {}
    const url = new URL(location.href);
    url.searchParams.set('cutoff', String(next));
    url.hash = '';
    location.href = url.toString();
  }
  if (document.getElementById('cutoff')) {
    renderReaderBar();
    const range = document.getElementById('cutoff');
    range.addEventListener('input', () => {
      document.getElementById('cutoffLabel').textContent = `第 ${range.value} / ${maxChapter(FULL_D)} 章`;
    });
    range.addEventListener('change', () => goCutoff(range.value));
    document.getElementById('cutoffPrev').addEventListener('click', () => goCutoff(cutoff - 10));
    document.getElementById('cutoffNext').addEventListener('click', () => goCutoff(cutoff + 10));
    document.getElementById('cutoffAll').addEventListener('click', () => goCutoff(maxChapter(FULL_D)));
  }

