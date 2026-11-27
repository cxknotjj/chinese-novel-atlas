
(function () {
  const D = window.ATLAS_DATA;
  if (!D) {
    document.body.innerHTML = '<p style="padding:40px">未找到数据文件 samples/fictional/data.js</p>';
    return;
  }

  /* ================= 数据适配 ================= */
  const CHAPTERS = D.chapters || [];
  const REALMS = (D.realms || []).slice().sort((a, b) => a.order - b.order);
  const FORESHADOWS = D.foreshadows || [];
  const CURRENT_CH = Math.max(
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
  const REALM_COLOR = ['#C3D5DC', '#8FB0BE', '#4E7C8F', '#2A5666', '#1B3F4D'];
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
  /** 境界内的层数比例 0..1，用于同境界内部的色阶渐变 */
  function stageFrac(p) {
    if (!p) return 0;
    const r = realmById.get(p.realm);
    const st = (r && r.stages) || [];
    if (!st.length) return 0.5;
    const i = st.indexOf(p.stage);
    return i < 0 ? 0.5 : (st.length > 1 ? i / (st.length - 1) : 0.5);
  }
  /** 境界基色 + 层数明度：练气一层浅、九层深，一眼看出成长 */
  function realmColorOf(p) {
    const ri = Math.max(realmIndex(p && p.realm), 1);
    const base = REALM_COLOR[Math.min(ri - 1, REALM_COLOR.length - 1)];
    const f = stageFrac(p);
    // 同境界内：明度 84% → 46%
    const l = 84 - f * 38;
    return shade(base, l);
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
  const doneCh = (D.meta.coverage && D.meta.coverage.chapters_done) || D.chapters.length;
  const isPartial = doneCh < D.meta.chapters;
  document.getElementById('title').textContent = D.meta.title;
  document.getElementById('tag').textContent =
    [D.meta.genre, D.meta.platform, D.meta.status].filter(Boolean).join(' · ') +
    (isPartial ? ` · 已拆 ${doneCh} 章` : '');
  document.getElementById('stats').innerHTML =
    `<span class="cov"><b>${doneCh}</b> / ${D.meta.chapters} 章已分析</span>` +
    `<span class="book"><b>${(D.meta.chars / 10000).toFixed(0)}</b> 万字</span>` +
    `<span><b>${D.entities.filter(e => e.type === 'character').length}</b> 角色</span>` +
    `<span class="entities"><b>${D.entities.length}</b> 实体</span>`;
  if (overdueCnt) {
    const dot = document.getElementById('fsDot');
    dot.hidden = false;
    dot.title = overdueCnt + ' 个伏笔已超期';
  }

  /* ================= 图谱 ================= */
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 2);

  const rawNodes = D.entities.map(e => {
    const d = deg.get(e.id) || 0;
    return {
      id: e.id, ref: e, name: e.name,
      r: 6.8 + Math.min(d, 22) * 0.58,
      d, x: 0, y: 0, vx: 0, vy: 0, fixed: false,
      dimT: 0, selT: 0        // 变暗 / 选中的过渡进度，0→1 插值用
    };
  });
  // 只画有关系连线的节点。孤立点没有信息量，还会把核心群挤到角落
  const nodes = rawNodes.filter(n => n.d > 0);
  const isolatedCount = rawNodes.length - nodes.length;
  const nodeById = new Map(nodes.map(n => [n.id, n]));

  const groups = [...new Set(nodes.map(n => n.ref.group))];
  const GOLDEN = Math.PI * (3 - Math.sqrt(5));
  groups.forEach((g, gi) => {
    const members = nodes.filter(n => n.ref.group === g);
    const count = members.length;

    // “其他”大多是互不相干的散点，硬塞进一个阵营会堆成一团
    if (g === '其他' || count > 42) {
      members.forEach((n, i) => {
        const a = i * GOLDEN + gi * 1.7;
        const ring = 315 + (i % 7) * 27 + (count > 42 ? 30 : 0);
        n.x = Math.cos(a) * ring * 1.12;
        n.y = Math.sin(a) * ring * 0.82;
      });
      return;
    }

    const a = (gi / Math.max(groups.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const ring = 245 + Math.min(120, Math.sqrt(count) * 15);
    const cx = Math.cos(a) * ring * 1.2;
    const cy = Math.sin(a) * ring * 0.9;
    const memberR = 38 + Math.sqrt(count) * 13;
    members.forEach((n, i) => {
      const t = (i / Math.max(1, members.length)) * Math.PI * 2 + (gi % 2 ? 0.35 : 0);
      const rr = memberR * (0.72 + Math.random() * 0.4);
      n.x = cx + Math.cos(t) * rr + (Math.random() - .5) * 12;
      n.y = cy + Math.sin(t) * rr + (Math.random() - .5) * 12;
    });
  });

  const groupAnchors = new Map();
  groups.forEach(g => {
    const members = nodes.filter(n => n.ref.group === g);
    if (g !== '其他' && members.length > 1) {
      groupAnchors.set(g, {
        x: members.reduce((s, n) => s + n.x, 0) / members.length,
        y: members.reduce((s, n) => s + n.y, 0) / members.length
      });
    }
  });

  const links = D.relations.map(r => ({
    s: nodeById.get(r.s), t: nodeById.get(r.t), ref: r,
    w: r.weight || 0.5, type: r.type,
    actT: 1                  // 高亮过渡进度，初始全亮
  })).filter(l => l.s && l.t);

  const adj = new Map();
  links.forEach(l => {
    if (!adj.has(l.s.id)) adj.set(l.s.id, new Set());
    if (!adj.has(l.t.id)) adj.set(l.t.id, new Set());
    adj.get(l.s.id).add(l.t.id);
    adj.get(l.t.id).add(l.s.id);
  });

  let graphScope = 'core';
  let groupFilter = '';
  const coreCount = nodes.filter(n => n.ref.type === 'org' || n.d >= 3).length;

  function visibleNode(n) {
    if (groupFilter) return n.ref.group === groupFilter;
    if (graphScope === 'core') return n.ref.type === 'org' || n.d >= 3;
    return true;
  }
  function visibleLink(l) { return visibleNode(l.s) && visibleNode(l.t); }

  function ensureNodeVisible(id) {
    const n = nodeById.get(id);
    if (n && !visibleNode(n)) {
      groupFilter = '';
      graphScope = 'all';
      updateGraphTools();
    }
  }

  function updateGraphTools() {
    const core = document.getElementById('scopeCore');
    const all = document.getElementById('scopeAll');
    const sel = document.getElementById('groupFilter');
    if (!core || !all || !sel) return;
    core.textContent = `核心 ${coreCount}`;
    all.textContent = `全部 ${nodes.length}`;
    core.classList.toggle('on', graphScope === 'core');
    all.classList.toggle('on', graphScope === 'all');
    if (!sel.dataset.init) {
      sel.innerHTML = `<option value="">全部势力</option>` +
        groups.map(g => `<option value="${g}">${g}</option>`).join('');
      sel.dataset.init = '1';
      sel.addEventListener('change', () => {
        groupFilter = sel.value;
        if (groupFilter) graphScope = 'all';
        updateGraphTools();
        hoverId = hoverLink = null;
        fitView();
        alpha = Math.max(alpha, 0.22);
      });
    }
    sel.value = groupFilter;
    document.getElementById('scopeCore').onclick = () => {
      graphScope = 'core'; groupFilter = ''; updateGraphTools(); fitView(); alpha = Math.max(alpha, 0.22);
    };
    document.getElementById('scopeAll').onclick = () => {
      graphScope = 'all'; groupFilter = ''; updateGraphTools(); fitView(); alpha = Math.max(alpha, 0.22);
    };
  }

  let view = { x: 0, y: 0, k: 1 };
  let hoverId = null, hoverLink = null, selectId = null, alpha = 1;
  let camAnim = null;
  const ripples = [];
  let pointer = { x: 0, y: 0 };

  function mixHex(a, b, t) {
    const parse = c => {
      c = (c || '#999').replace('#', '');
      if (c.length === 3) c = c.split('').map(x => x + x).join('');
      return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)];
    };
    const A = parse(a), B = parse(b);
    return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
  }

  // 把某个节点平滑移到可视区中心；右侧详情面板展开时，中心左移，避免被面板挡住
  function centerOn(n, animate) {
    if (!n) return;
    const panelW = panel.classList.contains('open') ? Math.min(348, W * 0.48) : 0;
    const tx = (W - panelW) / 2 - n.x * view.k;
    const ty = H / 2 - n.y * view.k;
    if (!animate) { view.x = tx; view.y = ty; camAnim = null; return; }
    camAnim = { fx: view.x, fy: view.y, tx, ty, start: performance.now(), dur: 460 };
  }

  function stepCamera(now) {
    if (!camAnim) return;
    const t = Math.min(1, (now - camAnim.start) / camAnim.dur);
    const e = 1 - Math.pow(1 - t, 3);
    view.x = camAnim.fx + (camAnim.tx - camAnim.fx) * e;
    view.y = camAnim.fy + (camAnim.ty - camAnim.fy) * e;
    if (t >= 1) camAnim = null;
  }

  function pulseNode(n) {
    if (!n) return;
    ripples.push({ n, t: 0 });
    if (ripples.length > 3) ripples.shift();
  }

  function screenRoundRect(x, y, w, h, r) {
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
    else {
      ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }
  }

  function drawRelationLabels(focus, hot) {
    if (!links.length || W <= 0) return;
    const boxes = [];
    const place = (text, sx, sy, color) => {
      ctx.font = '10px -apple-system, "PingFang SC", sans-serif';
      const tw = ctx.measureText(text).width;
      const bw = tw + 12, bh = 17;
      const candidates = [0, 11, -11, 22, -22];
      for (const off of candidates) {
        const x = sx + off;
        const y = sy;
        const left = x - bw / 2, top = y - bh / 2;
        if (left < 4 || top < 4 || left + bw > W - 4 || top + bh > H - 4) continue;
        const box = { l: left, t: top, r: left + bw, b: top + bh };
        if (boxes.some(b => !(box.r < b.l - 2 || box.l > b.r + 2 || box.b < b.t - 2 || box.t > b.b + 2))) continue;
        boxes.push(box);
        ctx.globalAlpha = 0.95;
        screenRoundRect(left, top, bw, bh, 4);
        ctx.fillStyle = 'rgba(250,249,245,0.94)';
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.9;
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#45423B';
        ctx.textAlign = 'center';
        ctx.fillText(text, x, y + 3.5);
        return true;
      }
      return false;
    };

    let candidates = [];
    if (focus) {
      candidates = links.filter(l => visibleLink(l) && hot.has(l.s.id) && hot.has(l.t.id))
        .sort((a, b) => b.w - a.w).slice(0, 16);
    } else if (!hoverLink) {
      if (view.k >= 1.1) {
        candidates = links.filter(visibleLink).sort((a, b) => b.w - a.w).slice(0, 34);
      } else {
        // 远景下只标出最重要的几条关系，避免一上来就被标签淹没
        candidates = links.filter(visibleLink).sort((a, b) => b.w - a.w).slice(0, 8);
      }
    }

    candidates.forEach(l => {
      const a = toScreen(l.s), b = toScreen(l.t);
      const dx = b.x - a.x, dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      if (len < 54) return;
      const nx = -dy / len, ny = dx / len;
      const mx = (a.x + b.x) / 2 + nx * 8;
      const my = (a.y + b.y) / 2 + ny * 8;
      const st = REL_STYLE[l.type] || REL_STYLE.social;
      place(relLabel(l), mx, my, st.color);
    });
  }

  function drawLinkTooltip() {
    if (!hoverLink) return;
    const st = REL_STYLE[hoverLink.type] || REL_STYLE.social;
    const text = `${hoverLink.s.name} · ${relLabel(hoverLink)} · ${hoverLink.t.name}`;
    ctx.font = '11px -apple-system, "PingFang SC", sans-serif';
    const bw = ctx.measureText(text).width + 20, bh = 25;
    let left = pointer.x + 13, top = pointer.y - 36;
    if (left + bw > W - 6) left = pointer.x - bw - 13;
    if (top < 6) top = pointer.y + 14;
    if (left < 6) left = 6;
    if (top + bh > H - 6) top = H - bh - 6;
    screenRoundRect(left, top, bw, bh, 5);
    ctx.fillStyle = 'rgba(255,255,255,0.97)';
    ctx.fill();
    ctx.strokeStyle = st.color;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#2B2A26';
    ctx.textAlign = 'left';
    ctx.fillText(text, left + 10, top + 16);
  }

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    W = rect.width; H = rect.height;
    if (W <= 0 || H <= 0) return;
    canvas.width = W * DPR; canvas.height = H * DPR;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function tick() {
    if (alpha < 0.008) return;
    const cx = (W / 2 - view.x) / view.k;
    const cy = (H / 2 - view.y) / view.k;
    const k = 0.0009 * alpha;

    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) { d2 = 1; dx = Math.random() - .5; dy = Math.random() - .5; }
        const d = Math.sqrt(d2);
        const f = (3400 * alpha) / d2;
        const fx = (dx / d) * f, fy = (dy / d) * f;
        // 近距离额外排斥，避免节点叠在一起
        const minD = a.r + b.r + 16;
        if (d < minD) {
          const push = (minD - d) * 0.42 * alpha;
          a.vx -= (dx / d) * push; a.vy -= (dy / d) * push;
          b.vx += (dx / d) * push; b.vy += (dy / d) * push;
        }
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }
    links.forEach(l => {
      const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const target = 104 + (1 - l.w) * 52;
      const f = (d - target) * 0.015 * l.w * alpha;
      const fx = (dx / d) * f, fy = (dy / d) * f;
      l.s.vx += fx; l.s.vy += fy;
      l.t.vx -= fx; l.t.vy -= fy;
    });
    nodes.forEach(n => {
      if (n.fixed) { n.vx = n.vy = 0; return; }
      const anchor = groupAnchors.get(n.ref.group);
      if (anchor) {
        n.vx += (anchor.x - n.x) * 0.0022 * alpha;
        n.vy += (anchor.y - n.y) * 0.0022 * alpha;
      }
      n.vx += (cx - n.x) * k * 1.15;
      n.vy += (cy - n.y) * k * 1.15;
      n.vx *= 0.87; n.vy *= 0.87;
      n.x += n.vx; n.y += n.vy;
    });
    alpha *= 0.994;
  }

  function fitView(pad) {
    if (!nodes.length || W <= 0) return;
    pad = pad || 46;
    const shown = nodes.filter(visibleNode);
    const scope = shown.length ? shown : nodes;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    scope.forEach(n => {
      minX = Math.min(minX, n.x - n.r); maxX = Math.max(maxX, n.x + n.r);
      minY = Math.min(minY, n.y - n.r); maxY = Math.max(maxY, n.y + n.r);
    });

    const w = Math.max(maxX - minX, 1), h = Math.max(maxY - minY, 1);
    const k = Math.max(0.42, Math.min((W - pad * 2) / w, (H - pad * 2) / h, 1.4));
    view.k = k;
    view.x = W / 2 - (minX + maxX) / 2 * k;
    view.y = H / 2 - (minY + maxY) / 2 * k;
  }

  // 力导向天然接近圆形；宽屏下把横向铺开，避免左右两侧大片留白
  function spreadLayoutAspect() {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach(n => {
      minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
    });
    const w = Math.max(maxX - minX, 1), h = Math.max(maxY - minY, 1);
    const target = Math.max(0.9, (W - 80) / Math.max(H - 80, 1));
    const ratio = w / h;
    if (ratio < target) {
      const cx = (minX + maxX) / 2;
      const sx = Math.min(2.8, target / ratio);
      nodes.forEach(n => { n.x = cx + (n.x - cx) * sx; });
    }
  }

  // 人物=圆，势力=圆角方块，器物=菱形，妖兽=三角
  function nodePath(n, rr) {
    const type = n.ref.type;
    ctx.beginPath();
    if (type === 'org') {
      const s = rr * 1.14;
      if (ctx.roundRect) ctx.roundRect(n.x - s, n.y - s, s * 2, s * 2, Math.min(5, rr * 0.36));
      else ctx.rect(n.x - s, n.y - s, s * 2, s * 2);
    } else if (type === 'item') {
      const s = rr * 1.02;
      ctx.moveTo(n.x, n.y - s); ctx.lineTo(n.x + s, n.y);
      ctx.lineTo(n.x, n.y + s); ctx.lineTo(n.x - s, n.y);
      ctx.closePath();
    } else if (type === 'creature') {
      const s = rr * 1.2;
      ctx.moveTo(n.x, n.y - s);
      ctx.lineTo(n.x + s * 0.94, n.y + s * 0.72);
      ctx.lineTo(n.x - s * 0.94, n.y + s * 0.72);
      ctx.closePath();
    } else {
      ctx.arc(n.x, n.y, rr, 0, Math.PI * 2);
    }
  }

  // 节点内的小类型图标：四类一律绘制；size 给最小可辨尺寸，笔画随节点自适应
  function drawNodeTypeIcon(type, x, y, size) {
    const s = Math.max(size, 6.2);
    ctx.save();
    ctx.translate(x, y);
    // item 节点底色偏浅，金色描边加深一档保证对比；org 用墨青，人物/妖兽用白
    ctx.strokeStyle = type === 'item' ? '#8F6B33' : type === 'org' ? '#3D6B7D' : '#FFFFFF';
    ctx.lineWidth = Math.max(0.85, s * 0.08);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    if (type === 'character') {
      ctx.arc(0, -s * 0.15, s * 0.16, 0, Math.PI * 2);
      ctx.moveTo(-s * 0.32, s * 0.38);
      ctx.quadraticCurveTo(-s * 0.3, s * 0.03, 0, s * 0.03);
      ctx.quadraticCurveTo(s * 0.3, s * 0.03, s * 0.32, s * 0.38);
    } else if (type === 'org') {
      ctx.moveTo(-s * 0.4, -s * 0.04); ctx.lineTo(0, -s * 0.32); ctx.lineTo(s * 0.4, -s * 0.04);
      ctx.moveTo(-s * 0.3, s * 0.02); ctx.lineTo(-s * 0.3, s * 0.38);
      ctx.moveTo(s * 0.3, s * 0.02); ctx.lineTo(s * 0.3, s * 0.38);
      ctx.moveTo(-s * 0.12, s * 0.38); ctx.lineTo(-s * 0.12, s * 0.16);
      ctx.lineTo(s * 0.12, s * 0.16); ctx.lineTo(s * 0.12, s * 0.38);
      ctx.moveTo(-s * 0.44, s * 0.43); ctx.lineTo(s * 0.44, s * 0.43);
    } else if (type === 'item') {
      ctx.moveTo(-s * 0.25, s * 0.34); ctx.lineTo(s * 0.27, -s * 0.32);
      ctx.lineTo(s * 0.38, -s * 0.1); ctx.lineTo(-s * 0.06, s * 0.4); ctx.closePath();
    } else if (type === 'creature') {
      ctx.moveTo(-s * 0.3, s * 0.02);
      ctx.quadraticCurveTo(-s * 0.44, s * 0.3, -s * 0.14, s * 0.34);
      ctx.lineTo(s * 0.14, s * 0.34);
      ctx.quadraticCurveTo(s * 0.44, s * 0.3, s * 0.3, s * 0.02);
      ctx.moveTo(-s * 0.36, -s * 0.2); ctx.arc(-s * 0.36, -s * 0.2, s * 0.1, 0, Math.PI * 2);
      ctx.moveTo(0, -s * 0.3); ctx.arc(0, -s * 0.3, s * 0.11, 0, Math.PI * 2);
      ctx.moveTo(s * 0.36, -s * 0.2); ctx.arc(s * 0.36, -s * 0.2, s * 0.1, 0, Math.PI * 2);
    }
    ctx.stroke();
    ctx.restore();
  }

  function draw() {
    if (W <= 0) return;
    const now = performance.now();
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.k, view.k);

    const focus = hoverId || selectId;
    const hot = focus ? new Set([focus, ...(adj.get(focus) || [])]) : null;


    links.forEach(l => {
      if (!visibleLink(l)) return;
      const st = REL_STYLE[l.type] || REL_STYLE.social;
      const sameGroup = l.s.ref.group === l.t.ref.group;
      const isHover = l === hoverLink;
      const target = (!focus || (hot.has(l.s.id) && hot.has(l.t.id))) ? 1 : 0;
      l.actT += (target - l.actT) * 0.15;
      ctx.beginPath();
      ctx.strokeStyle = isHover ? st.color : mixHex('#F0ECE2', st.color, l.actT);
      ctx.lineWidth = st.width * (0.7 + 0.3 * l.actT) * (sameGroup ? 1 : 0.78) * (isHover ? 1.9 : 1);
      ctx.globalAlpha = isHover ? 0.96 : (focus ? (0.06 + 0.94 * l.actT) : (sameGroup ? 0.52 : 0.22));
      ctx.setLineDash(st.dash);
      ctx.moveTo(l.s.x, l.s.y);
      ctx.lineTo(l.t.x, l.t.y);
      ctx.stroke();
    });
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    nodes.forEach(n => {
      if (!visibleNode(n)) return;
      const targetDim = (focus && !hot.has(n.id)) ? 1 : 0;
      n.dimT += (targetDim - n.dimT) * 0.16;
      const targetSel = n.id === selectId ? 1 : 0;
      n.selT += (targetSel - n.selT) * 0.18;

      const color = GROUP_COLOR[n.ref.group] || '#999';
      const type = n.ref.type;
      const breathe = 1 + n.selT * (0.055 + 0.022 * Math.sin(now / 320));
      const rr = n.r * breathe * (type === 'org' ? 1.02 : type === 'item' ? 0.88 : type === 'creature' ? 0.98 : 1);
      ctx.globalAlpha = 1 - n.dimT * 0.72;

      // 选中节点外圈呼吸环
      if (n.selT > 0.015) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, rr + 4 + 4 * n.selT, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(43,42,38,${0.16 * n.selT})`;
        ctx.lineWidth = 1.1;
        ctx.stroke();
      }

      if (type === 'org') {
        nodePath(n, rr);
        ctx.fillStyle = mixHex('#FFFFFF', color, 0.2);
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.7;
        ctx.stroke();
      } else if (type === 'item') {
        nodePath(n, rr);
        ctx.fillStyle = mixHex('#FFFFFF', color, 0.5);
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.1;
        ctx.stroke();
      } else {
        nodePath(n, rr);
        ctx.fillStyle = color;
        ctx.fill();
        if (type === 'creature') {
          ctx.strokeStyle = mixHex(color, '#2B2A26', 0.28);
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      // character / org / item / creature 四类一律绘制类型图标，不再按度数分两套阈值
      drawNodeTypeIcon(type, n.x, n.y, Math.max(rr * 0.96, 6.4));

      if (n.selT > 0.05) {
        nodePath(n, rr);
        ctx.lineWidth = 1.4 + 1.1 * n.selT;
        ctx.strokeStyle = `rgba(43,42,38,${0.4 + 0.55 * n.selT})`;
        ctx.stroke();
      } else if (n.id === selectId) {
        nodePath(n, rr);
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = '#2B2A26';
        ctx.stroke();
      }

      if (!targetDim && (type === 'org' || n.d >= 8 || n.selT > 0.2 || view.k > 1.45)) {
        ctx.globalAlpha = (1 - n.dimT) * (0.55 + 0.45 * n.selT);
        ctx.save();
        ctx.translate(n.x, n.y + rr + 11 / Math.max(view.k, 0.5));
        ctx.scale(1 / view.k, 1 / view.k);
        ctx.font = `${n.selT > 0.2 ? '600 ' : ''}10.5px -apple-system, "PingFang SC", sans-serif`;
        ctx.fillStyle = '#2B2A26';
        ctx.textAlign = 'center';
        ctx.fillText(n.name, 0, 0);
        ctx.restore();
      }
    });
    ctx.globalAlpha = 1;

    // 点击/切换节点时的扩散波纹
    for (let i = ripples.length - 1; i >= 0; i--) {
      const r = ripples[i];
      r.t += 0.026;
      if (r.t >= 1) { ripples.splice(i, 1); continue; }
      const n = r.n;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r + 5 + r.t * 34, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(43,42,38,${(1 - r.t) * 0.38})`;
      ctx.lineWidth = 1.4 * (1 - r.t) + 0.4;
      ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    drawRelationLabels(focus, hot);
    drawLinkTooltip();
    ctx.restore();
  }

  function loop() {
    stepCamera(performance.now());
    tick();
    draw();
    requestAnimationFrame(loop);
  }

  function toWorld(px, py) { return { x: (px - view.x) / view.k, y: (py - view.y) / view.k }; }
  function toScreen(n) { return { x: n.x * view.k + view.x, y: n.y * view.k + view.y }; }
  function relLabel(l) { return l.ref.label || REL_CN[l.type] || '关系'; }

  function pickLink(px, py) {
    let best = null, bestD = 5.5;
    links.forEach(l => {
      if (!visibleLink(l)) return;
      const a = toScreen(l.s), b = toScreen(l.t);
      const vx = b.x - a.x, vy = b.y - a.y;
      const len2 = vx * vx + vy * vy || 1;
      const t = Math.max(0, Math.min(1, ((px - a.x) * vx + (py - a.y) * vy) / len2));
      const qx = a.x + vx * t, qy = a.y + vy * t;
      const d = Math.hypot(px - qx, py - qy);
      if (d < bestD) { bestD = d; best = l; }
    });
    return best;
  }
  function pick(px, py) {
    const p = toWorld(px, py);
    let best = null, bestD = Infinity;
    nodes.forEach(n => {
      if (!visibleNode(n)) return;
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < n.r + 6 && d < bestD) { bestD = d; best = n; }
    });
    return best;
  }

  let dragNode = null, panning = false, last = null, moved = false, clickedEmpty = false;

  canvas.addEventListener('mousedown', e => {
    camAnim = null;
    const rect = canvas.getBoundingClientRect();
    const n = pick(e.clientX - rect.left, e.clientY - rect.top);
    moved = false; clickedEmpty = !n;
    if (n) { dragNode = n; n.fixed = true; n._px = e.clientX; n._py = e.clientY; }
    else { panning = true; last = { x: e.clientX, y: e.clientY }; }
    canvas.classList.add('dragging');
  });

  window.addEventListener('mousemove', e => {
    if (e.target !== canvas) { hoverId = null; hoverLink = null; return; }
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    if (dragNode) {
      const p = toWorld(mx, my);
      if (Math.hypot(e.clientX - dragNode._px, e.clientY - dragNode._py) > 3) moved = true;
      dragNode.x = p.x; dragNode.y = p.y;
      alpha = Math.max(alpha, 0.28);
      return;
    }
    if (panning && last) {
      view.x += e.clientX - last.x; view.y += e.clientY - last.y;
      last = { x: e.clientX, y: e.clientY }; moved = true;
      return;
    }
    if (mx < 0 || my < 0 || mx > W || my > H) { hoverId = null; hoverLink = null; return; }
    const n = pick(mx, my);
    hoverId = n ? n.id : null;
    hoverLink = n ? null : pickLink(mx, my);
    pointer = { x: mx, y: my };
    canvas.style.cursor = (n || hoverLink) ? 'pointer' : 'grab';
  });

  window.addEventListener('mouseup', e => {
    if (dragNode) {
      const n = dragNode;
      const dist = Math.hypot(e.clientX - n._px, e.clientY - n._py);
      if (dist < 6) select(n.id); else n.fixed = false;
    } else if (clickedEmpty && !moved) {
      selectId = null; closePanel();
    }
    dragNode = null; panning = false; last = null; clickedEmpty = false;
    canvas.classList.remove('dragging');
  });

  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    camAnim = null;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const before = toWorld(mx, my);
    view.k = Math.min(3.2, Math.max(0.35, view.k * (e.deltaY < 0 ? 1.1 : 0.9)));
    const after = toWorld(mx, my);
    view.x += (after.x - before.x) * view.k;
    view.y += (after.y - before.y) * view.k;
  }, { passive: false });

  canvas.addEventListener('dblclick', () => {
    nodes.forEach(n => { n.fixed = false; });
    alpha = 0.5;
    setTimeout(fitView, 60);
  });

  /* ================= 详情面板 ================= */
  const panel = document.getElementById('panel');
  const panelBody = document.getElementById('panelBody');

  function closePanel() {
    panel.classList.remove('open');
    selectId = null;
  }
  function animatePanelBody() {
    panelBody.classList.remove('switch-in');
    void panelBody.offsetWidth;
    panelBody.classList.add('switch-in');
  }
  document.getElementById('panelClose').addEventListener('click', closePanel);

  function relColor(t) { return (REL_STYLE[t] || REL_STYLE.social).color; }

  function renderPowerHistory(e) {
    const h = e.power_history || [];
    if (!h.length) return '';
    return `<div class="sec-title" style="margin-top:18px">境界轨迹</div>
      <div class="power-list">
      ${h.map(p => `<div class="power-row">
        <span class="power-ch">第 ${p.ch} 章</span>
        <span><span class="power-realm">${powerFull(p)}</span>
        ${p.note ? `<span class="power-note"> · ${p.note}</span>` : ''}</span>
      </div>`).join('')}
      </div>`;
  }

  function select(id, opts = {}) {
    const rec = allById.get(id);
    if (!rec) return;
    if (rec._kind !== 'entity') { renderLite(rec); return; }
    ensureNodeVisible(id);
    selectId = id;
    const e = rec;
    const neighbors = links.filter(l => l.s.id === id || l.t.id === id)
      .map(l => ({ other: l.s.id === id ? l.t : l.s, rel: l.ref }))
      .sort((a, b) => (b.rel.weight || 0) - (a.rel.weight || 0));

    const power = powerAt(id);
    const myForeshadows = FORESHADOWS.filter(f =>
      (f.content || '').includes(e.name) ||
      (f.note || '').includes(e.name));

    panelBody.innerHTML = `
      <h2 class="ent-name">${entityIcon(e.type, 'entity-icon-lg')}<span>${e.name}</span></h2>
      <div class="ent-meta">
        ${TYPE_NAME[e.type] || ''} · 第 ${e.first_ch} 章登场${e.last_ch ? ` · 第 ${e.last_ch} 章退场` : ''}
        ${power ? ` · 当前 ${powerFull(power)}` : ''}
      </div>
      <div class="chips">
        <span class="chip grp" style="background:${GROUP_COLOR[e.group] || '#999'}">${e.group}</span>
        ${(e.aliases || []).map(a => `<span class="chip">${a}</span>`).join('')}
      </div>
      <p class="ent-desc">${e.desc || ''}</p>
      ${e.attrs ? `<div class="sec-title">档案</div><div class="attrs">${
        Object.entries(e.attrs).map(([k, v]) => `<b>${k}</b> · ${v}`).join('<br>')
      }</div>` : ''}
      ${renderPowerHistory(e)}
      <div class="sec-title" style="margin-top:18px">关系 · ${neighbors.length}</div>
      ${neighbors.map(n => `
        <div class="rel-item" data-goto="${n.other.id}">
          <span class="rel-dot" style="background:${relColor(n.rel.type)}"></span>
          <span class="rel-name">${entityIcon(n.other.ref.type, 'entity-icon-sm')}${n.other.name}</span>
          <span class="rel-label">${n.rel.label || REL_CN[n.rel.type] || ''}</span>
        </div>`).join('')}
      ${myForeshadows.length ? `<div class="sec-title" style="margin-top:18px">相关伏笔</div>` +
        myForeshadows.map(f => `
          <div class="rel-item">
            <span class="rel-dot" style="background:${STATUS_META[fsStatus(f)].color}"></span>
            <span class="rel-name" style="font-size:12px">${f.content}</span>
          </div>`).join('') : ''}
    `;
    panel.classList.add('open');
    animatePanelBody();
    const picked = nodeById.get(id);
    pulseNode(picked);
    if (opts.center && picked) centerOn(picked, true);
    panelBody.querySelectorAll('[data-goto]').forEach(el => {
      el.addEventListener('click', () => {
        const t = el.getAttribute('data-goto');
        select(t, { center: true });
      });
    });
  }

  function renderLite(r) {
    const kindCn = r.type === 'org' ? '势力' : r._kind === 'place' ? '地点' : '设定';
    let extra = '';
    if (r.parent) {
      const p = allById.get(r.parent);
      if (p) extra = `<div class="chips"><span class="chip">上级：${p.name}</span></div>`;
    }
    if (r._kind === 'concept' && r.kind) {
      extra += `<div class="chips"><span class="chip">${
        { worldview: '世界观', golden_finger: '金手指', technique: '功法',
          item_grade: '品阶', organization_rule: '组织规则', prophecy: '预言' }[r.kind] || r.kind
      }</span></div>`;
    }
    const rules = (r.rules && r.rules.length) ? `
      <div class="sec-title" style="margin-top:16px">规则</div>
      <div class="attrs">${r.rules.map(x => '· ' + x).join('<br>')}</div>` : '';
    const limits = (r.limits && r.limits.length) ? `
      <div class="sec-title" style="margin-top:16px">限制 / 代价</div>
      <div class="attrs" style="color:#A6314A">${r.limits.map(x => '· ' + x).join('<br>')}</div>` : '';
    panelBody.innerHTML = `
      <h2 class="ent-name">${r.type ? entityIcon(r.type, 'entity-icon-lg') : ''}<span>${r.name}</span></h2>
      <div class="ent-meta">${r.type ? TYPE_NAME[r.type] : kindCn} · 第 ${r.first_ch || '?'} 章出现</div>
      ${extra}
      <p class="ent-desc">${r.desc || ''}</p>
      ${rules}${limits}
    `;
    panel.classList.add('open');
    animatePanelBody();
  }

  /* ================= 视图切换 ================= */
  const stage = document.getElementById('stage');
  const views = {
    graph: stage,
    wiki: document.getElementById('wiki'),
    geo: document.getElementById('geo'),
    map: document.getElementById('map'),
    power: document.getElementById('power'),
    rhythm: document.getElementById('rhythm'),
    realms: document.getElementById('realms'),
    foreshadow: document.getElementById('foreshadow')
  };
  let curView = 'graph';

  function setView(v) {
    curView = v;
    Object.keys(views).forEach(k => { views[k].hidden = k !== v; });
    document.querySelectorAll('.tab').forEach(t =>
      t.classList.toggle('on', t.dataset.view === v));
    if (v === 'graph') { resize(); alpha = Math.max(alpha, 0.3); }
    if (v === 'geo') renderGeo();
    if (v === 'map') renderMap();
    if (v === 'power') renderPower();
    if (v === 'rhythm') renderRhythm();
    if (v === 'realms') renderRealms();
    if (v === 'foreshadow') renderForeshadow();
  }
  document.querySelectorAll('.tab').forEach(t =>
    t.addEventListener('click', () => setView(t.dataset.view)));

  /* ================= 百科 ================= */
  const WIKI_PAGE_SIZE = 24;
  let wikiCharPage = 0, wikiOtherPage = 0, wikiPlacePage = 0, wikiConceptPage = 0;

  // 分页片段：百科 / 节奏 / 伏笔三处复用，放在模块作用域
  function pagerHTML(total, page, size, attr) {
    const pages = Math.max(1, Math.ceil(total / size));
    if (pages <= 1) return '';
    page = Math.min(Math.max(page, 0), pages - 1);
    let start = Math.max(0, page - 2);
    let end = Math.min(pages, start + 5);
    if (end - start < 5) start = Math.max(0, end - 5);
    let nums = '';
    for (let i = start; i < end; i++) {
      nums += `<button data-${attr}="${i}" class="${i === page ? 'on' : ''}">${i + 1}</button>`;
    }
    return `<div class="pager">
      <button data-${attr}="${page - 1}" ${page === 0 ? 'disabled' : ''}>上一页</button>
      ${start > 0 ? `<button data-${attr}="0">1</button><span>…</span>` : ''}
      ${nums}
      ${end < pages ? `<span>…</span><button data-${attr}="${pages - 1}">${pages}</button>` : ''}
      <button data-${attr}="${page + 1}" ${page >= pages - 1 ? 'disabled' : ''}>下一页</button>
      <span>共 ${total} 条</span>
    </div>`;
  }

  function renderWiki() {

  const WIKI_PAGE_SIZE = 24;
    const scrollTop = views.wiki.scrollTop;
    const chars = D.entities.filter(e => e.type === 'character');
    const others = D.entities.filter(e => e.type !== 'character');
    const charPages = Math.max(1, Math.ceil(chars.length / WIKI_PAGE_SIZE));
    const otherPages = Math.max(1, Math.ceil(others.length / WIKI_PAGE_SIZE));
    const placePages = Math.max(1, Math.ceil(D.places.length / WIKI_PAGE_SIZE));
    const conceptPages = Math.max(1, Math.ceil(D.concepts.length / WIKI_PAGE_SIZE));
    wikiCharPage = Math.min(wikiCharPage, charPages - 1);
    wikiOtherPage = Math.min(wikiOtherPage, otherPages - 1);
    wikiPlacePage = Math.min(wikiPlacePage, placePages - 1);
    wikiConceptPage = Math.min(wikiConceptPage, conceptPages - 1);

    const secs = [
      {
        title: '角色', items: chars.slice(wikiCharPage * WIKI_PAGE_SIZE, (wikiCharPage + 1) * WIKI_PAGE_SIZE),
        total: chars.length, page: wikiCharPage, attr: 'wchar', showType: false
      },
      {
        title: '势力 / 器物 / 妖兽', items: others.slice(wikiOtherPage * WIKI_PAGE_SIZE, (wikiOtherPage + 1) * WIKI_PAGE_SIZE),
        total: others.length, page: wikiOtherPage, attr: 'wother', showType: true
      },
      { title: '境界体系', items: REALMS.map(r => ({ id: r.id, name: r.name, desc: r.desc })), total: REALMS.length, showType: false },
      {
        title: '地点', items: D.places.slice(wikiPlacePage * WIKI_PAGE_SIZE, (wikiPlacePage + 1) * WIKI_PAGE_SIZE),
        total: D.places.length, page: wikiPlacePage, attr: 'wplace', showType: false
      },
      {
        title: '设定', items: D.concepts.slice(wikiConceptPage * WIKI_PAGE_SIZE, (wikiConceptPage + 1) * WIKI_PAGE_SIZE),
        total: D.concepts.length, page: wikiConceptPage, attr: 'wconcept', showType: false
      }
    ].filter(s => s.items.length);

    views.wiki.innerHTML = secs.map(s => `
      <h2>${s.title} <span class="n">${s.total} 条${s.attr ? ` · 第 ${s.page + 1} / ${Math.max(1, Math.ceil(s.total / WIKI_PAGE_SIZE))} 页` : ''}</span></h2>
      <div class="grid">
        ${s.items.map(it => `
          <div class="card" data-id="${it.id}">
            ${s.showType && it.type ? `<div class="card-type">${entityIcon(it.type)}<span>${TYPE_NAME[it.type] || it.type}</span></div>` : ''}
            <div class="n">${!s.showType && it.type ? entityIcon(it.type, 'entity-icon-sm') : ''}${it.name}</div>
            <div class="d">${(it.desc || '').slice(0, 64)}</div>
          </div>`).join('')}
      </div>
      ${s.attr ? pagerHTML(s.total, s.page, WIKI_PAGE_SIZE, s.attr) : ''}`).join('');

    views.wiki.querySelectorAll('[data-wchar]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      wikiCharPage = +b.dataset.wchar;
      renderWiki();
      const h = views.wiki.querySelectorAll('h2')[0];
      if (h) h.scrollIntoView({ block: 'start' });
    }));
    views.wiki.querySelectorAll('[data-wother]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      wikiOtherPage = +b.dataset.wother;
      renderWiki();
      const h = views.wiki.querySelectorAll('h2')[1];
      if (h) h.scrollIntoView({ block: 'start' });
    }));
    views.wiki.querySelectorAll('[data-wplace]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      wikiPlacePage = +b.dataset.wplace;
      renderWiki();
      const h = [...views.wiki.querySelectorAll('h2')].find(x => x.textContent.trim().startsWith('地点'));
      if (h) h.scrollIntoView({ block: 'start' });
    }));
    views.wiki.querySelectorAll('[data-wconcept]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      wikiConceptPage = +b.dataset.wconcept;
      renderWiki();
      const h = [...views.wiki.querySelectorAll('h2')].find(x => x.textContent.trim().startsWith('设定'));
      if (h) h.scrollIntoView({ block: 'start' });
    }));
    views.wiki.querySelectorAll('[data-id]').forEach(c => {
      c.addEventListener('click', () => {
        const id = c.dataset.id;
        const rec = allById.get(id);
        if (rec && rec._kind === 'entity') {
          setView('graph');
          select(id, { center: true });
        } else if (rec && rec._kind === 'place') {
          openPlace(id);
        } else if (rec) {
          renderLite(rec);
        } else {
          const r = REALMS.find(x => x.id === id);
          if (r) renderLite({ _kind: 'concept', name: r.name, desc: r.desc, first_ch: r.first_ch });
        }
      });
    });
    views.wiki.scrollTop = scrollTop;
  }

  /* ================= 地点志 ================= */
  let geoSelected = (placeById.get('p_yueguo') || placeRoots[0] || {}).id || '';
  const geoExpanded = new Set([...placeChildren.keys()]);

  function placeOwnerText(p, short) {
    const info = placeOwnerInfo(p);
    if (info.disputed) return short ? '交界' : info.roots.map(o => o.name).join(' / ');
    if (info.special) return info.special;
    if (!info.roots.length) return '未归属';
    const root = info.roots[0];
    if (info.direct && info.direct.id !== root.id) return short ? info.direct.name : root.name + ' · ' + info.direct.name + '辖';
    return root.name;
  }

  function ownerBadgesHTML(info) {
    let out = info.roots.map(o =>
      `<button class="geo-badge geo-jump" data-org="${o.id}" title="查看势力档案">${escHtml(o.name)}</button>`).join('');
    if (info.disputed) out += `<span class="geo-badge warn">交界 · 双方主张</span>`;
    if (info.special) out += `<span class="geo-badge warn">${escHtml(info.special)}</span>`;
    if (!out) out = `<span class="geo-empty">未标注势力归属</span>`;
    return out;
  }

  function geoRowHTML(p, depth) {
    const kids = placeChildren.get(p.id) || [];
    const st = placeStage(p);
    const info = placeOwnerInfo(p);
    const owner = placeOwnerText(p, true);
    const sel = p.id === geoSelected;
    return `<div class="geo-row${sel ? ' on' : ''}" data-place="${p.id}"
        style="padding-left:${11 + depth * 18}px">
      <button class="geo-toggle${kids.length ? '' : ' leaf'}" data-toggle="${p.id}"
        aria-label="展开或收起">${geoExpanded.has(p.id) ? '−' : '+'}</button>
      <i class="geo-dot" style="background:${st.color}"></i>
      <span class="geo-name" title="${escHtml(p.name)}">${escHtml(p.name)}</span>
      <span class="geo-ch">${p.first_ch ? '第' + p.first_ch + '章' : '—'}</span>
      <span class="geo-owner${info.roots.length || info.special ? ' owned' : ''}"
        title="${escHtml(placeOwnerText(p))}">${escHtml(owner)}</span>
    </div>${geoExpanded.has(p.id) ? kids.map(k => geoRowHTML(k, depth + 1)).join('') : ''}`;
  }

  function geoDetailHTML(p) {
    const st = placeStage(p);
    const depth = placeDepth(p);
    const info = placeOwnerInfo(p);
    const kids = placeChildren.get(p.id) || [];
    const path = placePath(p);
    const first = chapterByCh.get(p.first_ch);
    const matches = CHAPTERS.filter(c =>
      [c.title, c.summary, c.hook].filter(Boolean).join(' ').includes(p.name));
    const evs = [];
    if (first) evs.push({ c: first, tag: '首现' });
    matches.forEach(c => {
      if (c.ch !== (first && first.ch) && evs.length < 5) evs.push({ c, tag: '点名' });
    });

    const people = D.entities.filter(e => e.type === 'character' &&
      ([e.desc, ...(e.aliases || [])].filter(Boolean).join(' ').includes(p.name)));
    const sameGroup = info.roots.length
      ? D.entities.filter(e => e.type === 'character' && info.roots.some(o => e.group === o.group))
        .sort((a, b) => (deg.get(b.id) || 0) - (deg.get(a.id) || 0)).slice(0, 7)
      : [];
    const orgRoots = info.roots.slice(0, 2);
    const seenSib = new Set();
    const allSameOwnerPlaces = orgRoots.length
      ? PLACES.filter(x => {
          if (x.id === p.id) return false;
          const xi = placeOwnerInfo(x);
          if (!xi.roots.some(r => orgRoots.some(o => o.id === r.id))) return false;
          if (seenSib.has(x.id)) return false;
          seenSib.add(x.id);
          return true;
        })
      : [];
    const sameOwnerPlaces = allSameOwnerPlaces.slice(0, 12);

    const attrs = Object.entries(p.attrs || {});
    return `
      <h2 class="geo-detail-title">${escHtml(p.name)}</h2>
      <div class="geo-meta">第 ${p.first_ch || '—'} 章首现 · ${st.label} · 第 ${depth + 1} 层</div>
      <div class="geo-badges">${ownerBadgesHTML(info)}<span class="geo-badge">${kids.length} 个下级地点</span></div>
      <p class="geo-desc">${escHtml(p.desc || '暂无档案描述。')}</p>

      <div class="geo-sec-title">位置档案</div>
      <div class="geo-kv">
        <div class="k">父级路径</div>
        <div class="v">${path.map(x => `<button class="geo-jump" data-jump="${x.id}">${escHtml(x.name)}</button>`).join(' › ') || '—'}</div>
        ${attrs.map(([k, v]) => `<div class="k">${escHtml(k)}</div><div class="v">${escHtml(v)}</div>`).join('')}
      </div>

      <div class="geo-sec-title">子地点</div>
      <div class="geo-chip-row">${kids.length ? kids.map(k =>
        `<button class="geo-chip geo-jump" data-jump="${k.id}">${escHtml(k.name)} <span style="color:#9A9488">第${k.first_ch || '—'}章</span></button>`).join('') :
        '<span class="geo-empty">无下级地点记录</span>'}</div>

      <div class="geo-sec-title">归属与势力档案</div>
      ${orgRoots.length ? orgRoots.map(o => `
        <div class="geo-org-card">
          <b>${escHtml(o.name)}</b>
          <span class="geo-org-desc">${escHtml((o.desc || '暂无势力档案描述。').slice(0, 120))}</span>
          <button class="geo-org-link" data-org="${o.id}">档案</button>
        </div>`).join('') : info.special ? `
        <div class="geo-org-card gap">
          <b>${escHtml(info.special)}</b>
          <span class="geo-org-desc">没有单一势力归属，按原文的共管/公共区域处理；不强行挂到某一方。</span>
        </div>` : `
        <div class="geo-org-card gap">
          <b>数据缺口</b>
          <span class="geo-org-desc">只有行政/地理 parent，没有可核实的势力归属；保留为空，不猜。</span>
        </div>`}
      ${sameOwnerPlaces.length ? `
        <div class="geo-sec-title">同势力其他据点（${allSameOwnerPlaces.length}${allSameOwnerPlaces.length > 12 ? '，显示前 12' : ''}）</div>
        <div class="geo-chip-row">${sameOwnerPlaces.map(x =>
          `<button class="geo-chip geo-jump" data-jump="${x.id}">${escHtml(x.name)} <span style="color:#9A9488">第${x.first_ch || '—'}章</span></button>`).join('')}</div>` : ''}

      <div class="geo-sec-title">章节证据 · 摘要点名</div>
      <div class="geo-evidence">${evs.length ? evs.map(({ c, tag }) => `
        <div class="geo-ev-row" data-ch="${c.ch}">
          <div class="geo-ev-ch">第 ${c.ch} 章<br><span style="color:#B4B2A9">${tag}</span></div>
          <div class="geo-ev-body"><b>${escHtml(c.title)}</b> · ${escHtml((c.summary || '').slice(0, 82))}</div>
        </div>`).join('') : '<div class="geo-empty">章节摘要没有直接点名此地；目前只有首现章记录，没有可附会的事件。</div>'}</div>

      <div class="geo-sec-title">档案关联人物</div>
      <div class="geo-chip-row">${people.length
        ? people.slice(0, 7).map(e => `<button class="geo-chip" data-ent="${e.id}">${entityIcon(e.type, 'entity-icon-sm')}${escHtml(e.name)}</button>`).join('')
        : sameGroup.length
          ? sameGroup.map(e => `<button class="geo-chip" data-ent="${e.id}">${entityIcon(e.type, 'entity-icon-sm')}${escHtml(e.name)}</button>`).join('')
          : '<span class="geo-empty">档案里没有直接提到此地的人物。</span>'}</div>
      <div class="geo-empty" style="margin-top:6px">${people.length
        ? '按人物简介直接提到地名匹配；不等于此人在该地登场。'
        : sameGroup.length
          ? '这里没有直接点名的人物；上面是同势力人物（按档案归属列出，不等于在场）。'
          : ''}</div>

      <div class="geo-empty" style="margin-top:12px">本页只用层级、归属和首现章；数据没有坐标，不虚构方位。</div>
    `;
  }

  function renderGeo() {
    if (!geoSelected || !placeById.has(geoSelected)) geoSelected = (placeById.get('p_yueguo') || placeRoots[0] || {}).id || '';
    const scrollTop = views.geo.scrollTop;
    const p = placeById.get(geoSelected);
    const counts = GEO_STAGES.map(s => ({
      ...s, count: PLACES.filter(x => placeStage(x).label === s.label).length
    }));
    views.geo.innerHTML = `
      <div class="geo-note">
        ${PLACES.length} 个地点按 <b>parent</b> 组成层级容器，按首现章分四个地理阶段。数据只有层级、归属和出现章号，没有坐标；这张页面不画地图，也不猜方位。
      </div>
      <div class="geo-stage-strip">${counts.map(s => `
        <span class="geo-stage-chip"><i style="background:${s.color}"></i><b>${s.label}</b>
          <span>${s.count} 处 · ${s.note}</span></span>`).join('')}</div>
      <div class="geo-layout">
        <div class="geo-tree-panel">
          <div class="geo-tree-head"><b>地点层级树</b><span>${PLACES.length} 个地点 · ${placeRoots.length} 个顶层容器</span></div>
          ${placeRoots.map(p => geoRowHTML(p, 0)).join('')}
        </div>
        <div class="geo-detail">${p ? geoDetailHTML(p) : '<div class="geo-empty">没有地点数据。</div>'}</div>
      </div>
    `;

    views.geo.querySelectorAll('[data-toggle]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      const id = b.dataset.toggle;
      if (geoExpanded.has(id)) geoExpanded.delete(id); else geoExpanded.add(id);
      renderGeo();
    }));
    views.geo.querySelectorAll('[data-place]').forEach(row => row.addEventListener('click', () => {
      geoSelected = row.dataset.place;
      renderGeo();
    }));
    views.geo.querySelectorAll('[data-jump]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      const id = b.dataset.jump;
      if (!placeById.has(id)) return;
      geoSelected = id;
      renderGeo();
      const row = views.geo.querySelector(`[data-place="${id}"]`);
      if (row) row.scrollIntoView({ block: 'center' });
    }));
    views.geo.querySelectorAll('[data-ent]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      setView('graph');
      select(b.dataset.ent, { center: true });
    }));
    views.geo.querySelectorAll('[data-org]').forEach(b => b.addEventListener('click', e => {
      e.stopPropagation();
      const o = byId.get(b.dataset.org);
      if (o) renderLite(o);
    }));
    views.geo.querySelectorAll('[data-ch]').forEach(row => row.addEventListener('click', () => {
      const c = chapterByCh.get(+row.dataset.ch);
      if (c) showChapter(c);
    }));
    views.geo.scrollTop = scrollTop;
  }

  function openPlace(id) {
    if (!placeById.has(id)) return;
    geoSelected = id;
    setView('geo');
  }

  /* ================= 地图视图（M1 拓扑 / M2 证据化示意） ================= */
  // 空间关系可选：缺失或空 list 时 M2 自动回退 M1，不算错误
  const SPATIAL = Array.isArray(D.spatial_relations) ? D.spatial_relations : [];
  const SPATIAL_KIND_CN = {
    direction: '方位', distance: '距离', contain: '包含', adjacent: '相邻',
    portal: '传送', travel_path: '航线/路径', road: '道路', river: '河流',
    separated_by: '相隔', in_between: '介于'
  };
  const CONF_CN = { high: '高置信', medium: '中置信', low: '低置信' };
  const CONF_COLOR = { high: '#5A7A5E', medium: '#B8925A', low: '#9A9488' };
  const M2_KINDS = new Set(['direction', 'distance', 'contain', 'adjacent']);
  // 方向语义统一为「s 位于 t 的该方位」；向量 [x, y]，x 东正、y 南正
  const DIR_VEC = {
    north_of: [0, -1], south_of: [0, 1], west_of: [-1, 0], east_of: [1, 0],
    northeast_of: [1, -1], northwest_of: [-1, -1],
    southeast_of: [1, 1], southwest_of: [-1, 1]
  };

  let mapMode = 'm1';
  let mapLayer = 'all';
  let mapModel = null;
  let mapHoverNode = null, mapHoverEdge = null;
  let mapView = { x: 0, y: 0, k: 1 };
  let mapDragNode = null, mapPanning = false, mapLast = null, mapMoved = false;

  const mapSubtreeCache = new Map();
  function mapSubtree(rootId) {
    if (mapSubtreeCache.has(rootId)) return mapSubtreeCache.get(rootId);
    const out = new Set([rootId]);
    const walk = id => (placeChildren.get(id) || []).forEach(c => { out.add(c.id); walk(c.id); });
    walk(rootId);
    mapSubtreeCache.set(rootId, out);
    return out;
  }
  function mapLayerList() {
    const roots = placeRoots.map(p => ({ id: p.id, name: p.name, count: mapSubtree(p.id).size }));
    roots.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh'));
    return [{ id: 'all', name: '全部', count: PLACES.length }, ...roots];
  }
  function mapRootOf(id) {
    let cur = placeById.get(id), seen = new Set();
    while (cur && cur.parent && placeById.has(cur.parent) && !seen.has(cur.id)) {
      seen.add(cur.id); cur = placeById.get(cur.parent);
    }
    return cur ? cur.id : id;
  }
  const mapRootColor = new Map();
  function mapColorOf(rootId) {
    if (!mapRootColor.has(rootId)) mapRootColor.set(rootId, PALETTE[mapRootColor.size % PALETTE.length]);
    return mapRootColor.get(rootId);
  }
  function mapLayerNodeIds() {
    if (mapLayer === 'all') return new Set(PLACES.map(p => p.id));
    return mapSubtree(mapLayer);
  }
  function mapRelsFor(ids) {
    const m2 = [], aux = [];
    SPATIAL.forEach(r => {
      if (!placeById.has(r.s) || !placeById.has(r.t) || r.s === r.t) return;
      if (!ids.has(r.s) && !ids.has(r.t)) return;
      if (M2_KINDS.has(r.kind)) m2.push(r); else aux.push(r);
    });
    return { m2, aux };
  }

  /* ---------- M1：层级 / 拓扑图 ---------- */
  function buildM1Model(ids, aux) {
    const nodes = [...ids].map(id => {
      const p = placeById.get(id);
      return {
        id, ref: p, name: p.name, kids: (placeChildren.get(id) || []).length,
        ch: p.first_ch || 9999, x: 0, y: 0, r: 7, rootId: mapRootOf(id)
      };
    });
    const byIdM = new Map(nodes.map(n => [n.id, n]));
    const edges = [];
    nodes.forEach(n => {
      (placeChildren.get(n.id) || []).forEach(c => {
        if (byIdM.has(c.id)) edges.push({ s: n.id, t: c.id, kind: 'parent', ref: null });
      });
    });
    aux.forEach(r => {
      if (byIdM.has(r.s) && byIdM.has(r.t)) edges.push({ s: r.s, t: r.t, kind: r.kind, ref: r });
    });

    // 确定性树形布局：叶子按 DFS 顺序排槽位，父节点取孩子中点；坐标只用于避让
    const roots = nodes.filter(n => {
      const p = placeById.get(n.id);
      return !p.parent || !byIdM.has(p.parent);
    });
    let slot = 0;
    const levelH = 76, slotW = 66;
    const assign = (pid, depth) => {
      const n = byIdM.get(pid);
      const kids = (placeChildren.get(pid) || []).filter(c => byIdM.has(c.id));
      if (!kids.length) { n.x = slot * slotW; n.y = depth * levelH; slot++; return; }
      kids.forEach(c => assign(c.id, depth + 1));
      const xs = kids.map(c => byIdM.get(c.id).x);
      n.x = (Math.min(...xs) + Math.max(...xs)) / 2;
      n.y = depth * levelH;
    };
    roots.forEach(r => assign(r.id, 0));
    nodes.forEach(n => { n.r = 6.5 + Math.min(n.kids, 8) * 1.1; });
    return { nodes, edges, unknown: [], sat: null, fallback: null };
  }

  /* ---------- M2：证据化示意地图 ---------- */
  function buildM2Model(ids) {
    const { m2 } = mapRelsFor(ids);
    const nodeIds = new Set(ids);
    m2.forEach(r => { nodeIds.add(r.s); nodeIds.add(r.t); });

    const dirRels = m2.filter(r => r.kind === 'direction');
    const distRels = m2.filter(r => r.kind === 'distance');
    const evidenceN = dirRels.length + distRels.length;
    // 层内方向/距离约束不足 3 条：不画任何坐标，回退 M1
    if (evidenceN < 3) {
      return {
        nodes: [], edges: [], unknown: [], sat: null,
        fallback: { reason: `该层方位证据不足（${evidenceN} 条方向/距离约束），已回退到 M1 拓扑图` }
      };
    }

    const nodes = [...nodeIds].map(id => {
      const p = placeById.get(id);
      return {
        id, ref: p, name: p.name, kids: (placeChildren.get(id) || []).length,
        x: 50, y: 50, r: 7, unknown: false, inLayer: ids.has(id), rootId: mapRootOf(id)
      };
    });
    const byIdM = new Map(nodes.map(n => [n.id, n]));
    const hasDir = new Set(), hasDist = new Set();
    m2.forEach(r => {
      if (r.kind === 'direction') { hasDir.add(r.s); hasDir.add(r.t); }
      if (r.kind === 'distance') { hasDist.add(r.s); hasDist.add(r.t); }
    });
    // 没有任何 direction / distance 证据的节点一律进方位未知区，绝不落进四象限
    nodes.forEach(n => { n.unknown = !hasDir.has(n.id) && !hasDist.has(n.id); });

    // 确定性初值：黄金角圆周，无随机种子
    const GOLD = Math.PI * (3 - Math.sqrt(5));
    nodes.forEach((n, i) => {
      const a = i * GOLD;
      n.x = 50 + Math.cos(a) * 26;
      n.y = 50 + Math.sin(a) * 26;
    });
    const active = nodes.filter(n => !n.unknown);

    // 轻量约束松弛：固定轮次迭代，结果确定、无漂移
    for (let round = 0; round < 140; round++) {
      m2.forEach(r => {
        if (r.kind !== 'direction') return;
        const a = byIdM.get(r.s), b = byIdM.get(r.t);
        if (!a || !b || a.unknown || b.unknown) return;
        const v = DIR_VEC[r.value];
        if (!v) return;
        a.x += v[0] * 1.6; a.y += v[1] * 1.6;
        b.x -= v[0] * 1.6; b.y -= v[1] * 1.6;
      });
      m2.forEach(r => {
        if (r.kind !== 'contain') return;
        const parent = byIdM.get(r.s), child = byIdM.get(r.t);
        if (!parent || !child || child.unknown) return;
        // contain 只把子节点拉进父节点区域，不锁象限
        child.x += (parent.x - child.x) * 0.12;
        child.y += (parent.y - child.y) * 0.12;
      });
      m2.forEach(r => {
        if (r.kind !== 'adjacent') return;
        const a = byIdM.get(r.s), b = byIdM.get(r.t);
        if (!a || !b || a.unknown || b.unknown) return;
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
        if (d > 22) { a.x += dx / d * 0.5; a.y += dy / d * 0.5; b.x -= dx / d * 0.5; b.y -= dy / d * 0.5; }
      });
      m2.forEach(r => {
        if (r.kind !== 'distance') return;
        const a = byIdM.get(r.s), b = byIdM.get(r.t);
        if (!a || !b || a.unknown || b.unknown) return;
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
        // distance 只作弱分离力，不把「百余里」折算成像素比例
        if (d < 14) { const push = (14 - d) / d * 0.4; a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push; }
      });
      for (let i = 0; i < active.length; i++) for (let j = i + 1; j < active.length; j++) {
        const a = active[i], b = active[j];
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
        if (d < 10) { const push = (10 - d) / d * 0.3; a.x -= dx * push; a.y -= dy * push; b.x += dx * push; b.y += dy * push; }
      }
      active.forEach(n => { n.x = Math.max(6, Math.min(94, n.x)); n.y = Math.max(6, Math.min(94, n.y)); });
    }

    const edges = m2
      .filter(r => byIdM.has(r.s) && byIdM.has(r.t))
      .map(r => ({ s: r.s, t: r.t, kind: r.kind, ref: r }));

    // 约束满足率（按布局后的实际方位核对）
    let dirOk = 0;
    dirRels.forEach(r => {
      const a = byIdM.get(r.s), b = byIdM.get(r.t);
      if (!a || !b || a.unknown || b.unknown) return;
      const v = DIR_VEC[r.value]; if (!v) return;
      let ok = true;
      if (v[0] < 0 && a.x >= b.x) ok = false;
      if (v[0] > 0 && a.x <= b.x) ok = false;
      if (v[1] < 0 && a.y >= b.y) ok = false;
      if (v[1] > 0 && a.y <= b.y) ok = false;
      if (ok) dirOk++;
    });
    let distOk = 0;
    distRels.forEach(r => {
      const a = byIdM.get(r.s), b = byIdM.get(r.t);
      if (!a || !b || a.unknown || b.unknown) return;
      if (Math.hypot(a.x - b.x, a.y - b.y) >= 10) distOk++;
    });
    const containRels = m2.filter(r => r.kind === 'contain');
    let contOk = 0;
    containRels.forEach(r => {
      const p = byIdM.get(r.s), c = byIdM.get(r.t);
      if (!p || !c || c.unknown) return;
      if (Math.hypot(p.x - c.x, p.y - c.y) <= 26) contOk++;
    });

    nodes.forEach(n => { n.r = 7 + Math.min(n.kids, 6) * 0.8; });
    return {
      nodes, edges,
      unknown: nodes.filter(n => n.unknown),
      sat: { direction: `${dirOk}/${dirRels.length}`, distance: `${distOk}/${distRels.length}`, region: `${contOk}/${containRels.length}` },
      fallback: null
    };
  }

  function computeMapModel() {
    const ids = mapLayerNodeIds();
    if (mapMode === 'm2') return buildM2Model(ids);
    const { aux } = mapRelsFor(ids);
    return buildM1Model(ids, aux);
  }

  /* ---------- 画布绘制 ---------- */
  function mapCanvas2d() {
    const canvas = document.getElementById('mapCanvas');
    return canvas ? { canvas, ctx: canvas.getContext('2d') } : null;
  }
  function mapFit() {
    const stage = document.getElementById('mapStage');
    if (!stage || !mapModel || !mapModel.nodes.length) { mapView = { x: 0, y: 0, k: 1 }; return; }
    const rect = stage.getBoundingClientRect();
    const pad = 42;
    let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    mapModel.nodes.forEach(n => {
      if (n.unknown) return;
      minX = Math.min(minX, n.x - n.r); maxX = Math.max(maxX, n.x + n.r);
      minY = Math.min(minY, n.y - n.r); maxY = Math.max(maxY, n.y + n.r);
    });
    const w = Math.max(maxX - minX, 1), h = Math.max(maxY - minY, 1);
    mapView.k = Math.max(0.3, Math.min((rect.width - pad * 2) / w, (rect.height - pad * 2) / h, 1.6));
    mapView.x = rect.width / 2 - (minX + maxX) / 2 * mapView.k;
    mapView.y = rect.height / 2 - (minY + maxY) / 2 * mapView.k;
  }
  function mToScreen(n) { return { x: n.x * mapView.k + mapView.x, y: n.y * mapView.k + mapView.y }; }

  function mapEdgeStyle(edge) {
    if (mapMode === 'm1') {
      if (edge.kind === 'parent') return { color: '#C9C2B2', width: 1.3, dash: [], alpha: 0.85 };
      return { color: '#9A9488', width: 1.1, dash: [5, 4], alpha: 0.75 };
    }
    const conf = (edge.ref && edge.ref.confidence) || 'medium';
    const st = CONF_STYLE_MAP[conf] || CONF_STYLE_MAP.medium;
    return st;
  }
  const CONF_STYLE_MAP = {
    high:   { color: '#6B675E', width: 1.6, dash: [],        alpha: 0.92 },
    medium: { color: '#9A9488', width: 1.2, dash: [6, 4],   alpha: 0.7 },
    low:    { color: '#B4B2A9', width: 1.0, dash: [1.5, 3],  alpha: 0.4 }
  };

  function drawMap() {
    const pack = mapCanvas2d();
    if (!pack || !mapModel) return;
    const { canvas, ctx } = pack;
    const stage = document.getElementById('mapStage');
    const rect = stage.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    if (mapModel.fallback || !mapModel.nodes.length) return;

    // 边
    mapModel.edges.forEach(edge => {
      const a = mapModel.nodes.find(n => n.id === edge.s);
      const b = mapModel.nodes.find(n => n.id === edge.t);
      if (!a || !b) return;
      const sa = mToScreen(a), sb = mToScreen(b);
      const st = mapEdgeStyle(edge);
      const isHover = edge === mapHoverEdge;
      ctx.beginPath();
      ctx.strokeStyle = st.color;
      ctx.lineWidth = st.width * (isHover ? 1.7 : 1);
      ctx.globalAlpha = Math.min(1, st.alpha + (isHover ? 0.25 : 0));
      ctx.setLineDash(st.dash);
      ctx.moveTo(sa.x, sa.y); ctx.lineTo(sb.x, sb.y);
      ctx.stroke();
    });
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // 节点（M2 方位未知节点只进托盘，不画进四象限画布）
    mapModel.nodes.forEach(n => {
      if (n.unknown) return;
      const s = mToScreen(n);
      const color = mapMode === 'm2' && !n.inLayer ? '#9A9488' : mapColorOf(n.rootId);
      ctx.beginPath();
      ctx.arc(s.x, s.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      const hover = n === mapHoverNode;
      const showLabel = hover || (mapMode === 'm1'
        ? (n.kids >= 1 || n.id === mapLayer)
        : (n.inLayer && (n.kids >= 1 || n.id === mapLayer)));
      if (showLabel) {
        ctx.font = `${hover ? '600 ' : ''}10.5px -apple-system, "PingFang SC", sans-serif`;
        ctx.fillStyle = '#2B2A26';
        ctx.textAlign = 'center';
        ctx.fillText(n.name, s.x, s.y + n.r + 13 / Math.max(mapView.k, 0.6));
      }
    });

    // 悬停提示
    if (mapHoverEdge) {
      const r = mapHoverEdge.ref;
      const ch = (r.evidence && r.evidence.ch) || r.first_ch || '—';
      const text = `${SPATIAL_KIND_CN[r.kind] || r.kind} · ${r.value || ''} · 第 ${ch} 章`;
      drawMapTooltip(ctx, text);
    } else if (mapHoverNode) {
      const n = mapHoverNode;
      const extra = mapMode === 'm2'
        ? (n.unknown ? '方位未知（无方向/距离证据）' : '示意坐标（非真实经纬度）')
        : '层级/拓扑位置，仅用于避让';
      drawMapTooltip(ctx, `${n.name} · ${extra}`);
    }
  }

  function drawMapTooltip(ctx, text) {
    const stage = document.getElementById('mapStage');
    if (!stage) return;
    ctx.font = '11px -apple-system, "PingFang SC", sans-serif';
    const tw = ctx.measureText(text).width;
    const bw = tw + 20, bh = 24;
    let left = mapPointer.x + 13, top = mapPointer.y - 32;
    if (left + bw > stage.clientWidth - 6) left = mapPointer.x - bw - 13;
    if (top < 6) top = mapPointer.y + 14;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(left, top, bw, bh, 5);
    else ctx.rect(left, top, bw, bh);
    ctx.fillStyle = 'rgba(255,255,255,0.97)';
    ctx.fill();
    ctx.strokeStyle = '#E3DFD5';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#2B2A26';
    ctx.textAlign = 'left';
    ctx.fillText(text, left + 10, top + 16);
  }

  function mapPickNode(px, py) {
    const p = { x: (px - mapView.x) / mapView.k, y: (py - mapView.y) / mapView.k };
    let best = null, bd = Infinity;
    mapModel.nodes.forEach(n => {
      if (n.unknown) return;
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < n.r + 5 && d < bd) { bd = d; best = n; }
    });
    return best;
  }
  function mapPickEdge(px, py) {
    let best = null, bd = 6;
    mapModel.edges.forEach(e => {
      const a = mapModel.nodes.find(n => n.id === e.s);
      const b = mapModel.nodes.find(n => n.id === e.t);
      if (!a || !b) return;
      const sa = mToScreen(a), sb = mToScreen(b);
      const vx = sb.x - sa.x, vy = sb.y - sa.y;
      const len2 = vx * vx + vy * vy || 1;
      const t = Math.max(0, Math.min(1, ((px - sa.x) * vx + (py - sa.y) * vy) / len2));
      const qx = sa.x + vx * t, qy = sa.y + vy * t;
      const d = Math.hypot(px - qx, py - qy);
      if (d < bd) { bd = d; best = e; }
    });
    return best;
  }

  /* ---------- 点位详情（复用右侧面板，补父级路径/子地点/空间关系） ---------- */
  function openMapPlace(id) {
    const p = placeById.get(id);
    if (!p) return;
    const path = placePath(p);
    const kids = placeChildren.get(id) || [];
    const rels = SPATIAL.filter(r => r.s === id || r.t === id);
    let coordNote = '';
    if (mapMode === 'm2' && mapModel && !mapModel.fallback) {
      const n = mapModel.nodes.find(x => x.id === id);
      if (n) coordNote = n.unknown ? '方位未知（无方向/距离证据）'
        : `示意坐标（非真实经纬度）：(${n.x.toFixed(1)}, ${n.y.toFixed(1)})`;
    }

    const relHTML = rels.length ? rels.map(r => {
      const otherId = r.s === id ? r.t : r.s;
      const other = placeById.get(otherId);
      const ch = (r.evidence && r.evidence.ch) || r.first_ch || '—';
      const quote = (r.evidence && r.evidence.quote) || '';
      return `<div class="rel-item" data-map-goto="${otherId}">
        <span class="rel-dot" style="background:${CONF_COLOR[r.confidence] || '#9A9488'}"></span>
        <span class="rel-name">${other ? escHtml(other.name) : escHtml(otherId)}</span>
        <span class="rel-label">${SPATIAL_KIND_CN[r.kind] || r.kind} · ${escHtml(r.value || '')} · ${CONF_CN[r.confidence] || r.confidence}</span>
      </div>
      <div class="geo-ev-body" style="padding:0 0 6px 22px">第 ${ch} 章 · ${escHtml(quote) || '（无原文摘录）'}</div>`;
    }).join('') : '<div class="geo-empty">没有记录在案的空间关系。</div>';

    panelBody.innerHTML = `
      <h2 class="ent-name"><span>${escHtml(p.name)}</span></h2>
      <div class="ent-meta">地点 · 第 ${p.first_ch || '—'} 章首现${coordNote ? ` · ${escHtml(coordNote)}` : ''}</div>
      <div class="chips">
        <span class="chip">${path.length} 级层级</span>
        <span class="chip">${kids.length} 个下级地点</span>
      </div>
      <p class="ent-desc">${escHtml(p.desc || '暂无档案描述。')}</p>
      <div class="sec-title">父级路径</div>
      <div class="attrs">${path.map(x => `<button class="geo-jump" data-map-goto="${x.id}">${escHtml(x.name)}</button>`).join(' › ') || '—'}</div>
      <div class="sec-title" style="margin-top:14px">子地点</div>
      <div class="geo-chip-row">${kids.length ? kids.map(k =>
        `<button class="geo-chip" data-map-goto="${k.id}">${escHtml(k.name)} <span style="color:#9A9488">第${k.first_ch || '—'}章</span></button>`).join('')
        : '<span class="geo-empty">无下级地点记录</span>'}</div>
      <div class="sec-title" style="margin-top:14px">相关空间关系 · ${rels.length}</div>
      ${relHTML}
    `;
    panel.classList.add('open');
    animatePanelBody();
    panelBody.querySelectorAll('[data-map-goto]').forEach(el => {
      el.addEventListener('click', () => {
        const t = el.getAttribute('data-map-goto');
        if (placeById.has(t)) openMapPlace(t);
        else if (byId.has(t)) select(t, { center: true });
      });
    });
  }

  /* ---------- 渲染 ---------- */
  function renderMap() {
    const wrap = views.map;
    if (!wrap) return;
    const layerOpts = mapLayerList().map(l =>
      `<option value="${l.id}" ${l.id === mapLayer ? 'selected' : ''}>${escHtml(l.name)}（${l.count}）</option>`).join('');
    wrap.innerHTML = `
      <div class="map-wrap">
        <div class="map-toolbar">
          <div class="map-mode">
            <button data-map-mode="m1" class="${mapMode === 'm1' ? 'on' : ''}">M1 层级/拓扑</button>
            <button data-map-mode="m2" class="${mapMode === 'm2' ? 'on' : ''}">M2 示意方位</button>
          </div>
          <select id="mapLayerSel">${layerOpts}</select>
        </div>
        <div class="map-note-bar" id="mapNote"></div>
        <div class="map-stage" id="mapStage">
          <canvas id="mapCanvas" class="map-canvas"></canvas>
          <div class="map-fallback" id="mapFallback" hidden></div>
          <div class="map-legend" id="mapLegend"></div>
        </div>
        <div class="map-tray" id="mapTray" hidden>
          <div class="map-tray-head" id="mapTrayHead"></div>
          <div class="map-chip-row" id="mapTrayBody"></div>
        </div>
        <div class="map-footer" id="mapFooter"></div>
      </div>`;

    wrap.querySelectorAll('[data-map-mode]').forEach(b => b.addEventListener('click', () => {
      mapMode = b.dataset.mapMode;
      renderMap();
    }));
    const sel = document.getElementById('mapLayerSel');
    sel.addEventListener('change', () => { mapLayer = sel.value; renderMap(); });

    mapModel = computeMapModel();
    mapHoverNode = null; mapHoverEdge = null;

    const note = document.getElementById('mapNote');
    const fallback = document.getElementById('mapFallback');
    const legend = document.getElementById('mapLegend');
    const tray = document.getElementById('mapTray');
    const trayHead = document.getElementById('mapTrayHead');
    const trayBody = document.getElementById('mapTrayBody');
    const footer = document.getElementById('mapFooter');

    if (mapModel.fallback) {
      note.textContent = '层级/拓扑关系图 · 节点位置仅用于避让，不代表原文方位';
      fallback.hidden = false;
      fallback.innerHTML = `
        <div class="fb-card">
          <div class="fb-title">M2 证据不足，已回退</div>
          <div class="fb-body">${escHtml(mapModel.fallback.reason)}</div>
          <button id="mapToM1">切到 M1 拓扑图</button>
        </div>`;
      document.getElementById('mapToM1').addEventListener('click', () => { mapMode = 'm1'; renderMap(); });
      legend.innerHTML = '';
      tray.hidden = true;
      footer.innerHTML = '<span>当前层没有可用于二维定位的方向/距离证据；不画假坐标。</span>';
      return;
    }

    if (!mapModel.nodes.length) {
      note.textContent = '层级/拓扑关系图 · 节点位置仅用于避让，不代表原文方位';
      fallback.hidden = false;
      fallback.innerHTML = '<div class="fb-card"><div class="fb-body">本层没有地点数据。</div></div>';
      legend.innerHTML = ''; tray.hidden = true; footer.innerHTML = '';
      return;
    }

    if (mapMode === 'm1') {
      note.textContent = '层级/拓扑关系图 · 节点位置仅用于避让，不代表原文方位';
      legend.innerHTML = `
        <span><i class="lg-line"></i>父子层级</span>
        <span><i class="lg-line dashed"></i>传送 / 航线等辅助边</span>
        <span><i class="dot" style="background:${PALETTE[0]}"></i>按根层着色</span>`;
      footer.innerHTML = '<span>M1 只表达包含、传送、航线等拓扑关系；不画指北针、比例尺、经纬网。</span>';
    } else {
      note.textContent = '示意坐标，非真实经纬度；局部位置不可精确到里';
      legend.innerHTML = `
        <span><i class="lg-line"></i>高置信 · 实线</span>
        <span><i class="lg-line dashed"></i>中置信 · 虚线</span>
        <span><i class="lg-line dotted"></i>低置信 · 点线低透明度</span>
        <span><i class="dot" style="background:#9A9488"></i>层外关联地点</span>`;
      const s = mapModel.sat;
      footer.innerHTML = `<div class="sat">
        <span>方向 ${s.direction}</span><span>距离 ${s.distance}</span><span>区域 ${s.region}</span>
      </div><span>示意坐标，非真实经纬度；局部位置不可精确到里</span>`;
    }

    // 方位未知托盘
    if (mapMode === 'm2' && mapModel.unknown.length) {
      tray.hidden = false;
      trayHead.innerHTML = `<b>方位未知区</b> · ${mapModel.unknown.length} 个节点无方向/距离证据，不进入四象限`;
      trayBody.innerHTML = mapModel.unknown.map(n =>
        `<button class="map-chip" data-map-goto="${n.id}">${escHtml(n.name)}</button>`).join('');
      trayBody.querySelectorAll('[data-map-goto]').forEach(el => {
        el.addEventListener('click', () => openMapPlace(el.dataset.mapGoto));
      });
    } else {
      tray.hidden = true;
    }

    mapBindCanvas();
    mapResize();
  }

  function mapResize() {
    const canvas = document.getElementById('mapCanvas');
    const stage = document.getElementById('mapStage');
    if (!canvas || !stage) return;
    const rect = stage.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    canvas.width = rect.width * DPR;
    canvas.height = rect.height * DPR;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    mapFit();
    drawMap();
  }

  const mapPointer = { x: 0, y: 0 };
  function mapBindCanvas() {
    const canvas = document.getElementById('mapCanvas');
    if (!canvas) return;
    canvas.onmousedown = e => {
      const rect = canvas.getBoundingClientRect();
      const px = e.clientX - rect.left, py = e.clientY - rect.top;
      mapPointer.x = px; mapPointer.y = py;
      const n = mapPickNode(px, py);
      mapMoved = false;
      mapLast = { x: e.clientX, y: e.clientY };
      if (n) { mapDragNode = n; } else { mapPanning = true; }
      canvas.classList.add('dragging');
    };
    window.onmousemove = e => {
      if (curView !== 'map') return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      if (mapDragNode) {
        if (mapLast && Math.hypot(e.clientX - mapLast.x, e.clientY - mapLast.y) > 3) mapMoved = true;
        const p = { x: (mx - mapView.x) / mapView.k, y: (my - mapView.y) / mapView.k };
        mapDragNode.x = p.x; mapDragNode.y = p.y;
        drawMap();
        return;
      }
      if (mapPanning && mapLast) {
        mapView.x += e.clientX - mapLast.x;
        mapView.y += e.clientY - mapLast.y;
        mapLast = { x: e.clientX, y: e.clientY };
        mapMoved = true;
        drawMap();
        return;
      }
      mapPointer.x = mx; mapPointer.y = my;
      mapHoverNode = mapPickNode(mx, my);
      mapHoverEdge = mapHoverNode ? null : mapPickEdge(mx, my);
      canvas.style.cursor = (mapHoverNode || mapHoverEdge) ? 'pointer' : 'grab';
      drawMap();
    };
    window.onmouseup = e => {
      if (mapDragNode) {
        if (!mapMoved) openMapPlace(mapDragNode.id);
      } else if (mapPanning && !mapMoved) {
        // 点空白不做处理
      }
      mapDragNode = null; mapPanning = false; mapLast = null;
      canvas.classList.remove('dragging');
    };
    canvas.onwheel = e => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const before = { x: (mx - mapView.x) / mapView.k, y: (my - mapView.y) / mapView.k };
      mapView.k = Math.min(3, Math.max(0.35, mapView.k * (e.deltaY < 0 ? 1.1 : 0.9)));
      mapView.x = mx - before.x * mapView.k;
      mapView.y = my - before.y * mapView.k;
      drawMap();
    };
  }

  window.addEventListener('resize', () => { if (curView === 'map') mapResize(); });

  /* ================= 势力版图 ================= */
  let powerOnlyOwned = false;

  function powerRowsData() {
    const tops = orgEntities.filter(o => {
      const parent = o.parent ? byId.get(o.parent) : null;
      return !parent || parent.type !== 'org';
    });
    return tops.map(o => {
      const subs = orgEntities.filter(x => x.id !== o.id && orgRootOf(x).id === o.id);
      const places = PLACES.filter(p => placeOwnerInfo(p).roots.some(r => r.id === o.id));
      const conflict = new Set(), alliance = new Set();
      D.relations.forEach(r => {
        if (r.type !== 'conflict' && r.type !== 'alliance') return;
        const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
        if (!so || !to || so.id === to.id) return;
        if (so.id === o.id) (r.type === 'conflict' ? conflict : alliance).add(to.name);
        if (to.id === o.id) (r.type === 'conflict' ? conflict : alliance).add(so.name);
      });
      const firsts = [o.first_ch, ...places.map(p => p.first_ch)].filter(x => typeof x === 'number');
      const first = firsts.length ? Math.min(...firsts) : null;
      return { org: o, subs, places, conflict: [...conflict], alliance: [...alliance], first };
    }).sort((a, b) => b.places.length - a.places.length ||
      (a.first || 9999) - (b.first || 9999) || a.org.name.localeCompare(b.org.name, 'zh'));
  }

  function renderPower() {
    const scrollTop = views.power.scrollTop;
    const rows = powerRowsData();
    const topCount = rows.length;
    const withPlaces = rows.filter(r => r.places.length).length;
    const disputed = PLACES.filter(p => placeOwnerInfo(p).disputed);
    const special = PLACES.filter(p => !placeOwnerInfo(p).roots.length && placeOwnerInfo(p).special);
    const unassigned = PLACES.filter(p => !placeOwnerInfo(p).roots.length && !placeOwnerInfo(p).special);
    const relEdges = D.relations.filter(r => {
      const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
      return so && to && so.id !== to.id && (r.type === 'conflict' || r.type === 'alliance');
    });
    const relPairs = [];
    const seenRel = new Set();
    relEdges.forEach(r => {
      const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
      const key = [r.type, ...[so.id, to.id].sort()].join('|');
      if (seenRel.has(key)) return;
      seenRel.add(key);
      relPairs.push({ type: r.type, a: so.name, b: to.name });
    });
    const visibleRows = powerOnlyOwned ? rows.filter(r => r.places.length) : rows;

    const placeChip = p => {
      const info = placeOwnerInfo(p);
      const direct = info.direct && info.roots[0] && info.direct.id !== info.roots[0].id
        ? ` · ${info.direct.name}辖` : '';
      return `<button class="power-place" data-power-place="${p.id}"
        title="${escHtml(p.desc || '')}">${escHtml(p.name)}<small>第${p.first_ch || '—'}章${escHtml(direct)}${info.disputed ? ' · 交界' : ''}</small></button>`;
    };

    views.power.innerHTML = `
      <div class="power-note">
        据点由 <b>places.attrs 的所属/所属势力/势力/门派</b> 加上 <b>parent 继承</b>得出；交界只在描述明确写「交界」时列双方；没有坐标，不做地图。
      </div>
      <div class="power-metrics">
        <div class="power-metric"><div class="v">${topCount}</div><div class="k">顶层势力</div></div>
        <div class="power-metric"><div class="v">${withPlaces}</div><div class="k">有据点记录</div></div>
        <div class="power-metric"><div class="v">${PLACES.length}</div><div class="k">地点总数</div></div>
        <div class="power-metric"><div class="v" style="color:${unassigned.length ? 'var(--danger)' : 'var(--ink)'}">${unassigned.length}</div><div class="k">未归属地点</div></div>
        <div class="power-metric"><div class="v">${disputed.length + special.length}</div><div class="k">交界/共管</div></div>
        <div class="power-metric"><div class="v">${relPairs.length}</div><div class="k">势力关系边</div></div>
      </div>
      <div class="power-toolbar">
        <span>显示</span>
        <button class="power-filter${powerOnlyOwned ? '' : ' on'}" data-power-scope="all">全部 ${topCount}</button>
        <button class="power-filter${powerOnlyOwned ? ' on' : ''}" data-power-scope="owned">仅有据点 ${withPlaces}</button>
        <span>· 无据点的势力保留为可核查的数据缺口</span>
      </div>
      <div class="power-wrap">
        <table class="power-table">
          <thead><tr><th>势力</th><th>据点</th><th>首现</th><th>档案 / 结局线索</th><th>势力关系</th></tr></thead>
          <tbody>
            ${visibleRows.map(r => `
              <tr class="${r.places.length ? '' : 'power-gap-row'}">
                <td>
                  <button class="power-org" data-power-org="${r.org.id}">${entityIcon(r.org.type, 'entity-icon-sm')}${escHtml(r.org.name)}</button>
                  ${r.subs.length ? `<span class="power-sub">下辖：${r.subs.slice(0, 4).map(x => escHtml(x.name)).join('、')}${r.subs.length > 4 ? '…' : ''}</span>` : ''}
                </td>
                <td><div class="power-places">${r.places.length ? r.places.slice().sort(byFirstCh).map(placeChip).join('') : '<span class="power-gap">未记录据点（数据缺口）</span>'}</div></td>
                <td>${r.first ? '第 ' + r.first + ' 章' : '—'}</td>
                <td><span class="power-status" title="${escHtml(r.org.desc || '')}">${escHtml((r.org.desc || '无档案').slice(0, 88))}</span></td>
                <td><div class="power-rel">
                  ${r.conflict.length ? `<span class="enemy">敌对</span>：${r.conflict.join('、')}` : ''}
                  ${r.conflict.length && r.alliance.length ? '<br>' : ''}
                  ${r.alliance.length ? `<span class="ally">同盟</span>：${r.alliance.join('、')}` : ''}
                  ${!r.conflict.length && !r.alliance.length ? '<span class="power-gap">未见同盟/敌对边</span>' : ''}
                </div></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="power-extra">
        <div class="power-extra-card">
          <h3>交界与共管（不强行归给单方）</h3>
          <div class="chips">${[...disputed, ...special].length ? [...disputed, ...special].map(p => placeChip(p)).join('') : '<span class="power-gap">无</span>'}</div>
          <p>落沙坡按描述列为七玄门/野狼帮交界；血色禁地及其子地点按「七派共管」单列。</p>
        </div>
        <div class="power-extra-card">
          <h3>未归属地点（${unassigned.length}）</h3>
          <div class="chips">${unassigned.length ? unassigned.slice().sort(byFirstCh).map(p => placeChip(p)).join('') : '<span class="power-gap">无</span>'}</div>
          <p>这些地点只有行政/地理 parent，没有可核实的势力归属；保留为数据缺口，不猜。</p>
        </div>
        <div class="power-extra-card">
          <h3>势力关系摘录</h3>
          <div class="chips">${relPairs.length ? relPairs.map(x => `<span class="geo-badge ${x.type === 'conflict' ? '' : ''}" style="border-color:${x.type === 'conflict' ? '#EBC9C4' : '#CFE0D2'};color:${x.type === 'conflict' ? 'var(--danger)' : 'var(--ok)'}">${x.type === 'conflict' ? '敌对' : '同盟'} · ${escHtml(x.a)} ↔ ${escHtml(x.b)}</span>`).join('') : '<span class="power-gap">无</span>'}</div>
          <p>来自 relations 的 alliance / conflict 边；只展示势力顶层，不把人物关系混进来。</p>
        </div>
      </div>
    `;

    views.power.querySelectorAll('[data-power-scope]').forEach(b => b.addEventListener('click', () => {
      powerOnlyOwned = b.dataset.powerScope === 'owned';
      renderPower();
    }));
    views.power.querySelectorAll('[data-power-org]').forEach(b => b.addEventListener('click', () => select(b.dataset.powerOrg)));
    views.power.querySelectorAll('[data-power-place]').forEach(b => b.addEventListener('click', () => openPlace(b.dataset.powerPlace)));
    views.power.scrollTop = scrollTop;
  }


  function svgLine() {
    if (!CHAPTERS.length) return '';
    const W = 860, H = 190, P = 34;
    const minC = CHAPTERS[0].ch, maxC = CURRENT_CH;
    const X = c => P + ((c - minC) / Math.max(maxC - minC, 1)) * (W - P * 2);
    const Y = t => H - P - t * (H - P * 2 - 8);

    let path = '';
    CHAPTERS.forEach((c, i) => {
      path += (i === 0 ? 'M' : 'L') + X(c.ch).toFixed(1) + ' ' + Y(c.tension).toFixed(1) + ' ';
    });
    const area = path + `L${X(CHAPTERS[CHAPTERS.length - 1].ch).toFixed(1)} ${Y(0)} L${X(CHAPTERS[0].ch).toFixed(1)} ${Y(0)} Z`;

    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">
      <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#A6314A" stop-opacity="0.18"/>
        <stop offset="100%" stop-color="#A6314A" stop-opacity="0"/>
      </linearGradient></defs>
      ${[0.25, 0.5, 0.75, 1].map(t => `
        <line x1="${P}" y1="${Y(t)}" x2="${W - P}" y2="${Y(t)}" stroke="#F0ECE2" stroke-width="1"/>
        <text x="${P - 8}" y="${Y(t) + 3}" font-size="9" fill="#B4B2A9" text-anchor="end">${t}</text>`).join('')}
      <path d="${area}" fill="url(#g1)"/>
      <path d="${path}" fill="none" stroke="#A6314A" stroke-width="1.6" stroke-linejoin="round"/>
      ${CHAPTERS.map(c => `
        <circle cx="${X(c.ch).toFixed(1)}" cy="${Y(c.tension).toFixed(1)}" r="3.2"
          fill="${EMOTION_COLOR[c.emotion] || '#B4B2A9'}" stroke="#fff" stroke-width="1.2">
          <title>第${c.ch}章 ${c.title} · 张力${c.tension}</title>
        </circle>`).join('')}
      <text x="${P}" y="${H - 8}" font-size="9" fill="#B4B2A9">第 1 章</text>
      <text x="${W - P}" y="${H - 8}" font-size="9" fill="#B4B2A9" text-anchor="end">第 ${CURRENT_CH} 章</text>
    </svg>`;
  }

  /* ================= 节奏 ================= */
  const CH_PAGE_SIZE = 30;
  let chPage = 0;

  function renderRhythm() {
    const hookRate = CHAPTERS.length ? CHAPTERS.filter(c => c.hook).length / CHAPTERS.length : 0;
    const avgWords = CHAPTERS.length
      ? Math.round(CHAPTERS.reduce((a, c) => a + c.words, 0) / CHAPTERS.length) : 0;
    const shuang = CHAPTERS.filter(c => c.emotion === '爽').map(c => c.ch);
    let gap = '—';
    if (shuang.length > 1) {
      const gs = [];
      for (let i = 1; i < shuang.length; i++) gs.push(shuang[i] - shuang[i - 1]);
      gs.sort((a, b) => a - b);
      gap = gs[Math.floor(gs.length / 2)] + ' 章';
    }
    const isFanqie = (D.meta.platform || '').includes('番茄');
    const hookWarn = isFanqie && hookRate < 0.8;
    const done = (D.meta.coverage && D.meta.coverage.chapters_done) || CHAPTERS.length;
    const sampled = CHAPTERS.length < done;
    const sortedCh = CHAPTERS.slice().sort((a, b) => b.tension - a.tension);
    const chPages = Math.max(1, Math.ceil(sortedCh.length / CH_PAGE_SIZE));
    chPage = Math.min(chPage, chPages - 1);
    const pageCh = sortedCh.slice(chPage * CH_PAGE_SIZE, (chPage + 1) * CH_PAGE_SIZE);

    views.rhythm.innerHTML = `
      ${sampled ? `<div class="sample-note">
        章节数据为抽样（${CHAPTERS.length} / ${done} 章），爽点间隔与钩子率仅供参考；全量分析后指标才准确。
      </div>` : ''}
      <div class="metric-row">
        <div class="metric ${hookWarn ? 'warn' : ''}">
          <div class="k">章末钩子率</div>
          <div class="v">${(hookRate * 100).toFixed(0)}%</div>
          <div class="b">${isFanqie ? '番茄基准 80%' : '起点基准 60%'}</div>
        </div>
        <div class="metric">
          <div class="k">爽点间隔</div>
          <div class="v">${gap}</div>
          <div class="b">${isFanqie ? '番茄基准 3 章' : '起点基准 10 章'}</div>
        </div>
        <div class="metric">
          <div class="k">平均章字数</div>
          <div class="v">${avgWords}</div>
          <div class="b">${isFanqie ? '番茄基准 4000' : '起点基准 6000'}</div>
        </div>
        <div class="metric">
          <div class="k">已分析章节</div>
          <div class="v">${CHAPTERS.length}</div>
          <div class="b">全书 ${D.meta.chapters} 章</div>
        </div>
      </div>

      <h2>张力曲线 <span class="n">每点一章，颜色为情绪</span></h2>
      <div class="rhythm-wrap">${svgLine()}</div>

      <h2>章节明细 <span class="n">按张力排序 · 第 ${chPage + 1} / ${chPages} 页</span></h2>
      <div class="ch-list">
        ${pageCh.map(c => `
          <div class="ch-row" data-ch="${c.ch}">
            <div class="ch-no">第 ${c.ch} 章</div>
            <div>
              <div class="ch-title">${c.title}</div>
              <div class="ch-hook">${c.hook || '无钩子'}</div>
            </div>
            <div class="ch-badge" style="color:${EMOTION_COLOR[c.emotion] || '#888'}">${c.emotion} · ${c.tension}</div>
          </div>`).join('')}
      </div>
      ${pagerHTML(sortedCh.length, chPage, CH_PAGE_SIZE, 'chpage')}
    `;
    views.rhythm.querySelectorAll('[data-ch]').forEach(row => {
      row.addEventListener('click', () => {
        const c = CHAPTERS.find(x => x.ch === +row.dataset.ch);
        if (c) showChapter(c);
      });
    });
    views.rhythm.querySelectorAll('[data-chpage]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      chPage = +b.dataset.chpage;
      renderRhythm();
      const h = [...views.rhythm.querySelectorAll('h2')].find(x => x.textContent.trim().startsWith('章节明细'));
      if (h) h.scrollIntoView({ block: 'start' });
    }));
  }

  function showChapter(c) {
    panelBody.innerHTML = `
      <h2 class="ent-name">第 ${c.ch} 章</h2>
      <div class="ent-meta">${c.title} · ${c.words} 字 · 张力 ${c.tension}</div>
      <div class="chips">
        <span class="chip" style="color:${EMOTION_COLOR[c.emotion] || '#888'}">${c.emotion}</span>
        ${c.hook_type ? `<span class="chip">钩子：${c.hook_type}</span>` : ''}
      </div>
      <p class="ent-desc">${c.summary}</p>
      ${c.hook ? `<div class="sec-title">章末钩子</div><div class="attrs">${c.hook}</div>` : ''}
      ${(c.battles || []).length ? `<div class="sec-title" style="margin-top:16px">战斗</div>
        ${c.battles.map(b => `<div class="attrs">${(byId.get(b.a || b.s) || {}).name || '未知'} vs ${(byId.get(b.b || b.t) || {}).name || '未知'}
          · 境界差 ${b.gap > 0 ? '+' : ''}${b.gap} · ${b.note}</div>`).join('')}` : ''}
    `;
    panel.classList.add('open');
    animatePanelBody();
  }

  /* ================= 境界 ================= */
  function renderRealms() {
    // 主角（关系最多者）置顶，其余按最终修为降序
    const mainId = [...deg.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    const chars = D.entities
      .filter(e => e.type === 'character' && (e.power_history || []).length)
      .sort((a, b) => {
        if (a.id === mainId) return -1;
        if (b.id === mainId) return 1;
        const pa = a.power_history[a.power_history.length - 1];
        const pb = b.power_history[b.power_history.length - 1];
        return levelNum(pb) - levelNum(pa);
      });

    const ladder = REALMS.map((r, i) => {
      const st = r.stages || [];
      const base = REALM_COLOR[Math.min(i, REALM_COLOR.length - 1)];
      const bars = st.length
        ? `<div class="rbar">${st.map((s, j) =>
            `<i style="background:${shade(base, 84 - (st.length > 1 ? j / (st.length - 1) : 0.5) * 38)}" title="${s}"></i>`
          ).join('')}</div>`
        : '';
      const seen = st.length
        ? (D.entities.flatMap(e => e.power_history || []).filter(p => p.realm === r.id).length) : 0;
      return `
      <div class="realm-step" style="background:${shade(base, 92)};border-color:${shade(base, 74)}">
        <div class="rn">${r.name}</div>
        <div class="rs">${st.length ? `${st.length} 个小阶` : '无细分'}${seen ? ` · ${seen} 条记录` : ''}</div>
        ${bars}
      </div>`;
    }).join('');

    const W = 800, P = 4;
    const minC = 1, maxC = CURRENT_CH;
    const X = c => P + ((c - minC) / Math.max(maxC - minC, 1)) * (W - P * 2);

    const rows = chars.map(e => {
      const h = e.power_history;
      const segs = h.map((p, i) => {
        const from = p.ch;
        const to = (i + 1 < h.length) ? h[i + 1].ch : (e.last_ch || CURRENT_CH);
        return `<div class="gantt-seg" data-ent="${e.id}" style="left:${(X(from) / W * 100).toFixed(2)}%;
          width:${Math.max((X(to) - X(from)) / W * 100, 0.8).toFixed(2)}%;
          background:${realmColorOf(p)}" title="${powerFull(p)} · 第${from}章${p.note ? ' · ' + p.note : ''}"></div>`;
      }).join('');
      const latest = h[h.length - 1];
      const isMain = e.id === mainId;
      return `<div class="gantt-row${isMain ? ' main' : ''}">
        <div class="gantt-name" data-ent="${e.id}">${e.name}${isMain ? ' ★' : ''}</div>
        <div class="gantt-track">${segs}</div>
        <div class="gantt-now">${powerFull(latest)}</div>
      </div>`;
    }).join('');

    const battles = [];
    CHAPTERS.forEach(c => (c.battles || []).forEach(b => battles.push(Object.assign({ ch: c.ch }, b))));

    views.realms.innerHTML = `
      <h2>境界阶梯 <span class="n">${REALMS.length} 级</span></h2>
      <div class="realm-ladder">${ladder}</div>

      <h2>各角色境界轨迹 <span class="n">横轴为章号</span></h2>
      <div class="gantt">
        ${rows}
        <div class="gantt-axis" style="margin-left:78px">
          ${[1, 30, 60, 90, CURRENT_CH].map(c => `
            <span class="gantt-tick" style="left:${(X(c) / W * 100).toFixed(2)}%">${c}</span>`).join('')}
        </div>
      </div>

      ${battles.length ? `
      <h2>战斗记录 <span class="n">负值为越级挑战</span></h2>
      ${battles.map(b => {
        const pa = powerAtCh(b.a || b.s, b.ch), pb = powerAtCh(b.b || b.t, b.ch);
        const diff = levelNum(pa) - levelNum(pb);
        return `
        <div class="battle-row">
          <div class="ch-no" style="color:#9A9488">第 ${b.ch} 章</div>
          <div class="battle-vs">
            <span>${(byId.get(b.a || b.s) || {}).name || '未知'} <b>${powerFull(pa)}</b></span>
            <span class="vs">vs</span>
            <span>${(byId.get(b.b || b.t) || {}).name || '未知'} <b>${powerFull(pb)}</b></span>
          </div>
          <div style="color:${diff < 0 ? '#C0392B' : '#5A7A5E'}">
            ${diff < 0 ? `境界差 ${fbLayer(diff)} · 越级` : diff > 0 ? `境界差 +${fbLayer(diff)}` : '同阶'}
          </div>
        </div>`;
      }).join('')}` : ''}
    `;
    views.realms.querySelectorAll('[data-ent]').forEach(el => {
      el.addEventListener('click', () => select(el.dataset.ent));
    });
  }

  /* ================= 伏笔 ================= */
  const FS_PAGE_SIZE = 15;
  let fsPage = 0;
  const chByCh = new Map(CHAPTERS.map(c => [c.ch, c]));

  function fsEvidence(f) {
    if (f.payoff_ch && f.payoff_ch !== f.plant_ch) {
      return {
        label: '回收章（抽取判定）', ch: f.payoff_ch,
        note: '看到第 ' + f.payoff_ch + ' 章有回收记录，正文语义仍需抽样复核'
      };
    }
    if (f.last_mention_ch && f.last_mention_ch !== f.plant_ch) {
      return {
        label: '最后提及 · 仅提及', ch: f.last_mention_ch,
        note: '之后再没出现，只能说明“又被提了一嘴”，不能视为已兑现'
      };
    }
    return { label: '无后续提及', ch: null, note: '埋下后未再出现，仍待回收或已被作者放弃' };
  }

  function fsEvidenceHTML(f) {
    const ev = fsEvidence(f);
    const c = ev.ch ? chByCh.get(ev.ch) : null;
    return `<div class="fs-evidence">
      <b>${ev.label}</b>${ev.ch ? ` · 第 ${ev.ch} 章` : ''}${c ? `《${c.title}》` : ''} · ${ev.note}
      ${c && c.summary ? `<span style="color:#A9A397">｜章节摘要：${c.summary.slice(0, 76)}</span>` : ''}
    </div>`;
  }

  function renderForeshadow() {
    const counts = { overdue: 0, planted: 0, paid: 0, dropped: 0 };
    FORESHADOWS.forEach(f => counts[fsStatus(f)]++);

    const order = { overdue: 0, planted: 1, dropped: 2, paid: 3 };
    const sorted = FORESHADOWS.slice().sort((a, b) =>
      (order[fsStatus(a)] - order[fsStatus(b)]) || (b.importance - a.importance));
    const pages = Math.max(1, Math.ceil(sorted.length / FS_PAGE_SIZE));
    fsPage = Math.min(fsPage, pages - 1);
    const pageRows = sorted.slice(fsPage * FS_PAGE_SIZE, (fsPage + 1) * FS_PAGE_SIZE);

    const maxC = Math.max(CURRENT_CH, ...FORESHADOWS.map(f => f.payoff_ch || 0));

    const doneTotal = (D.meta.coverage && D.meta.coverage.chapters_done) || CURRENT_CH;
    const partial = doneTotal < D.meta.chapters;
    views.foreshadow.innerHTML = `
      ${partial ? `<div class="sample-note">
        当前只分析了全书 ${D.meta.chapters} 章中的前 ${doneTotal} 章。
        「超期」看的是<b>沉默时长</b>：距最后一次提及超过 ${FS_THRESHOLD} 章才会标红
        （阈值 = 已分析 ${doneTotal} 章 × 15%，下限 50）。
        埋得久但一直在提的主线伏笔不算超期；埋下去就再没管过的才会。
        尚未分析的 ${D.meta.chapters - doneTotal} 章里可能已回收一部分，跑完全书结论才准确。
      </div>` : ''}
      <div class="fs-summary">
        <div class="fs-stat alarm">
          <div class="v">${counts.overdue}</div>
          <div class="k">已超期（>${FS_THRESHOLD} 章未收）</div>
        </div>
        <div class="fs-stat"><div class="v">${counts.planted}</div><div class="k">待回收</div></div>
        <div class="fs-stat"><div class="v">${counts.paid}</div><div class="k">有回收章</div></div>
        <div class="fs-stat"><div class="v">${counts.dropped}</div><div class="k">已放弃</div></div>
      </div>
      <div class="fs-meta" style="margin:2px 0 10px">
        判定口径：<b>有回收章</b>只认明确的回收章；只有“再次提及”仍归入待回收/超期，并单列证据；<b>无后续提及</b>表示埋下后再没出现。
      </div>

      <h2>伏笔台账 <span class="n">${sorted.length} 条 · 第 ${fsPage + 1} / ${pages} 页</span></h2>
      ${pageRows.map(f => {
        const st = fsStatus(f);
        const meta = STATUS_META[st];
        const end = f.payoff_ch || CURRENT_CH;
        const leftPct = (f.plant_ch / maxC) * 100;
        const widthPct = Math.max(((end - f.plant_ch) / maxC) * 100, 1);
        const overPct = f.payoff_ch ? 0 : Math.max(((CURRENT_CH - f.plant_ch) / maxC) * 100 - widthPct, 0);
        return `
        <div class="fs-row">
          <div class="fs-head">
            <span class="fs-content">${f.content}</span>
            <span class="fs-badge" style="color:${meta.color};background:${meta.bg}">${meta.cn}</span>
          </div>
          <div class="fs-meta">
            第 ${f.plant_ch} 章埋${f.payoff_ch
              ? ` · 第 ${f.payoff_ch} 章收 · 跨 ${f.payoff_ch - f.plant_ch} 章`
              : ` · 已过 ${CURRENT_CH - f.plant_ch} 章`}${!f.payoff_ch && f.last_mention_ch
              ? ` · 最后提及第 ${f.last_mention_ch} 章（沉默 ${fsSilent(f)} 章）`
              : !f.payoff_ch ? ' · 埋下后再未提及' : ''}
            ${f.thread ? ` · 线索「${f.thread}」` : ''}
          </div>
          ${fsEvidenceHTML(f)}
          <div class="fs-bar">
            <div class="span" style="left:${leftPct}%;width:${widthPct}%;background:${meta.color}"></div>
            ${overPct > 0 && st === 'overdue' ? `<div class="over" style="left:${leftPct + widthPct}%;width:${overPct}%"></div>` : ''}
          </div>
        </div>`;
      }).join('')}
      ${pagerHTML(sorted.length, fsPage, FS_PAGE_SIZE, 'fspage')}
    `;
    views.foreshadow.querySelectorAll('[data-fspage]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      fsPage = +b.dataset.fspage;
      renderForeshadow();
      views.foreshadow.scrollTop = 0;
    }));
  }

  /* ================= 搜索 ================= */
  document.getElementById('search').addEventListener('input', e => {
    const q = e.target.value.trim().toLowerCase();
    if (!q) { hoverId = null; return; }
    const hit = D.entities.find(x =>
      x.name.toLowerCase().includes(q) ||
      (x.aliases || []).some(a => a.toLowerCase().includes(q)));
    if (hit) {
      if (curView !== 'graph') setView('graph');
      select(hit.id, { center: true });
    }
  });

  /* ================= 图例 ================= */
  document.getElementById('legend').innerHTML =
    `<div class="legend-types legend-types-row">
      <span>${entityIcon('character')}人物</span>
      <span>${entityIcon('org')}势力</span>
      <span>${entityIcon('item')}器物</span>
      <span>${entityIcon('creature')}妖兽</span>
    </div>` +
    `<div class="legend-types rel-legend">
      ${Object.keys(REL_STYLE).map(k => {
        const st = REL_STYLE[k];
        const style = st.dash.length ? (st.dash[0] <= 2 ? 'dotted' : 'dashed') : 'solid';
        return `<span><i style="border-top-color:${st.color};border-top-style:${style}"></i>${REL_CN[k]}</span>`;
      }).join('')}
    </div>` +
    [...new Set(D.entities.map(e => e.group))].map(g =>
      `<span><i style="background:${GROUP_COLOR[g] || '#999'}"></i>${g}</span>`).join('') +
    (isolatedCount ? `<span style="color:#9A9488">另有 ${isolatedCount} 个角色无关系连线（见百科）</span>` : '');

  /* ================= 启动 ================= */
  if (location.search.includes('debug=1')) {
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:99;background:#fff;border:1px solid #ccc;padding:6px 10px;font:11px monospace;white-space:pre';
    document.body.appendChild(d);
    setInterval(() => {
      const r = canvas.parentElement.getBoundingClientRect();
      let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
      nodes.forEach(n => { minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x); minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y); });
      d.textContent = `W=${W|0} H=${H|0} dpr=${DPR} parent=${r.width|0}x${r.height|0}\nview k=${view.k.toFixed(3)} x=${view.x|0} y=${view.y|0}\nnodes ${nodes.length} bbox x[${minX|0},${maxX|0}] y[${minY|0},${maxY|0}]\ntranslated center=(${((minX+maxX)/2*view.k+view.x)|0},${((minY+maxY)/2*view.k+view.y)|0})`;
    }, 400);
  }

  window.addEventListener('resize', resize);
  resize();
  updateGraphTools();
  renderWiki();
  requestAnimationFrame(loop);
  for (let i = 0; i < 900; i++) tick();
  spreadLayoutAspect();
  fitView();
  alpha = 0.03;
})();
