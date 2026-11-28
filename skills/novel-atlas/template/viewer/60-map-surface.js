/* Novel Atlas viewer · 地图纸面、地形与 stamp
   职责：纸底 / 海陆水洗 / 地形 / 山脊 / 建筑与植被 stamp */
  /* ---------- 示意 2D 绘制 ---------- */
  function worldToScreenPt(pt) {
    const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
    return { x: pt[0] * kx + mapView.x, y: pt[1] * ky + mapView.y };
  }
  // 位图资产：构建时资源占位被替换为 data URI；运行时缓存 Image。
  const mapAssetCache = {};
  function mapAsset(full) {
    if (!mapAssetCache[full]) {
      const img = new Image();
      img.src = full;
      mapAssetCache[full] = img;
    }
    return mapAssetCache[full];
  }
  // cover 铺满：保持比例，允许上下/左右微裁，不变形
  function drawCover(ctx, img, rect) {
    if (!img.complete || !img.naturalWidth) return false;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const scale = Math.max(rect.width / iw, rect.height / ih);
    const w = iw * scale, h = ih * scale;
    ctx.drawImage(img, (rect.width - w) / 2, (rect.height - h) / 2, w, h);
    return true;
  }
  // 把图片 cover 到指定 box（保留 x/y），用于海域纹理，不能复用顶部 0,0 的 drawCover
  function drawBoxCover(ctx, img, box) {
    if (!img.complete || !img.naturalWidth) return false;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const scale = Math.max(box.w / iw, box.h / ih);
    const w = iw * scale, h = ih * scale;
    ctx.drawImage(img, box.x + (box.w - w) / 2, box.y + (box.h - h) / 2, w, h);
    return true;
  }
  // contain 放入给定矩形，保持比例居中
  function drawContain(ctx, img, x, y, w, h) {
    if (!img.complete || !img.naturalWidth) return false;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    const scale = Math.min(w / iw, h / ih);
    const dw = iw * scale, dh = ih * scale;
    ctx.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    return true;
  }
  function drawPolyline(ctx, pts) {
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  }
  function drawArrowhead(ctx, tip, from) {
    const ang = Math.atan2(tip.y - from.y, tip.x - from.x);
    const s = 7, a1 = ang + Math.PI * 0.85, a2 = ang - Math.PI * 0.85;
    ctx.beginPath();
    ctx.moveTo(tip.x, tip.y);
    ctx.lineTo(tip.x + Math.cos(a1) * s, tip.y + Math.sin(a1) * s);
    ctx.moveTo(tip.x, tip.y);
    ctx.lineTo(tip.x + Math.cos(a2) * s, tip.y + Math.sin(a2) * s);
    ctx.strokeStyle = 'rgba(240,235,220,0.85)';
    ctx.lineWidth = 1.1;
    ctx.stroke();
  }
  /* ---------- 示意 2D 绘制：atlas-kit 数据驱动 ---------- */
  // 21 件手绘 PNG 在网页里降为可选 stamp；9 件路线/标记/UI 全部由这里代码绘制。
  // 文字、路线、标记位置都来自 map_layout，不烘焙进图片。
  const ATLAS = (MAP_LAYOUT && MAP_LAYOUT.atlas) || {};
  const ATLAS_THEME = Object.assign({
    ink: '#3B332A', accent: '#A66A45', seal: '#A93828', paper: '#E8DCC5',
    water: '#6E8E96', route: '#8A7254', muted: '#8D8070'
  }, ATLAS.palette || {});

  const ATLAS_STAMPS = [
    { id: 'terrain_far_01', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_far_01.webp' },
    { id: 'terrain_far_02', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_far_02.webp' },
    { id: 'terrain_peak_01', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_peak_01.webp' },
    { id: 'terrain_peak_02', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_peak_02.webp' },
    { id: 'terrain_ridge_01', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_ridge_01.webp' },
    { id: 'terrain_ridge_02', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_ridge_02.webp' },
    { id: 'terrain_slope_01', type: 'terrain', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/terrain_slope_01.webp' },
    { id: 'water_cloud_01', type: 'water', pivot: [0.5, 0.5], src: '__ASSET__:map/atlas/water_cloud_01.webp' },
    { id: 'water_cloud_02', type: 'water', pivot: [0.5, 0.5], src: '__ASSET__:map/atlas/water_cloud_02.webp' },
    { id: 'water_bank_01', type: 'water', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/water_bank_01.webp' },
    { id: 'water_bank_02', type: 'water', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/water_bank_02.webp' },
    { id: 'arch_sect_gate_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_sect_gate_01.webp' },
    { id: 'arch_city_wall_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_city_wall_01.webp' },
    { id: 'arch_pass_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_pass_01.webp' },
    { id: 'arch_cave_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_cave_01.webp' },
    { id: 'arch_village_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_village_01.webp' },
    { id: 'arch_dock_01', type: 'architecture', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/arch_dock_01.webp' },
    { id: 'veg_pine_01', type: 'vegetation', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/veg_pine_01.webp' },
    { id: 'veg_bamboo_01', type: 'vegetation', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/veg_bamboo_01.webp' },
    { id: 'veg_reeds_01', type: 'vegetation', pivot: [0.5, 0.5], src: '__ASSET__:map/atlas/veg_reeds_01.webp' },
    { id: 'veg_dead_tree_01', type: 'vegetation', pivot: [0.5, 0.875], src: '__ASSET__:map/atlas/veg_dead_tree_01.webp' }
  ];
  const ATLAS_STAMP_BY_ID = {};
  ATLAS_STAMPS.forEach(a => { ATLAS_STAMP_BY_ID[a.id] = a; });
  const ATLAS_SUPPORT = {
    paper: '__ASSET__:map/atlas/ui_paper_ornate.webp',
    sea: '__ASSET__:map/atlas/water_sea_01.webp'
  };

  function atlasRgba(hex, alpha) {
    const s = String(hex || '#000').replace('#', '');
    const r = parseInt(s.slice(0, 2), 16), g = parseInt(s.slice(2, 4), 16), b = parseInt(s.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  function atlasNum(v, d) { return typeof v === 'number' && isFinite(v) ? v : d; }
  function atlasPath(ctx, pts) {
    if (!pts || !pts.length) return false;
    ctx.beginPath();
    pts.forEach((p, i) => {
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
    });
    ctx.closePath();
    return true;
  }
  function atlasBBox(pts) {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    (pts || []).forEach(p => {
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x);
      y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    });
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0, x1, y1 };
  }
  function atlasPointInPoly(pt, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1];
      const xj = poly[j][0], yj = poly[j][1];
      if (((yi > pt.y) !== (yj > pt.y)) &&
          pt.x < (xj - xi) * (pt.y - yi) / ((yj - yi) || 1e-9) + xi) inside = !inside;
    }
    return inside;
  }
  function atlasSmoothPoints(pts, steps = 12) {
    if (!pts || pts.length < 3) return pts || [];
    const P = [pts[0], ...pts, pts[pts.length - 1]];
    const out = [];
    const cr = (p0, p1, p2, p3, t) => {
      const t2 = t * t, t3 = t2 * t;
      return {
        x: 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
        y: 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3)
      };
    };
    for (let i = 0; i < P.length - 3; i++) {
      for (let j = 0; j < steps; j++) out.push(cr(P[i], P[i + 1], P[i + 2], P[i + 3], j / steps));
    }
    out.push(P[P.length - 2]);
    return out;
  }
  function atlasChaikin(poly, iterations = 2) {
    if (!poly || poly.length < 3) return poly || [];
    let p = poly;
    for (let n = 0; n < iterations; n++) {
      const out = [];
      for (let i = 0; i < p.length; i++) {
        const a = p[i], b = p[(i + 1) % p.length];
        out.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
        out.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
      }
      p = out;
    }
    return p;
  }
  function atlasArrow(ctx, tip, from, color, scale) {
    const ang = Math.atan2(tip.y - from.y, tip.x - from.x);
    const s = 7 * (scale || 1);
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2 * (scale || 1);
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(tip.x + Math.cos(ang + Math.PI * 0.78) * s, tip.y + Math.sin(ang + Math.PI * 0.78) * s);
    ctx.lineTo(tip.x, tip.y);
    ctx.lineTo(tip.x + Math.cos(ang - Math.PI * 0.78) * s, tip.y + Math.sin(ang - Math.PI * 0.78) * s);
    ctx.stroke();
    ctx.restore();
  }

  function atlasNodeScreen(n) {
    const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
    return {
      x: n.x * kx + mapView.x,
      y: (n.y + (n._markerDy || 0)) * ky + mapView.y
    };
  }
  function atlasWorldScreen(pt) {
    const kx = mapView.kx || mapView.k, ky = mapView.ky || mapView.k;
    return { x: pt[0] * kx + mapView.x, y: pt[1] * ky + mapView.y };
  }
  function atlasMarkerSize(rank, rect) {
    const s = rect.width / 1440;
    if (rank === 1) return Math.round(Math.min(40, Math.max(28, 34 * s)));
    if (rank === 3) return Math.round(Math.min(28, Math.max(18, 21 * s)));
    return Math.round(Math.min(34, Math.max(22, 27 * s)));
  }
  function atlasMarkerSizeOnScreen(rank, rect) {
    return atlasMarkerSize(rank, rect) * mapZoomScale();
  }
  function atlasMarkerTypeOf(n) {
    if (n.marker === 'none') return 'none';
    const explicit = (ATLAS.markers || {})[n.id];
    if (explicit) return explicit;
    if (n.marker) return n.marker;
    const name = n.name || '';
    if (/禁地|秘境|遗迹|洞府|古墓|深渊|墟/.test(name)) return 'secret';
    if (/险|魔|绝|死|断魂|血|凶|禁/.test(name)) return 'danger';
    if (/宗|门|派|阁|殿|寺|观|山门|道观/.test(name)) return 'sect';
    if (/城|京|都|镇|堡|关|州|国|村|寨|集|市|街/.test(name)) return 'city';
    return 'place';
  }

  function drawAtlasPaper(ctx, rect) {
    ctx.fillStyle = ATLAS_THEME.paper;
    ctx.fillRect(0, 0, rect.width, rect.height);
    const paper = mapAsset(ATLAS_SUPPORT.paper);
    const ready = paper.complete && paper.naturalWidth;
    if (!ready) { paper.onload = () => { if (curView === 'map') drawMap(); }; }

    if (ready) {
      // 整张纸底铺满：容纳画布宽高比，不再 cover 裁掉上下装饰边
      ctx.drawImage(paper, 0, 0, paper.naturalWidth, paper.naturalHeight,
        0, 0, rect.width, rect.height);
    } else {
      // 素材未就绪时的代码框，避免白屏
      ctx.save();
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.route, 0.5);
      ctx.lineWidth = 1.2;
      ctx.strokeRect(10.5, 10.5, rect.width - 21, rect.height - 21);
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.route, 0.28);
      ctx.strokeRect(16.5, 16.5, rect.width - 33, rect.height - 33);
      ctx.restore();
    }
  }

  function drawAtlasLand(ctx, reg, rect) {
    if (!reg.polygon) return;
    const pts = atlasChaikin(reg.polygon, 2).map(p => atlasWorldScreen(p));
    ctx.save();
    atlasPath(ctx, pts);
    // 陆地不画边界，避免出现“多边形选区”；只给纸面一层几乎看不出的暖色水洗
    ctx.fillStyle = 'rgba(218,199,164,0.05)';
    ctx.fill();
    ctx.restore();
  }

  function drawAtlasWaterPoly(ctx, pts, rect, opt) {
    if (!pts || pts.length < 3) return;
    const screen = pts.map(p => atlasWorldScreen(p));
    const b = atlasBBox(screen);
    ctx.save();
    atlasPath(ctx, screen);
    const g = ctx.createLinearGradient(0, b.y, 0, b.y + b.h);
    g.addColorStop(0, atlasRgba(ATLAS_THEME.water, opt.top));
    g.addColorStop(0.62, atlasRgba(ATLAS_THEME.water, opt.mid));
    g.addColorStop(1, atlasRgba('#4F7179', opt.bottom));
    ctx.fillStyle = g;
    ctx.fill();

    // 低频水彩斑驳：代码生成的湿边/水痕，不依赖固定纹理
    ctx.save();
    atlasPath(ctx, screen);
    ctx.clip();
    [
      [0.22, 0.24, 0.42, 0.22, 0.05],
      [0.55, 0.16, 0.46, 0.18, 0.04],
      [0.34, 0.58, 0.34, 0.14, 0.04],
      [0.68, 0.52, 0.30, 0.16, 0.035],
      [0.15, 0.72, 0.38, 0.12, 0.03]
    ].forEach(([fx, fy, fw, fh, a], i) => {
      ctx.beginPath();
      ctx.ellipse(b.x + b.w * fx, b.y + b.h * fy, b.w * fw, b.h * fh, 0.25, 0, Math.PI * 2);
      ctx.fillStyle = i % 2 ? `rgba(246,248,242,${a})` : `rgba(58,84,91,${a})`;
      ctx.fill();
    });
    ctx.restore();

    // 可选海面纹理：默认关闭，避免固定纹理的矩形边缘
    if (opt.texture) {
      const tex = mapAsset(ATLAS_SUPPORT.sea);
      if (tex.complete && tex.naturalWidth) {
        ctx.save();
        ctx.globalAlpha = 0.18;
        ctx.clip();
        drawBoxCover(ctx, tex, b);
        ctx.restore();
      } else if (!tex.complete) tex.onload = () => { if (curView === 'map') drawMap(); };
    }

    // 波纹：clip 内横线，越靠下越淡
    ctx.save();
    atlasPath(ctx, screen);
    ctx.clip();
    const gap = Math.max(34, rect.height * 0.064);
    for (let y = b.y + gap * 1.5; y < b.y + b.h; y += gap) {
      ctx.beginPath();
      for (let x = b.x - 8; x <= b.x + b.w + 8; x += 7) {
        const yy = y + Math.sin((x - b.x) * 0.045 + y * 0.012) * 2.3;
        if (x === b.x - 8) ctx.moveTo(x, yy); else ctx.lineTo(x, yy);
      }
      ctx.strokeStyle = `rgba(244,246,241,${0.085 + Math.min(0.045, (y - b.y) / Math.max(b.h, 1) * 0.045)})`;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    ctx.restore();

    // 海岸：先一圈模糊湿边，再压一条细墨线
    ctx.save();
    atlasPath(ctx, screen);
    ctx.strokeStyle = atlasRgba('#5B7A80', 0.20);
    ctx.lineWidth = 10;
    ctx.shadowColor = atlasRgba('#5B7A80', 0.34);
    ctx.shadowBlur = 16;
    ctx.stroke();
    ctx.restore();
    ctx.save();
    atlasPath(ctx, screen);
    ctx.strokeStyle = atlasRgba('#456469', opt.coast);
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
    ctx.restore();
  }

  function drawAtlasSea(ctx, reg, rect) {
    drawAtlasWaterPoly(ctx, atlasChaikin(reg.polygon, 3), rect, {
      top: 0.12, mid: 0.27, bottom: 0.36,
      coast: 0.48,
      texture: ATLAS.seaTexture === true
    });
  }
  function drawAtlasVoid(ctx, reg, rect) {
    if (!reg.polygon) return;
    const pts = atlasChaikin(reg.polygon, 2).map(p => atlasWorldScreen(p));
    ctx.save();
    atlasPath(ctx, pts);
    ctx.fillStyle = 'rgba(243,236,221,0.62)';
    ctx.shadowColor = 'rgba(90,70,40,0.20)';
    ctx.shadowBlur = 18;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = 'rgba(201,185,143,0.80)';
    ctx.lineWidth = 1.3;
    ctx.setLineDash([7, 5]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = 'rgba(59,51,42,0.20)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  }

  function drawAtlasRidgeFallback(ctx, ridge) {
    const pts = smoothWorldPoints(ridge.points).map(p => atlasWorldScreen(p));
    if (pts.length < 2) return;
    const z = mapZoomScale();
    ctx.save();
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.22);
    ctx.lineWidth = 7 * z;
    ctx.lineJoin = 'round';
    drawPolyline(ctx, pts);
    ctx.stroke();
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.55);
    ctx.lineWidth = Math.max(1.2, (ridge.width || 1.8) * 0.9) * z;
    drawPolyline(ctx, pts);
    ctx.stroke();
    ctx.restore();
  }
  function smoothWorldPoints(points) {
    const raw = (points || []).map(p => ({ x: p[0], y: p[1] }));
    return atlasSmoothPoints(raw, 10);
  }
  function drawAtlasStamp(ctx, spec, rect, nodesById) {
    const asset = ATLAS_STAMP_BY_ID[spec.asset];
    if (!asset) return false;
    const img = mapAsset(asset.src);
    let cx = atlasNum(spec.x, 50), cy = atlasNum(spec.y, 50);
    let node = null;
    if (spec.attach) {
      if (!nodesById || !nodesById.has(spec.attach)) return false;
      node = nodesById.get(spec.attach);
      if (node.layer && map2dLayer !== 'all' && node.layer !== map2dLayer) return false;
      cx = node.x;
      cy = node.y + atlasNum(spec.offsetY, 0);
    } else if (spec.layer && map2dLayer !== 'all' && spec.layer !== map2dLayer) {
      return false;
    }
    const defaults = { terrain: 14, water: 10, architecture: 8, vegetation: 6 };
    const wWorld = atlasNum(spec.w, defaults[asset.type] || 8);
    const p = atlasWorldScreen([cx, cy]);
    const x = p.x;
    const y = p.y;
    if (!img.complete || !img.naturalWidth) {
      img.onload = () => { if (curView === 'map') drawMap(); };
      return false;
    }
    const w = wWorld / 100 * rect.width * mapZoomScale();
    const h = w * img.naturalHeight / img.naturalWidth;
    const pivot = spec.anchor === 'center' ? [0.5, 0.5] : (asset.pivot || [0.5, 0.875]);
    ctx.save();
    ctx.translate(x, y);
    if (spec.rotation) ctx.rotate(spec.rotation * Math.PI / 180);
    if (spec.flip) ctx.scale(-1, 1);
    ctx.globalAlpha = atlasNum(spec.opacity, 0.86);
    ctx.drawImage(img, -w * pivot[0], -h * pivot[1], w, h);
    ctx.restore();
    if (node && asset.type === 'architecture') {
      node._markerDy = Math.max(node._markerDy || 0, atlasNum(spec.markerOffset, 2.0));
    }
    return {
      box: { x: x - w * pivot[0] - 2, y: y - h * pivot[1] - 2, w: w + 4, h: h + 4 },
      architecture: asset.type === 'architecture'
    };
  }
  function drawAtlasStamps(ctx, rect) {
    const list = Array.isArray(ATLAS.stamps) ? ATLAS.stamps.slice() : [];
    const nodesById = new Map((mapModel.nodes || []).map(n => [n.id, n]));
    list.sort((a, b) => atlasNum(a.order, 0) - atlasNum(b.order, 0));
    let drawn = 0;
    const boxes = [];
    list.forEach(s => {
      const out = drawAtlasStamp(ctx, s, rect, nodesById);
      if (!out) return;
      drawn++;
      if (out.architecture && out.box) boxes.push(out.box);
    });
    return { drawn, boxes };
  }

  function drawAtlasTerrain(ctx, rect) {
    const terrain = mapModel.terrain || {};
    const nodesById = new Map((mapModel.nodes || []).map(n => [n.id, n]));
    const visibleRegions = new Set((mapModel.regions || []).map(r => r.id));
    const featureVisible = f => !f.region || visibleRegions.has(f.region);

    // 山脊：默认直接使用手绘 PNG ridge；无图时退回代码墨线
    (terrain.ridges || []).filter(featureVisible).forEach((ridge, i) => {
      const pts = ridge.points || [];
      if (ATLAS.terrainStamps !== false && pts.length >= 2) {
        const b = atlasBBox(pts);
        const ridgeId = (i % 2 && ATLAS_STAMP_BY_ID.terrain_ridge_02) ? 'terrain_ridge_02' : 'terrain_ridge_01';
        const w = Math.max(8, Math.min(24, b.w * 1.35 + 5));
        drawAtlasStamp(ctx, {
          asset: ridgeId, x: b.x + b.w / 2, y: Math.min(96, b.y + b.h + 1.5),
          w, opacity: 0.62
        }, rect, nodesById);
      } else {
        drawAtlasRidgeFallback(ctx, ridge);
      }
    });

    // 河流：双线水脉，不用固定 PNG
    (terrain.rivers || []).filter(featureVisible).forEach(r => {
      const pts = smoothWorldPoints(r.points).map(p => atlasWorldScreen(p));
      if (pts.length < 2) return;
      const z = mapZoomScale();
      const w = Math.max(1.2, (r.width || 1) * rect.width / 100 * 0.55) * z;
      ctx.save();
      ctx.lineCap = 'round';
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.water, 0.22);
      ctx.lineWidth = w * 3.2;
      drawPolyline(ctx, pts); ctx.stroke();
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.water, 0.62);
      ctx.lineWidth = w;
      drawPolyline(ctx, pts); ctx.stroke();
      ctx.strokeStyle = 'rgba(245,247,242,0.45)';
      ctx.lineWidth = Math.max(0.7, w * 0.35);
      drawPolyline(ctx, pts); ctx.stroke();
      ctx.restore();
    });

    (terrain.lakes || []).filter(featureVisible).forEach(lake => {
      drawAtlasWaterPoly(ctx, atlasChaikin(lake.polygon, 2), rect, {
        top: 0.18, mid: 0.34, bottom: 0.38, coast: 0.32, texture: false
      });
    });

    (terrain.islets || []).filter(() => map2dLayer === 'all' || !mapModel.regions.length || (mapModel.regions || []).some(r => r.shape === 'sea')).forEach(islet => {
      const p = atlasWorldScreen([islet.x, islet.y]);
      const x = p.x, y = p.y;
      const r = Math.max(2.5, (islet.r || 1.2) / 100 * rect.width) * mapZoomScale();
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(x, y, r * 1.35, r * 0.78, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(232,220,197,0.86)';
      ctx.shadowColor = 'rgba(90,70,40,0.22)';
      ctx.shadowBlur = 6;
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.32);
      ctx.lineWidth = 0.9;
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x - r * 0.45, y - r * 0.12);
      ctx.lineTo(x, y - r * 0.62);
      ctx.lineTo(x + r * 0.38, y - r * 0.08);
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.26);
      ctx.stroke();
      ctx.restore();
    });
  }

