/* Novel Atlas viewer · 地图交互与编排器
   职责：命中 / 图层 / 时间切片 / 编排面板 / 缩放拖拽 */

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
    if (mapModel.map2d) {
      let best = null, bd = 1e9;
      mapModel.nodes.forEach(n => {
        if (n.unknown || n._hidden || atlasMarkerTypeOf(n) === 'none') return;
        const s = atlasNodeScreen(n);
        const rad = Math.max(12, n._markerR || 12);
        const d = Math.hypot(px - s.x, py - s.y);
        if (d < rad && d < bd) { bd = d; best = n; }
      });
      return best;
    }
    const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
    const p = { x: (px - mapView.x) / kx, y: (py - mapView.y) / ky };
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
    let coordNote = '', badgeNote = '', sourceNote = '层级拓扑，无坐标';
    if (mapMode === 'm2' && mapModel && !mapModel.fallback) {
      const n = mapModel.nodes.find(x => x.id === id);
      if (n) coordNote = n.unknown ? '方位未知（无方向/距离证据）'
        : `示意坐标（非真实经纬度）：(${n.x.toFixed(1)}, ${n.y.toFixed(1)})`;
      sourceNote = '约束求解示意坐标（非真实经纬度）';
    } else if (mapMode === 'map2d' && mapModel && !mapModel.fallback) {
      const n = mapModel.nodes.find(x => x.id === id);
      badgeNote = n ? (n.evidence ? ' · 有原文方位证据' : ' · 近似摆放') : '';
      sourceNote = '示意布局（非经纬度，叙事导航用近似摆放）';
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
      <div class="ent-meta">地点 · 第 ${p.first_ch || '—'} 章首现${coordNote ? ` · ${escHtml(coordNote)}` : ''}${badgeNote}</div>
      <div class="chips">
        <span class="chip">${path.length} 级层级</span>
        <span class="chip">${kids.length} 个下级地点</span>
      </div>
      <div class="sec-title">坐标来源</div>
      <div class="attrs">${escHtml(sourceNote)}</div>
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
  function map2dLayerOptions() {
    if (!MAP_LAYOUT) return [];
    const layers = []; const seen = new Set();
    const push = id => { if (id && !seen.has(id)) { seen.add(id); layers.push(id); } };
    // 先按区域声明顺序，再补节点里出现但区域没列的 layer；不写死任何书的 place id
    (MAP_LAYOUT.regions || []).forEach(r => push(r.layer));
    (MAP_LAYOUT.nodes || []).forEach(n => push(n.layer));
    return layers;
  }
  function mapSelectOptions() {
    const levels = { all: (D._mapLevels || {}).global };
    ((D._mapLevels || {}).layers || []).forEach(l => { levels[l.id] = l.level; });
    if (mapMode === 'map2d') {
      const avail = new Set(map2dLayerOptions());
      const eff = (map2dLayer === 'all' || avail.has(map2dLayer)) ? map2dLayer : 'all';
      const opts = map2dLayerOptions().map(id => [id, (placeById.get(id) || {}).name || id]);
      opts.push(['all', '全部']);
      return opts.map(([v, n]) =>
        `<option value="${v}" ${v === eff ? 'selected' : ''}>${escHtml(n)}${levels[v] ? ` · ${levels[v]}` : ''}</option>`).join('');
    }
    return mapLayerList().map(l =>
      `<option value="${l.id}" ${l.id === resolvedMapLayer() ? 'selected' : ''}>${escHtml(l.name)}（${l.count}）${l.id !== 'all' && levels[l.id] ? ` · ${levels[l.id]}` : ''}</option>`).join('');
  }
  function mapSliceOptions() {
    const slices = mapTimeSlices();
    if (!slices.length) return '';
    const eff = (mapSlice === 'all' || slices.some(s => String(s.ch) === mapSlice)) ? mapSlice : 'all';
    return `<select id="mapSliceSel" title="M4 时态切片"><option value="all" ${eff === 'all' ? 'selected' : ''}>时间切片 · 全部</option>${
      slices.map(s => `<option value="${escHtml(String(s.ch))}" ${eff === String(s.ch) ? 'selected' : ''}>第 ${escHtml(String(s.ch))} 章 · ${escHtml(s.label || '切片')}</option>`).join('')
    }</select>`;
  }
  function mapEditInspectorHtml() {
    if (!mapEditMode || mapMode !== 'map2d' || !MAP_LAYOUT) return '';
    const place = mapEditSelected ? placeById.get(mapEditSelected) : null;
    const src = mapEditSelected
      ? ((MAP_LAYOUT && MAP_LAYOUT.nodes) || []).find(n => n.place === mapEditSelected)
      : null;
    const layers = map2dLayerOptions().map(id => {
      const p = placeById.get(id);
      return `<option value="${escHtml(id)}" ${src && src.layer === id ? 'selected' : ''}>${escHtml(p ? p.name : id)}</option>`;
    }).join('');
    const assets = ATLAS_STAMPS.map(a =>
      `<option value="${escHtml(a.id)}">${escHtml(a.id)} · ${escHtml(a.type)}</option>`).join('');
    return `
      <div class="map-inspector" id="mapInspector" ${place ? '' : 'hidden'}>
        <div class="mi-head"><b>${place ? escHtml(place.name) : '未选中节点'}</b><span>拖拽改坐标</span></div>
        <label>层
          <select id="miLayer" ${place ? '' : 'disabled'}>
            <option value="">（无）</option>${layers}
          </select>
        </label>
        <label>底件
          <select id="miStamp" ${place ? '' : 'disabled'}>${assets}</select>
        </label>
        <button id="miAttach" ${place ? '' : 'disabled'}>挂到节点</button>
        <button id="miRemoveStamp" ${place ? '' : 'disabled'}>移除该节点底件</button>
        <span class="mi-tip">只写导出 JSON，不改 data.json</span>
      </div>`;
  }

  function setMapDirty(v) {
    mapDirty = v;
    const save = document.getElementById('mapEditSave');
    if (save) save.disabled = !v || mapMode !== 'map2d';
  }

  function refreshMapInspector() {
    const host = document.getElementById('mapInspector');
    if (!host) return;
    const html = mapEditInspectorHtml();
    if (!html) { host.hidden = true; return; }
    host.outerHTML = html;
    bindMapInspector();
  }

  function bindMapInspector() {
    const layerSel = document.getElementById('miLayer');
    if (!layerSel) return;
    layerSel.addEventListener('change', () => {
      const src = ((MAP_LAYOUT || {}).nodes || []).find(n => n.place === mapEditSelected);
      if (!src) return;
      src.layer = layerSel.value || null;
      setMapDirty(true);
      mapModel = computeMapModel();
      drawMap();
    });
    const attach = document.getElementById('miAttach');
    if (attach) attach.addEventListener('click', () => {
      const assetId = document.getElementById('miStamp').value;
      const asset = ATLAS_STAMP_BY_ID[assetId];
      if (!asset || !MAP_LAYOUT || !mapEditSelected) return;
      if (!MAP_LAYOUT.atlas) MAP_LAYOUT.atlas = ATLAS;
      if (!ATLAS.stamps) ATLAS.stamps = [];
      const defaults = { terrain: 14, water: 10, architecture: 8, vegetation: 6 };
      ATLAS.stamps.push({
        asset: assetId, attach: mapEditSelected, w: defaults[asset.type] || 8,
        markerOffset: asset.type === 'architecture' ? 2.2 : undefined
      });
      setMapDirty(true);
      drawMap();
    });
    const remove = document.getElementById('miRemoveStamp');
    if (remove) remove.addEventListener('click', () => {
      if (!mapEditSelected) return;
      const keep = (ATLAS.stamps || []).filter(s => s.attach !== mapEditSelected);
      ATLAS.stamps = keep;
      if (MAP_LAYOUT.atlas) MAP_LAYOUT.atlas.stamps = keep;
      setMapDirty(true);
      drawMap();
    });
  }

  function renderMap() {
    const wrap = views.map;
    if (!wrap) return;
    if (mapEditMode && !mapEditSelected && MAP_LAYOUT) {
      const first = (MAP_LAYOUT.nodes || []).find(n => placeById.has(n.place));
      mapEditSelected = first ? first.place : null;
    }
    wrap.innerHTML = `
      <div class="map-wrap">
        <div class="map-toolbar">
          <div class="map-mode">
            <button data-map-mode="map2d" class="${mapMode === 'map2d' ? 'on' : ''}">示意 2D</button>
            <button data-map-mode="m2" class="${mapMode === 'm2' ? 'on' : ''}">证据方位</button>
            <button data-map-mode="topo" class="${mapMode === 'topo' ? 'on' : ''}">拓扑</button>
          </div>
          <select id="mapLayerSel">${mapSelectOptions()}</select>
          ${mapSliceOptions()}
          <div class="map-edit">
            <button id="mapEditToggle" class="${mapEditMode ? 'on' : ''}" ${mapMode === 'map2d' && MAP_LAYOUT ? '' : 'disabled'} title="拖拽节点调整示意位置">编排</button>
            <button id="mapEditSave" ${mapDirty && mapMode === 'map2d' ? '' : 'disabled'} title="导出带节点坐标的 map_layout JSON">导出</button>
            <button id="mapEditReset" title="放弃本轮拖动，重新载入页面">重置</button>
          </div>
        </div>
        ${mapEditInspectorHtml()}
        <div class="map-note-bar" id="mapNote"></div>
        <div class="map-stage" id="mapStage">
          <canvas id="mapCanvas" class="map-canvas"></canvas>
          <div class="map-zoom" id="mapZoom">
            <button data-zoom="in" title="放大">＋</button>
            <button data-zoom="out" title="缩小">－</button>
            <button data-zoom="reset" title="适配画布">复位</button>
            <button data-zoom="one" id="mapZoomValue" class="map-zoom-value" title="当前缩放 · 点击恢复到 100%">100%</button>
            <button data-map-export="png" title="导出当前视图 PNG">PNG</button>
            <button data-map-export="svg" title="导出当前视图 SVG（位图封装，非矢量重绘）">SVG</button>
          </div>
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
      if (mapMode !== 'map2d') mapEditMode = false;
      renderMap();
    }));
    const sel = document.getElementById('mapLayerSel');
    sel.addEventListener('change', () => {
      if (mapMode === 'map2d') map2dLayer = sel.value; else mapLayer = sel.value;
      renderMap();
    });
    const sliceSel = document.getElementById('mapSliceSel');
    if (sliceSel) sliceSel.addEventListener('change', () => {
      mapSlice = sliceSel.value;
      renderMap();
    });
    const editToggle = document.getElementById('mapEditToggle');
    if (editToggle) editToggle.addEventListener('click', () => {
      mapEditMode = !mapEditMode;
      if (!mapEditMode) mapEditSelected = null;
      renderMap();
    });
    const editSave = document.getElementById('mapEditSave');
    if (editSave) editSave.addEventListener('click', () => {
      const layout = (D.map_layout || {});
      const payload = {
        schema: 'novel-atlas/map-layout',
        title: D.meta.title,
        exported_at: new Date().toISOString(),
        note: '节点坐标为示意布局；可用 atlas_map.py 导入或人工合并进 data.json 的 map_layout',
        map_layout: {
          nodes: layout.nodes || [],
          regions: layout.regions || [],
          routes: layout.routes || [],
          terrain: layout.terrain || {},
          atlas: layout.atlas || {},
          time_slices: layout.time_slices || []
        }
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${(D.meta.title || 'atlas').replace(/[\\/:*?"<>|]/g, '_')}-map-layout.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      mapDirty = false;
      renderMap();
    });
    const editReset = document.getElementById('mapEditReset');
    if (editReset) editReset.addEventListener('click', () => {
      if (mapDirty && !confirm('放弃本轮拖动并重新载入？')) return;
      location.reload();
    });
    bindMapInspector();
    document.querySelectorAll('[data-zoom]').forEach(b => b.addEventListener('click', () => {
      const act = b.dataset.zoom;
      if (act === 'in') zoomBy(1.25);
      else if (act === 'out') zoomBy(0.8);
      else if (act === 'reset') { mapFit(); drawMap(); }
      else {
        if (mapModel && mapModel.map2d) {
          mapView.kx = mapView.fitKx || mapView.kx;
          mapView.ky = mapView.fitKy || mapView.ky;
          mapView.k = Math.min(mapView.kx, mapView.ky);
          mapView.x = 0; mapView.y = 0;
        } else { mapView.k = 1; mapFit(); }
        drawMap();
      }
    }));

    document.querySelectorAll('[data-map-export]').forEach(b => b.addEventListener('click', () => {
      const c = document.getElementById('mapCanvas');
      if (!c) return;
      const title = (D.meta.title || 'atlas').replace(/[\\/:*?"<>|]/g, '_');
      if (b.dataset.mapExport === 'png') {
        const a = document.createElement('a');
        a.href = c.toDataURL('image/png');
        a.download = `${title}-${mapMode}.png`;
        a.click();
        return;
      }
      const png = c.toDataURL('image/png');
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${c.width}" height="${c.height}" viewBox="0 0 ${c.width} ${c.height}"><image href="${png}" width="${c.width}" height="${c.height}"/></svg>`;
      const blob = new Blob([svg], { type: 'image/svg+xml' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${title}-${mapMode}.svg`;
      a.click();
      URL.revokeObjectURL(a.href);
    }));

    mapModel = computeMapModel();
    if (mapMode === 'map2d' && map2dLayer !== 'all' && !map2dLayerOptions().includes(map2dLayer)) {
      map2dLayer = 'all';
      mapModel = computeMapModel();
    }
    if (mapMode === 'map2d' && mapSlice !== 'all' && !mapTimeSlices().some(s => String(s.ch) === mapSlice)) {
      mapSlice = 'all';
      mapModel = computeMapModel();
    }
    mapHoverNode = null; mapHoverEdge = null;

    const note = document.getElementById('mapNote');
    const fallback = document.getElementById('mapFallback');
    const legend = document.getElementById('mapLegend');
    const tray = document.getElementById('mapTray');
    const trayHead = document.getElementById('mapTrayHead');
    const trayBody = document.getElementById('mapTrayBody');
    const footer = document.getElementById('mapFooter');

    if (mapModel.fallback) {
      const is2d = mapMode === 'map2d';
      note.textContent = is2d
        ? `地图 ${((D._mapLevels || {}).global || 'M1')} · 示意布局，不是精确经纬度；节点位置用于叙事导航`
        : `地图 ${((D._mapLevels || {}).global || 'M1')} · 层级/拓扑关系图 · 节点位置仅用于避让`;
      fallback.hidden = false;
      fallback.innerHTML = `
        <div class="fb-card">
          <div class="fb-title">${is2d ? '未提供示意布局' : '证据不足，已回退'}</div>
          <div class="fb-body">${escHtml(mapModel.fallback.reason)}</div>
          <button id="mapFallbackBtn">切到拓扑</button>
        </div>`;
      document.getElementById('mapFallbackBtn').addEventListener('click', () => { mapMode = 'topo'; renderMap(); });
      legend.innerHTML = '';
      tray.hidden = true;
      footer.innerHTML = '<span>当前没有可用于二维定位的坐标证据；不画假坐标。</span>';
      return;
    }

    if (!mapModel.nodes.length && !(mapModel.regions && mapModel.regions.length)) {
      note.textContent = mapMode === 'map2d'
        ? '示意布局，不是精确经纬度；当前进度下没有可见地点'
        : '层级/拓扑关系图 · 当前进度下没有可见地点';
      fallback.hidden = false;
      fallback.innerHTML = '<div class="fb-card"><div class="fb-body">本层没有地点数据。</div></div>';
      legend.innerHTML = ''; tray.hidden = true; footer.innerHTML = '';
      return;
    }

    if (mapMode === 'map2d') {
      const ml = D._mapLevels || {};
      const layer = (ml.layers || []).find(x => x.id === map2dLayer);
      const slice = activeMapSlice();
      note.textContent = `地图 ${ml.global || 'M1'}${layer ? ` · ${layer.name} ${layer.level}` : ''}${slice ? ` · ${slice.label || '时态切片'}（第 ${slice.ch} 章）` : ''} · 示意布局，不是精确经纬度；节点位置用于叙事导航${mapEditMode ? ' · 编排模式：拖拽节点后导出 JSON' : ''}`;
      // 图例直接画在 canvas 上（见 drawMap2dLegend），DOM 图例留空并隐藏，避免空纸卡残留
      legend.innerHTML = '';
      legend.style.display = 'none';
      footer.innerHTML = `<span>滚轮缩放 · 右键/单指拖拽平移 · 点节点看详情${mapEditMode ? ' · 拖拽节点改位置' : ''}</span><span>地图证据等级 ${ml.global || 'M1'} · ${escHtml(ml.reason || '')}</span>`;
    } else if (mapMode === 'topo') {
      note.textContent = '层级/拓扑关系图 · 节点位置仅用于避让，不代表原文方位';
      legend.style.display = '';
      legend.innerHTML = `
        <span><i class="lg-line"></i>父子层级</span>
        <span><i class="lg-line dashed"></i>传送 / 航线等辅助边</span>
        <span><i class="dot" style="background:${PALETTE[0]}"></i>按根层着色</span>`;
      footer.innerHTML = '<span>拓扑只表达包含、传送、航线等层级关系；不画指北针、比例尺、经纬网。</span>';
    } else {
      note.textContent = '示意坐标，非真实经纬度；局部位置不可精确到里';
      legend.style.display = '';
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
    mapResize(false);
  }

  function mapResize(preserveView) {
    const canvas = document.getElementById('mapCanvas');
    const stage = document.getElementById('mapStage');
    if (!canvas || !stage) return;
    const rect = stage.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    canvas.width = rect.width * DPR;
    canvas.height = rect.height * DPR;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    const old = preserveView && mapView.vw && mapView.vh
      ? {
        kx: mapView.kx, ky: mapView.ky, x: mapView.x, y: mapView.y,
        fitKx: mapView.fitKx, fitKy: mapView.fitKy, vw: mapView.vw, vh: mapView.vh
      }
      : null;
    mapFit();
    if (old) {
      // 窗口尺寸变化时保留当前缩放层级与画布中心对应的世界坐标
      const zx = old.fitKx ? old.kx / old.fitKx : 1;
      const zy = old.fitKy ? old.ky / old.fitKy : 1;
      mapView.kx = (mapView.fitKx || 1) * zx;
      mapView.ky = (mapView.fitKy || 1) * zy;
      mapView.k = Math.min(mapView.kx, mapView.ky);
      const wx = (old.vw / 2 - old.x) / (old.kx || 1);
      const wy = (old.vh / 2 - old.y) / (old.ky || 1);
      mapView.x = rect.width / 2 - wx * mapView.kx;
      mapView.y = rect.height / 2 - wy * mapView.ky;
    }
    mapView.vw = rect.width;
    mapView.vh = rect.height;
    if (Number.isFinite(bootZoomPending) && bootZoomPending > 0) {
      const z = bootZoomPending;
      bootZoomPending = 0;
      zoomBy(z);
      return;
    }
    drawMap();
  }

  const mapPointer = { x: 0, y: 0 };
  function mapEndDrag(canvas, pointerId, clientX, clientY) {
    canvas.classList.remove('dragging');
    try { canvas.releasePointerCapture(pointerId); } catch (err) { /* 指针已释放 */ }
    if (curView === 'map') {
      const rect = canvas.getBoundingClientRect();
      const mx = clientX - rect.left, my = clientY - rect.top;
      mapHoverNode = mapPickNode(mx, my);
      mapHoverEdge = mapHoverNode ? null : mapPickEdge(mx, my);
      canvas.style.cursor = (mapHoverNode || mapHoverEdge) ? 'pointer' : 'grab';
    }
  }
  function mapBindCanvas() {
    const canvas = document.getElementById('mapCanvas');
    if (!canvas) return;
    canvas.onpointerdown = e => {
      const mouse = e.pointerType === 'mouse';
      // 桌面：右键拖拽平移，和常见地图/图谱操作一致；左键用于点节点或编辑态拖节点。
      // 移动端：单指拖拽平移，轻点节点打开档案。
      if (mouse && e.button !== 0 && e.button !== 2) return;
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const px = e.clientX - rect.left, py = e.clientY - rect.top;
      mapPointer.x = px; mapPointer.y = py;
      const n = mapPickNode(px, py);
      mapPressNode = mouse && e.button === 2 ? null : n;
      mapMoved = false;
      mapLast = { x: e.clientX, y: e.clientY };
      if (mouse && e.button === 2) {
        mapDragNode = null;
        mapPanning = true;
      } else {
        mapDragNode = (mapEditMode && n) ? n : null;
        mapPanning = !mapDragNode;
      }
      canvas.classList.add('dragging');
      try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* 老浏览器忽略 */ }
    };
    canvas.onpointermove = e => {
      if (curView !== 'map') return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      if (mapDragNode) {
        if (!mapEditMode) return;
        if (mapLast && Math.hypot(e.clientX - mapLast.x, e.clientY - mapLast.y) > 3) mapMoved = true;
        const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
        const p = {
          x: (mx - mapView.x) / kx,
          y: (my - mapView.y) / ky - (mapDragNode._markerDy || 0)
        };
        mapDragNode.x = p.x; mapDragNode.y = p.y;
        const src = ((MAP_LAYOUT || {}).nodes || []).find(n => n.place === mapDragNode.id);
        if (src) { src.x = p.x; src.y = p.y; }
        mapDirty = true;
        const saveBtn = document.getElementById('mapEditSave');
        if (saveBtn) saveBtn.disabled = false;
        drawMap();
        return;
      }
      if (mapPanning && mapLast) {
        const dx = e.clientX - mapLast.x, dy = e.clientY - mapLast.y;
        if (!mapMoved && Math.hypot(dx, dy) < 3) return;
        mapMoved = true;
        mapView.x += dx;
        mapView.y += dy;
        mapLast = { x: e.clientX, y: e.clientY };
        mapPointer.x = mx; mapPointer.y = my;
        canvas.style.cursor = 'grabbing';
        drawMap();
        return;
      }
      mapPointer.x = mx; mapPointer.y = my;
      mapHoverNode = mapPickNode(mx, my);
      mapHoverEdge = mapHoverNode ? null : mapPickEdge(mx, my);
      canvas.style.cursor = (mapHoverNode || mapHoverEdge) ? 'pointer' : 'grab';
      drawMap();
    };
    canvas.onpointerup = e => {
      if (mapDragNode) {
        if (mapEditMode) {
          mapEditSelected = mapDragNode.id;
          refreshMapInspector();
          drawMap();
        } else if (!mapMoved) {
          openMapPlace(mapDragNode.id);
        }
      } else if (mapPanning && !mapMoved && mapPressNode) {
        openMapPlace(mapPressNode.id);
      }
      mapDragNode = null; mapPanning = false; mapLast = null; mapPressNode = null;
      mapEndDrag(canvas, e.pointerId, e.clientX, e.clientY);
    };
    canvas.onpointercancel = e => {
      mapDragNode = null; mapPanning = false; mapLast = null; mapPressNode = null;
      mapEndDrag(canvas, e.pointerId, e.clientX, e.clientY);
    };
    canvas.oncontextmenu = e => e.preventDefault();
    canvas.onwheel = e => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const kx0 = mapView.kx || mapView.k, ky0 = mapView.ky || mapView.k;
      const before = { x: (mx - mapView.x) / kx0, y: (my - mapView.y) / ky0 };
      const f = e.deltaY < 0 ? 1.1 : 0.9;
      if (mapModel.map2d) {
        mapView.kx = Math.min(6, Math.max(0.35, kx0 * f));
        mapView.ky = Math.min(6, Math.max(0.35, ky0 * f));
        mapView.k = Math.min(mapView.kx, mapView.ky);
      } else {
        mapView.k = Math.min(3, Math.max(0.35, mapView.k * f));
        mapView.kx = mapView.ky = mapView.k;
      }
      mapView.x = mx - before.x * mapView.kx;
      mapView.y = my - before.y * mapView.ky;
      drawMap();
    };
  }

  window.addEventListener('resize', () => { if (curView === 'map') mapResize(true); });

  // 调试/验收桥：只读暴露模型、统计与画布，不参与界面交互
  window.__atlasMap = {
    getModel: () => mapModel,
    getView: () => ({ ...mapView }),
    stats: () => (mapModel && mapModel._stats) || null,
    canvas: () => document.getElementById('mapCanvas'),
    set2dLayer: l => { map2dLayer = l; renderMap(); },
    setMode: m => { mapMode = m; renderMap(); }
  };

