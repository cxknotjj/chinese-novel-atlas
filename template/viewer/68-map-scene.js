/* Novel Atlas viewer · 地图场景合成
   职责：drawMap2d 的绘制顺序 / 标签避让 / 悬停提示 */
  function drawMap2d(ctx, rect) {
    const regions = mapModel.regions || [];
    const nodes = mapModel.nodes || [];
    const regionLayerIds = new Set(regions.map(r => r.layer).filter(Boolean));
    const nodesById = new Map(nodes.map(n => [n.id, n]));
    const zoomZ = mapView.fitKx ? (mapView.kx / mapView.fitKx) : 1;
    const markerSizes = {};
    const hideMarker = n => n.rank === 3 && zoomZ < 1.32;

    // 1) 纸底 + 内框
    drawAtlasPaper(ctx, rect);

    // 地图内容统一裁到纸面内框，避免缩放时压到边框
    const framePad = Math.max(10, rect.width * 0.018);
    ctx.save();
    ctx.beginPath();
    ctx.rect(framePad, framePad, rect.width - framePad * 2, rect.height - framePad * 2);
    ctx.clip();

    // 2) 区域：陆地只留极淡水色，海/秘境是可见主体
    regions.filter(r => r.shape === 'land').forEach(r => drawAtlasLand(ctx, r, rect));
    regions.filter(r => r.shape === 'void').forEach(r => drawAtlasVoid(ctx, r, rect));
    regions.filter(r => r.shape === 'sea').forEach(r => drawAtlasSea(ctx, r, rect));

    // 3) 地形：山脊 / 河流 / 湖泊 / 岛链
    drawAtlasTerrain(ctx, rect);

    // 4) 手绘 stamp：地形之外的建筑/植被/云水
    const stampResult = drawAtlasStamps(ctx, rect) || {};
    const stampBoxes = stampResult.boxes || [];

    // 5) 路线：数据点列 → Catmull-Rom 平滑，不用固定 PNG
    const routeLabels = drawAtlasRoutes(ctx, rect);

    // 6) 标签候选：区域 > rank1 > 航路 > rank2 > rank3
    const candidates = [];
    const safePad = framePad + 9;
    const onStage = (x, y, pad = 16) => x >= safePad - pad && x <= rect.width - safePad + pad && y >= safePad - pad && y <= rect.height - safePad + pad;
    const titleBox = atlasTitleBox(ctx, rect);
    const uiBoxes = [{ x: titleBox.x - 10, y: titleBox.y - 10, w: titleBox.w + 20, h: titleBox.h + 20 }];
    if (ATLAS.compass !== false) {
      const comp = Object.assign({ x: 91.5, y: 87.5, size: 7.2 }, ATLAS.compass || {});
      const cs = (comp.size / 100) * rect.width;
      const cx = (comp.x / 100) * rect.width, cy = (comp.y / 100) * rect.height;
      uiBoxes.push({ x: cx - cs / 2 - 6, y: cy - cs / 2 - 6, w: cs + 12, h: cs + 12 });
    }
    const ds = ATLAS.disclaimer || {};
    const dsFs = Math.max(9, Math.min(12, rect.width / 120));
    const dsX = (atlasNum(ds.x, 1.7) / 100) * rect.width, dsY = (atlasNum(ds.y, 95.5) / 100) * rect.height;
    const dsW = (ds.text || '示意舆图 · 方位与比例非精确').length * dsFs * 1.02 + dsFs * 3;
    uiBoxes.push({ x: dsX - 4, y: dsY - dsFs * 1.1, w: dsW + 8, h: dsFs * 2.2 });
    regions.forEach(r => {
      if (!r.name) return;
      const poly = (r.polygon || []).map(atlasWorldScreen);
      if (poly.length < 3) return;
      const minX = Math.min(...poly.map(p => p.x)), maxX = Math.max(...poly.map(p => p.x));
      const minY = Math.min(...poly.map(p => p.y)), maxY = Math.max(...poly.map(p => p.y));
      // 一级地区名必须使用地区实体的原名：不从 layer 名称派生、不补「大陆」、不截括号。
      const regionPlace = r.layer ? nodesById.get(r.layer) : null;
      const text = String((regionPlace && regionPlace.name) || r.name || '').trim();
      if (!text) return;
      const font = Math.max(17, Math.min(30, rect.width * 0.022)) * mapLabelScale();
      const h = font * 1.3;
      const gap = Math.max(6, font * 0.28);
      ctx.save();
      ctx.font = `600 ${font}px "Songti SC","SimSun",serif`;
      const tw = ctx.measureText(text).width + 12;
      ctx.restore();
      const fitsStage = (x, y) => x - tw / 2 >= safePad && x + tw / 2 <= rect.width - safePad &&
        y - h / 2 >= safePad && y + h / 2 <= rect.height - safePad;
      // 区域名固定在区域底边中点附近：先试底边内侧，再退到底边外侧；
      // label_at 只在明确落在区域底边以下时作为手动锚点。
      const padX = (minX + maxX) / 2;
      const insideY = Math.min(Math.max(maxY - h / 2 - gap, minY + h / 2), rect.height - safePad - h / 2);
      const outsideY = maxY + h / 2 + gap;
      const variants = [];
      const at = r.label_at ? atlasWorldScreen(r.label_at) : null;
      if (at && at.y > maxY + gap) variants.push({ x: at.x, y: at.y, seq: 0 });
      else variants.push({ x: padX, y: insideY, seq: 0 });
      variants.push({ x: padX, y: outsideY, seq: 1 });
      if (Math.abs(outsideY - insideY) > h * 0.35) {
        variants.push({ x: padX, y: Math.max(minY + h / 2, insideY - h * 0.55), seq: 2 });
      }
      variants.forEach(v => {
        if (!fitsStage(v.x, v.y)) return;
        candidates.push({
          kind: 'region', text, x: v.x, y: v.y,
          w: tw, h, priority: 0, font, seq: v.seq, regionGroup: r.id
        });
      });
    });

    const visibleNodeCount = nodes.filter(n => !n.unknown).length;
    nodes.forEach(n => {
      if (n.label === false || regionLayerIds.has(n.id)) return;
      if (n.rank === 2 && visibleNodeCount > 26 && zoomZ < 1.12) return;
      if (n.rank === 3 && zoomZ < 1.55) return;
      const s = atlasNodeScreen(n);
      const type = atlasMarkerTypeOf(n);
      const size = type === 'none' ? 10 * mapZoomScale() : atlasMarkerSizeOnScreen(n.rank || 2, rect);
      markerSizes[n.id] = size;
      if (!onStage(s.x, s.y, size)) return;
      const font = (n.rank === 1 ? Math.max(12, Math.min(15, rect.width / 105)) : Math.max(11, Math.min(13, rect.width / 125))) * mapLabelScale();
      ctx.save();
      ctx.font = `${n.rank === 1 ? '600 ' : ''}${font}px -apple-system,"PingFang SC",sans-serif`;
      const tw = ctx.measureText(n.name).width;
      ctx.restore();
      // 文字固定在图标正下方（空间不够才翻到上方），x 与图标中心严格一致；
      // anchorY 记下图标边缘，画一条短连接线，避免看起来像属于旁边的图标。
      let below = true;
      let ly = s.y + size / 2 + font * 1.25;
      if (ly + font > rect.height - 12) { below = false; ly = s.y - size / 2 - font * 1.15; }
      if (ly < framePad + font * 0.9 || ly > rect.height - framePad - font * 0.9) return;
      candidates.push({
        kind: 'node', id: n.id, text: n.name, x: s.x, y: ly,
        anchorY: s.y + (below ? size / 2 : -size / 2),
        w: tw + 10, h: font * 1.35, priority: n.rank === 1 ? 1 : (n.rank === 3 ? 4 : 2),
        font, rank: n.rank
      });
    });
    routeLabels.forEach(l => { if (onStage(l.x, l.y, 12)) candidates.push(l); });

    // 标记 icon 的保留框：文字不得压住别的标记；rank3 在远景不占位；
    // 区域层节点不再画小点，不占标签位置。
    const reserved = nodes.filter(n => !hideMarker(n) && !regionLayerIds.has(n.id) && atlasMarkerTypeOf(n) !== 'none').map(n => {
      const s = atlasNodeScreen(n);
      const size = markerSizes[n.id] || atlasMarkerSizeOnScreen(n.rank || 2, rect);
      return { id: n.id, box: { x: s.x - size / 2 - 2, y: s.y - size / 2 - 2, w: size + 4, h: size + 4 } };
    });
    const obstacles = reserved.concat(stampBoxes.map(box => ({ box })));
    const boxHit = (a, b) => !(a.x + a.w < b.x || a.x > b.x + b.w || a.y + a.h < b.y || a.y > b.y + b.h);

    candidates.sort((a, b) => a.priority - b.priority || (a.seq || 0) - (b.seq || 0) || (a.y - b.y));
    const kept = [], dropped = [], keptRegionGroups = new Set();
    candidates.forEach(c => {
      if (c.regionGroup && keptRegionGroups.has(c.regionGroup)) { dropped.push(c); return; }
      const box = { x: c.x - c.w / 2, y: c.y - c.h / 2, w: c.w, h: c.h };
      const hitLabel = kept.some(k => boxHit(box, k.box));
      const hitMarker = obstacles.some(o => o.id !== c.id && boxHit(box, o.box));
      const hitUI = uiBoxes.some(u => boxHit(box, u));
      if (hitLabel || hitMarker || hitUI) { dropped.push(c); return; }
      kept.push(Object.assign({}, c, { box }));
      if (c.regionGroup) keptRegionGroups.add(c.regionGroup);
    });

    // 7) 区域名
    kept.filter(c => c.kind === 'region').forEach(c => drawAtlasRegionLabel(ctx, c.box, c.text, c.font));

    // 8) 标记：区域层节点已由区域面承载，不再单独画小点
    nodes.forEach(n => {
      if (n.unknown || hideMarker(n) || regionLayerIds.has(n.id)) {
        n._markerR = 0; n._hidden = true; return;
      }
      const s = atlasNodeScreen(n);
      const type = atlasMarkerTypeOf(n);
      n._hidden = type === 'none';
      if (type === 'none') { n._markerR = 0; return; }
      const size = markerSizes[n.id] || atlasMarkerSizeOnScreen(n.rank || 2, rect);
      if (!onStage(s.x, s.y, size)) { n._markerR = 0; n._hidden = true; return; }
      drawAtlasMarker(ctx, type, s.x, s.y, size, n === mapHoverNode || n.id === mapEditSelected);
      n._markerR = Math.max(12, size);
    });

    // 9) 节点名 / 航路名
    kept.filter(c => c.kind === 'node').forEach(c => {
      c.color = c.rank === 1 ? '#2B2A26' : '#4A4234';
      drawAtlasNodeLabel(ctx, c);
    });
    kept.filter(c => c.kind === 'route').forEach(c => {
      ctx.save();
      ctx.font = `${c.font}px -apple-system,"PingFang SC",sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineWidth = Math.max(2, c.font * 0.18);
      ctx.strokeStyle = 'rgba(243,236,221,0.92)';
      ctx.strokeText(c.text, c.x, c.y);
      ctx.fillStyle = c.color;
      ctx.fillText(c.text, c.x, c.y);
      ctx.restore();
    });

    ctx.restore();

    // 10) 固定 UI：题签、印章、罗盘、免责小印
    drawAtlasFixedUI(ctx, rect);

    // 11) 统计与调试
    let overlapPairs = 0;
    for (let i = 0; i < kept.length; i++) for (let j = i + 1; j < kept.length; j++) {
      if (boxHit(kept[i].box, kept[j].box)) overlapPairs++;
    }
    let sx0 = 1e9, sy0 = 1e9, sx1 = -1e9, sy1 = -1e9;
    kept.forEach(b => {
      sx0 = Math.min(sx0, b.box.x); sy0 = Math.min(sy0, b.box.y);
      sx1 = Math.max(sx1, b.box.x + b.box.w); sy1 = Math.max(sy1, b.box.y + b.box.h);
    });
    const useW = rect.width > 0 && sx1 > -1e8 ? +((sx1 - sx0) / rect.width).toFixed(3) : 0;
    const useH = rect.height > 0 && sy1 > -1e8 ? +((sy1 - sy0) / rect.height).toFixed(3) : 0;
    const comp = Object.assign({ x: 91.5, y: 87.5, size: 7.2 }, ATLAS.compass || {});
    const compR = comp.size / 100 * rect.width / 2;
    let compassGap = 1e9;
    nodes.forEach(n => {
      const s = atlasNodeScreen(n);
      const size = markerSizes[n.id] || (atlasMarkerTypeOf(n) === 'none' ? 10 * mapZoomScale() : atlasMarkerSizeOnScreen(n.rank || 2, rect));
      const d = Math.hypot(s.x - comp.x / 100 * rect.width, s.y - comp.y / 100 * rect.height);
      compassGap = Math.min(compassGap, d - compR - size / 2);
    });
    mapModel._stats = {
      overlapPairs,
      textTotal: candidates.length,
      textKept: kept.length,
      textDropped: dropped.length,
      keptLabels: kept.length,
      droppedLabels: dropped.length,
      iconSizes: { marker: markerSizes[nodes[0] && nodes[0].id] || 24, rank1: atlasMarkerSizeOnScreen(1, rect), rank2: atlasMarkerSizeOnScreen(2, rect), rank3: atlasMarkerSizeOnScreen(3, rect) },
      inlineImages: 23,
      atlasRasterCount: 21,
      vectorComponents: 9,
      baseLayout: 'atlas-cover',
      regionVisible: kept.filter(b => b.kind === 'region').length,
      compassBadgeMinGapPx: Math.round(compassGap),
      nodeCount: nodes.length,
      zoomZ: +zoomZ.toFixed(2),
      fitKx: +(mapView.fitKx || 0).toFixed(2),
      kx: +(mapView.kx || 0).toFixed(2),
      screenUse: { w: useW, h: useH },
      canvas: { w: Math.round(rect.width), h: Math.round(rect.height) }
    };
    let statsEl = document.getElementById('mapStats');
    if (!statsEl) {
      statsEl = document.createElement('div');
      statsEl.id = 'mapStats'; statsEl.hidden = true;
      document.body.appendChild(statsEl);
    }
    statsEl.textContent = JSON.stringify(mapModel._stats);

    // 12) 悬停提示
    if (mapHoverEdge) {
      const r = mapHoverEdge.ref;
      const ch = (r.evidence && r.evidence.ch) || r.first_ch || '—';
      drawMapTooltip(ctx, `${SPATIAL_KIND_CN[r.kind] || r.kind} · ${r.value || ''} · 第 ${ch} 章`);
    } else if (mapHoverNode) {
      const n = mapHoverNode;
      const badge = n.evidence ? '有原文方位证据' : '近似摆放';
      drawMapTooltip(ctx, `${n.name} · ${badge}`);
    }
  }
