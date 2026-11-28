/* Novel Atlas viewer · 地图数据模型与视图变换
   职责：M1/M2/2D 模型 / 分层 / 缩放 / drawMap 调度 */
  /* ================= 地图视图（M1 拓扑 / M2 证据化示意） ================= */
  // 空间关系可选：缺失或空 list 时 M2 自动回退 M1，不算错误
  const SPATIAL = Array.isArray(D.spatial_relations) ? D.spatial_relations : [];
  // 示意布局可选：data.map_layout（v2 契约），缺失时 2D 回退拓扑
  const MAP_LAYOUT = (D.map_layout && D.map_layout.mode === 'schematic') ? D.map_layout : null;
  // 有 direction/distance 证据的端点集合（徽标判定）
  const evidenceEndpoints = new Set();
  SPATIAL.forEach(r => {
    if (r.kind === 'direction' || r.kind === 'distance') { evidenceEndpoints.add(r.s); evidenceEndpoints.add(r.t); }
  });
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

  // 三个子视图：map2d 示意 2D（默认）/ m2 证据方位（约束求解，原样保留）/ topo 拓扑树
  let mapMode = 'map2d';
  let mapLayer = null;        // m2 / topo 用：null=默认最大根层；'all'=总览
  let map2dLayer = 'all';
  let mapSlice = 'all';
  let mapModel = null;
  let mapHoverNode = null, mapHoverEdge = null;
  let mapView = { x: 0, y: 0, k: 1 };
  let mapDragNode = null, mapPanning = false, mapLast = null, mapMoved = false, mapPressNode = null;
let mapEditMode = false, mapDirty = false, mapEditSelected = null;

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
  function resolvedMapLayer() {
    if (mapLayer) return mapLayer;
    const list = mapLayerList();
    return list[1] ? list[1].id : 'all';
  }
  function mapLayerNodeIds() {
    const l = resolvedMapLayer();
    if (l === 'all') return new Set(PLACES.map(p => p.id));
    return mapSubtree(l);
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

  function mapTimeSlices() {
    const list = (MAP_LAYOUT && Array.isArray(MAP_LAYOUT.time_slices)) ? MAP_LAYOUT.time_slices : [];
    return list.filter(s => {
      const ch = Number(s.ch || s.first_ch || s.start_ch || 0);
      return ch > 0 && ch <= cutoff;
    });
  }
  function activeMapSlice() {
    if (mapSlice === 'all') return null;
    return mapTimeSlices().find(s => String(s.ch) === String(mapSlice)) || null;
  }
  function map2dRegionOf(placeId) {
    return (MAP_LAYOUT.regions || []).find(r =>
      r.layer && (r.layer === mapRootOf(placeId) || mapSubtree(r.layer).has(placeId)));
  }

  /* ---------- 示意 2D：读 map_layout 的近似布局 ---------- */
  function map2dRegionLayerOf(placeId) {
    const root = mapRootOf(placeId);
    const reg = (MAP_LAYOUT.regions || []).find(r => r.layer && (r.layer === root || mapSubtree(r.layer).has(placeId)));
    return reg ? reg.layer : null;
  }
  function buildMap2dModel() {
    if (!MAP_LAYOUT) {
      return {
        nodes: [], edges: [], regions: [], unknown: [], sat: null, map2d: true,
        fallback: { reason: '未提供示意坐标，已回退拓扑视图' }
      };
    }
    const slice = activeMapSlice();
    const sliceNodes = new Set((slice && slice.nodes) || []);
    const sliceRegions = new Set((slice && slice.regions) || []);
    const sliceRoutes = new Set((slice && slice.routes) || []);
    const sliceFiltered = !!(slice && (sliceNodes.size || sliceRegions.size));
    const rawNodes = (MAP_LAYOUT.nodes || []).filter(n => placeById.has(n.place)).filter(n => {
      if (!sliceFiltered) return true;
      if (sliceNodes.has(n.place)) return true;
      const region = map2dRegionOf(n.place);
      return !!(region && sliceRegions.has(region.id));
    });
    const nodes = rawNodes.map(n => {
      const p = placeById.get(n.place);
      const layer = n.layer || map2dRegionLayerOf(n.place);
      return {
        id: n.place, ref: p, name: p.name, x: n.x, y: n.y,
        rank: n.rank || 2, label: n.label !== false, layer,
        marker: n.marker || null, markerOffset: n.markerOffset,
        rootId: mapRootOf(n.place), kids: (placeChildren.get(n.place) || []).length,
        r: 7, evidence: evidenceEndpoints.has(n.place),
        unknown: false, inLayer: true
      };
    });
    const availLayers = new Set();
    nodes.forEach(n => { if (n.layer) availLayers.add(n.layer); });
    (MAP_LAYOUT.regions || []).forEach(r => { if (r.layer) availLayers.add(r.layer); });
    // 当前选中层在本数据中不存在时，回退「全部」，不得整层隐藏成空
    const layerFilter = (map2dLayer === 'all' || availLayers.has(map2dLayer)) ? map2dLayer : 'all';
    const regions = (MAP_LAYOUT.regions || []).filter(r =>
      (!sliceRegions.size || sliceRegions.has(r.id) || !sliceFiltered) &&
      (layerFilter === 'all' || !r.layer || r.layer === layerFilter));
    const visibleNodes = nodes.filter(n => layerFilter === 'all' || n.layer === layerFilter);
    const visibleIds = new Set(visibleNodes.map(n => n.id));
    const edges = SPATIAL
      .filter(r => visibleIds.has(r.s) && visibleIds.has(r.t))
      .map(r => ({ s: r.s, t: r.t, kind: r.kind, ref: r }));
    const routes = (MAP_LAYOUT.routes || []).filter(r => {
      if (!sliceRoutes.size) return true;
      return sliceRoutes.has(r.id) || (!r.id && visibleIds.has(r.s) && visibleIds.has(r.t));
    });
    return {
      nodes: visibleNodes, edges, regions, unknown: [], sat: null, map2d: true, fallback: null,
      terrain: MAP_LAYOUT.terrain || null, routes
    };
  }

  /* ---------- 拓扑：places.parent 层级树（次要视图，不做美化） ---------- */
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
    if (mapMode === 'map2d') return buildMap2dModel();
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
    if (!stage || !mapModel || (!mapModel.nodes.length && !(mapModel.regions && mapModel.regions.length))) {
      mapView = { x: 0, y: 0, k: 1, kx: 1, ky: 1, fitKx: 1, fitKy: 1 };
      return;
    }
    const rect = stage.getBoundingClientRect();
    const pad = mapModel.map2d ? 26 : 42;
    let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    if (mapModel.regions) {
      mapModel.regions.forEach(reg => (reg.polygon || []).forEach(pt => {
        minX = Math.min(minX, pt[0]); maxX = Math.max(maxX, pt[0]);
        minY = Math.min(minY, pt[1]); maxY = Math.max(maxY, pt[1]);
      }));
    }
    mapModel.nodes.forEach(n => {
      if (n.unknown) return;
      minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
    });
    const w = Math.max(maxX - minX, 1), h = Math.max(maxY - minY, 1);
    if (mapModel.map2d) {
      // 2D 示意：map_layout 的 0–100 直接映射到底图矩形，全出血、不留内边距（内边距只作用于 UI 控件）
      mapView.kx = rect.width / 100;
      mapView.ky = rect.height / 100;
      mapView.k = Math.min(mapView.kx, mapView.ky);
      mapView.x = 0; mapView.y = 0;
      mapView.fitKx = mapView.kx; mapView.fitKy = mapView.ky;
    } else {
      const maxK = 1.6;
      mapView.k = Math.max(0.3, Math.min((rect.width - pad * 2) / w, (rect.height - pad * 2) / h, maxK));
      mapView.kx = mapView.ky = mapView.k;
      mapView.x = rect.width / 2 - (minX + maxX) / 2 * mapView.k;
      mapView.y = rect.height / 2 - (minY + maxY) / 2 * mapView.k;
      mapView.fitKx = mapView.kx; mapView.fitKy = mapView.ky;
    }
  }
  function mapZoomScale() {
    const fit = mapView.fitKx || mapView.kx || 1;
    const now = mapView.kx || mapView.k || 1;
    return Math.max(0.2, Math.min(8, now / fit));
  }
  function syncMapZoomLabel() {
    const el = document.getElementById('mapZoomValue');
    if (!el) return;
    const pct = Math.round(mapZoomScale() * 100);
    el.textContent = pct + '%';
    el.title = `当前缩放 ${pct}% · 点击恢复到 100%`;
  }
  function mapLabelScale() {
    const z = mapZoomScale();
    return z >= 1 ? Math.min(1.8, Math.pow(z, 0.6)) : 1;
  }
  function mToScreen(n) {
    const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
    return { x: n.x * kx + mapView.x, y: n.y * ky + mapView.y };
  }
  /** 地图缩放的唯一入口：倍数作用于「适配比例」，不作用于像素。
      两个坑：
      1. 用绝对像素上限（如 6）会让宽屏上的 fitKx（= width/100）一开局就超过上限，
         滚轮往上反而变小 —— 1900px 宽时最大只能到 6/19 ≈ 32%。
      2. kx/ky 必须乘同一倍数。分别夹取会让一方先触顶，地图宽高比失衡被拉伸。
      (ax, ay) 是缩放锚点（画布坐标），鼠标滚轮传鼠标位置，按钮传画布中心。 */
  function zoomMapBy(f, ax, ay) {
    const kx0 = mapView.kx || mapView.k, ky0 = mapView.ky || mapView.k;
    const fx = mapView.fitKx || kx0, fy = mapView.fitKy || ky0;
    const wx = (ax - mapView.x) / kx0;
    const wy = (ay - mapView.y) / ky0;
    const z = Math.max(0.35, Math.min(6, (kx0 / fx) * f));
    mapView.kx = fx * z;
    mapView.ky = fy * z;
    mapView.k = Math.min(mapView.kx, mapView.ky);
    mapView.x = ax - wx * mapView.kx;
    mapView.y = ay - wy * mapView.ky;
  }

  function zoomBy(f) {
    const stage = document.getElementById('mapStage');
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    zoomMapBy(f, rect.width / 2, rect.height / 2);
    drawMap();
  }

  function mapEdgeStyle(edge) {
    if (mapMode === 'topo') {
      if (edge.kind === 'parent') return { color: '#C9C2B2', width: 1.3, dash: [], alpha: 0.85 };
      return { color: '#9A9488', width: 1.1, dash: [5, 4], alpha: 0.75 };
    }
    if (mapMode === 'map2d') {
      const dashed = ['portal', 'travel_path', 'road', 'river', 'separated_by', 'in_between'].includes(edge.kind);
      return dashed
        ? { color: '#9A9488', width: 1.1, dash: [5, 4], alpha: 0.7 }
        : { color: '#8A8578', width: 1.2, dash: [], alpha: 0.85 };
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
    syncMapZoomLabel();
    const pack = mapCanvas2d();
    if (!pack || !mapModel) return;
    const { canvas, ctx } = pack;
    const stage = document.getElementById('mapStage');
    const rect = stage.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    if (mapModel.fallback) return;
    if (mapModel.map2d) { drawMap2d(ctx, rect); return; }
    if (!mapModel.nodes.length) return;

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
      const showLabel = hover || (mapMode === 'topo'
        ? (n.kids >= 1 || n.id === resolvedMapLayer())
        : (n.inLayer && (n.kids >= 1 || n.id === resolvedMapLayer())));
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

