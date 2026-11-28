/* Novel Atlas viewer · 地图路线、标记、文字与装饰
   职责：路线 / 图标 / 地名 / 题签 / 印章 / 免责声明 */
  function drawAtlasRoutes(ctx, rect) {
    const nodesById = new Map((mapModel.nodes || []).map(n => [n.id, n]));
    const seaPolys = (mapModel.regions || []).filter(r => r.shape === 'sea' && r.polygon).map(r => r.polygon);
    const labels = [];
    (mapModel.routes || []).forEach(route => {
      const a = nodesById.get(route.s), b = nodesById.get(route.t);
      if (!a || !b) return;
      const world = [{ x: a.x, y: a.y }]
        .concat((route.curve || []).map(p => ({ x: p[0], y: p[1] })))
        .concat([{ x: b.x, y: b.y }]);
      const pts = atlasSmoothPoints(world, 14).map(p => atlasWorldScreen([p.x, p.y]));
      if (pts.length < 2) return;
      const sea = route.tone === 'sea' || seaPolys.some(poly =>
        atlasPointInPoly({ x: a.x, y: a.y }, poly) ||
        atlasPointInPoly({ x: b.x, y: b.y }, poly));
      const isRiver = route.kind === 'river';
      const solid = route.kind === 'road' || isRiver;
      const color = isRiver ? ATLAS_THEME.water : (sea ? '#6F8B93' : ATLAS_THEME.route);
      const alpha = sea ? 0.82 : 0.88;
      const z = mapZoomScale();
      ctx.save();
      ctx.lineCap = 'round';
      ctx.strokeStyle = atlasRgba(color, alpha);
      ctx.lineWidth = (isRiver ? 1.5 : (sea ? 2.1 : 1.9)) * z;
      ctx.setLineDash(solid ? [] : [7 * z, 5 * z]);
      drawPolyline(ctx, pts);
      ctx.stroke();
      ctx.setLineDash([]);
      // 端点：小墨点，避免“无头线段”
      if (!isRiver) {
        [pts[0], pts[pts.length - 1]].forEach(p => {
          ctx.beginPath(); ctx.arc(p.x, p.y, 2.4 * z, 0, Math.PI * 2);
          ctx.fillStyle = atlasRgba(color, 0.58); ctx.fill();
          ctx.strokeStyle = atlasRgba(ATLAS_THEME.paper, 0.7); ctx.lineWidth = 0.8 * z; ctx.stroke();
        });
      }
      if (!solid) {
        const tip = pts[pts.length - 1], from = pts[Math.max(0, pts.length - 8)];
        atlasArrow(ctx, tip, from, atlasRgba(color, 0.92), z);
      }
      ctx.restore();
      if (route.label) {
        const idx = Math.max(0, Math.floor(pts.length * 0.56));
        const p = pts[idx];
        const labelFont = 11 * mapLabelScale();
        ctx.save();
        ctx.font = `${labelFont}px -apple-system,"PingFang SC",sans-serif`;
        const tw = ctx.measureText(route.label).width;
        ctx.restore();
        labels.push({
          kind: 'route', text: route.label, x: p.x, y: p.y - labelFont * 0.8,
          w: tw + 8, h: labelFont * 1.45, priority: 3, color: sea ? '#627E86' : '#7A3B2E', font: labelFont
        });
      }
    });
    return labels;
  }

  function drawAtlasMarker(ctx, type, cx, cy, size, highlighted) {
    if (type === 'none') return;
    const u = size / 100;
    if (!u) return;
    const px = v => v / u;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(u, u);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (highlighted) {
      ctx.beginPath(); ctx.arc(50, 50, 48, 0, Math.PI * 2);
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.seal, 0.75); ctx.lineWidth = px(2.2); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(50, 50, 44, 0, Math.PI * 2);
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.34); ctx.lineWidth = px(0.9); ctx.stroke();
    ctx.beginPath(); ctx.arc(50, 50, 40, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(232,220,197,0.20)'; ctx.fill();

    if (type === 'city') {
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.86); ctx.lineWidth = px(1.1);
      ctx.beginPath();
      ctx.moveTo(27, 64); ctx.lineTo(27, 50); ctx.lineTo(32, 50); ctx.lineTo(32, 46);
      ctx.lineTo(38, 46); ctx.lineTo(38, 50); ctx.lineTo(44, 50); ctx.lineTo(44, 46);
      ctx.lineTo(50, 46); ctx.lineTo(50, 50); ctx.lineTo(56, 50); ctx.lineTo(56, 46);
      ctx.lineTo(62, 46); ctx.lineTo(62, 50); ctx.lineTo(68, 50); ctx.lineTo(68, 64);
      ctx.closePath(); ctx.stroke();
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.50); ctx.lineWidth = px(0.8);
      ctx.beginPath(); ctx.moveTo(27, 57); ctx.lineTo(68, 57); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(46, 64); ctx.lineTo(46, 58); ctx.lineTo(48, 55.5);
      ctx.lineTo(50, 54.5); ctx.lineTo(52.5, 55.5); ctx.lineTo(54, 58); ctx.lineTo(54, 64);
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.84); ctx.lineWidth = px(1); ctx.stroke();
      ctx.beginPath(); ctx.arc(50, 60, 2.2, Math.PI, Math.PI * 2);
      ctx.fillStyle = atlasRgba(ATLAS_THEME.accent, 0.55); ctx.fill();
    } else if (type === 'sect') {
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.84); ctx.lineWidth = px(1.2);
      ctx.beginPath();
      ctx.moveTo(29, 49); ctx.quadraticCurveTo(50, 36, 71, 49); ctx.stroke();
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.68); ctx.lineWidth = px(1);
      ctx.beginPath(); ctx.moveTo(27, 51); ctx.quadraticCurveTo(50, 40, 73, 51); ctx.stroke();
      ctx.lineWidth = px(1.1);
      ctx.beginPath();
      ctx.moveTo(40, 51); ctx.lineTo(40, 67); ctx.moveTo(60, 51); ctx.lineTo(60, 67);
      ctx.moveTo(36, 67); ctx.lineTo(64, 67); ctx.stroke();
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.accent, 0.68);
      ctx.beginPath();
      ctx.moveTo(46, 67); ctx.lineTo(46, 59); ctx.lineTo(48, 56);
      ctx.lineTo(50, 55); ctx.lineTo(52, 56); ctx.lineTo(54, 59); ctx.lineTo(54, 67);
      ctx.stroke();
    } else if (type === 'secret') {
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.72); ctx.lineWidth = px(1.25);
      ctx.beginPath();
      for (let a = 0; a <= Math.PI * 5; a += 0.22) {
        const r = 4.5 + a * 1.45;
        const x = 50 + Math.cos(a) * r, y = 50 + Math.sin(a) * r;
        if (a === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.beginPath(); ctx.arc(50, 50, 2.1, 0, Math.PI * 2);
      ctx.fillStyle = atlasRgba(ATLAS_THEME.seal, 0.78); ctx.fill();
      ctx.beginPath(); ctx.arc(66, 34, 1.7, 0, Math.PI * 2);
      ctx.fillStyle = atlasRgba(ATLAS_THEME.accent, 0.55); ctx.fill();
    } else if (type === 'danger') {
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.seal, 0.86); ctx.lineWidth = px(1.3);
      ctx.beginPath(); ctx.moveTo(50, 26); ctx.lineTo(74, 68); ctx.lineTo(26, 68); ctx.closePath(); ctx.stroke();
      ctx.lineWidth = px(1.2);
      ctx.beginPath(); ctx.moveTo(50, 43); ctx.lineTo(50, 56); ctx.stroke();
      ctx.beginPath(); ctx.arc(50, 61, 1.8, 0, Math.PI * 2);
      ctx.fillStyle = atlasRgba(ATLAS_THEME.seal, 0.86); ctx.fill();
    } else {
      ctx.beginPath(); ctx.arc(50, 50, 11, 0, Math.PI * 2);
      ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.52); ctx.lineWidth = px(1); ctx.stroke();
      ctx.beginPath(); ctx.arc(50, 50, 3.2, 0, Math.PI * 2);
      ctx.fillStyle = atlasRgba(ATLAS_THEME.ink, 0.62); ctx.fill();
    }
    ctx.restore();
  }

  function drawAtlasRegionLabel(ctx, box, text, fontPx) {
    ctx.save();
    ctx.font = `600 ${fontPx}px "Songti SC","SimSun",serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = Math.max(3, fontPx * 0.12);
    ctx.strokeStyle = 'rgba(243,236,221,0.88)';
    ctx.strokeText(text, box.x + box.w / 2, box.y + box.h / 2);
    ctx.fillStyle = ATLAS_THEME.ink;
    ctx.fillText(text, box.x + box.w / 2, box.y + box.h / 2);
    ctx.restore();
  }
  function drawAtlasNodeLabel(ctx, cand) {
    ctx.save();
    ctx.font = `${cand.rank === 1 ? '600 ' : ''}${cand.font}px -apple-system,"PingFang SC",sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = Math.max(3.2, cand.font * 0.22);
    ctx.strokeStyle = 'rgba(243,236,221,0.94)';
    ctx.strokeText(cand.text, cand.x, cand.y);
    ctx.fillStyle = cand.color || '#2B2A26';
    ctx.fillText(cand.text, cand.x, cand.y);
    ctx.restore();
  }

  function drawAtlasCompass(ctx, cx, cy, size, opacity) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(size / 100, size / 100);
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = ATLAS_THEME.ink;
    ctx.fillStyle = ATLAS_THEME.ink;
    [[46, 0.36, 1.8], [40, 0.46, 1.2], [31, 0.34, 1]].forEach(([r, a, w]) => {
      ctx.beginPath(); ctx.arc(50, 50, r, 0, Math.PI * 2);
      ctx.globalAlpha = opacity * a; ctx.lineWidth = w; ctx.stroke();
    });
    ctx.globalAlpha = opacity;
    for (let i = 0; i < 24; i++) {
      const a = i * Math.PI / 12;
      const r1 = 18.5, r2 = 11;
      ctx.beginPath();
      ctx.moveTo(50 + Math.cos(a) * r1, 50 + Math.sin(a) * r1);
      ctx.lineTo(50 + Math.cos(a) * r2, 50 + Math.sin(a) * r2);
      ctx.globalAlpha = opacity * (i % 6 === 0 ? 0.55 : 0.32);
      ctx.lineWidth = 0.9;
      ctx.stroke();
    }
    ctx.globalAlpha = opacity;
    ctx.beginPath();
    ctx.moveTo(50, 50); ctx.lineTo(46.3, 26); ctx.lineTo(50, 18); ctx.lineTo(53.7, 26); ctx.closePath();
    ctx.fillStyle = atlasRgba(ATLAS_THEME.seal, 0.62); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(50, 50); ctx.lineTo(46.3, 74); ctx.lineTo(50, 82); ctx.lineTo(53.7, 74); ctx.closePath();
    ctx.fillStyle = atlasRgba(ATLAS_THEME.ink, 0.48); ctx.fill();
    ctx.beginPath(); ctx.arc(50, 50, 2.6, 0, Math.PI * 2);
    ctx.fillStyle = atlasRgba(ATLAS_THEME.ink, 0.75); ctx.fill();
    ctx.restore();
  }

  function atlasTitleSpec() {
    const def = atlasDefaultTitle();
    const base = Object.assign({ x: 4.2, y: 8.8, size: 3.1, direction: 'vertical' }, ATLAS.title || {});
    const byLayer = (map2dLayer !== 'all' && ATLAS.titleByLayer) ? ATLAS.titleByLayer[map2dLayer] : null;
    const spec = Object.assign({}, base, byLayer || {});
    if (!spec.text) spec.text = def.text;
    return spec;
  }

  function atlasTitleBox(ctx, rect) {
    const spec = atlasTitleSpec();
    const fs = Math.max(11, Math.min((atlasNum(spec.size, 3.1) / 100) * rect.width, rect.height * 0.053));
    const text = spec.text || '山河舆图';
    const chars = Array.from(text);
    const vertical = spec.direction !== 'horizontal';
    const lineH = fs * 1.04;
    let w = fs * 1.65, h = chars.length * lineH + fs * 0.85;
    if (!vertical) {
      ctx.save();
      ctx.font = `600 ${fs}px "Songti SC","SimSun",serif`;
      w = ctx.measureText(text).width + fs * 1.7;
      h = fs * 1.65;
      ctx.restore();
    }
    let x = (atlasNum(spec.x, 4.2) / 100) * rect.width;
    let y = (atlasNum(spec.y, 8.8) / 100) * rect.height;
    // 左上角云纹的安全区：题签不压在纸底装饰上
    const cornerW = rect.width * 0.105, cornerH = rect.height * 0.18;
    if (x < cornerW && y < cornerH) y = cornerH + 4;
    return { x, y, w, h };
  }

  function drawAtlasCartouche(ctx, rect, spec) {
    const fs = Math.max(11, Math.min((atlasNum(spec.size, 3.1) / 100) * rect.width, rect.height * 0.053));
    const text = spec.text || '山河舆图';
    const chars = Array.from(text);
    const vertical = spec.direction !== 'horizontal';
    const lineH = fs * 1.04;
    let w = fs * 1.65, h = chars.length * lineH + fs * 0.85;
    if (!vertical) {
      ctx.save();
      ctx.font = `600 ${fs}px "Songti SC","SimSun",serif`;
      w = ctx.measureText(text).width + fs * 1.7;
      h = fs * 1.65;
      ctx.restore();
    }
    const x = (atlasNum(spec.x, 4.2) / 100) * rect.width;
    const y = (atlasNum(spec.y, 9) / 100) * rect.height;
    ctx.save();
    ctx.fillStyle = 'rgba(244,237,223,0.72)';
    ctx.shadowColor = 'rgba(90,70,40,0.12)';
    ctx.shadowBlur = 12;
    ctx.fillRect(x, y, w, h);
    ctx.shadowBlur = 0;
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.60);
    ctx.lineWidth = 1.6;
    ctx.strokeRect(x + 0.8, y + 0.8, w - 1.6, h - 1.6);
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.ink, 0.34);
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 4.5, y + 4.5, w - 9, h - 9);
    ctx.strokeStyle = atlasRgba(ATLAS_THEME.accent, 0.55);
    ctx.lineWidth = 1;
    const c = Math.min(9, fs * 0.38);
    [[x + 7, y + 7, 1, 1], [x + w - 7, y + 7, -1, 1],
     [x + 7, y + h - 7, 1, -1], [x + w - 7, y + h - 7, -1, -1]].forEach(([px, py, dx, dy]) => {
      ctx.beginPath(); ctx.moveTo(px + dx * c, py); ctx.lineTo(px, py); ctx.lineTo(px, py + dy * c); ctx.stroke();
    });
    ctx.fillStyle = ATLAS_THEME.ink;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = `600 ${fs}px "Songti SC","SimSun",serif`;
    if (vertical) {
      chars.forEach((ch, i) => ctx.fillText(ch, x + w / 2, y + fs * 0.55 + i * lineH + fs * 0.42));
    } else {
      ctx.fillText(text, x + w / 2, y + h / 2 + 1);
    }
    ctx.restore();
    return {
      frame: { x, y, w, h },
      seal: {
        x: (atlasNum(spec.sealX, (x + w / 2) / rect.width * 100)),
        y: (atlasNum(spec.sealY, (y + h + fs * 0.72) / rect.height * 100)),
        size: atlasNum(spec.sealSize, 2.55),
        ch: spec.sealCh || chars[0] || '山',
        angle: atlasNum(spec.sealAngle, -0.035)
      }
    };
  }

  function drawAtlasSeal(ctx, rect, spec) {
    const size = Math.max(16, (atlasNum(spec.size, 2.5) / 100) * rect.width);
    const cx = (atlasNum(spec.x, 6) / 100) * rect.width;
    const cy = (atlasNum(spec.y, 28) / 100) * rect.height;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(atlasNum(spec.angle, 0));
    ctx.fillStyle = ATLAS_THEME.seal;
    ctx.globalAlpha = 0.92;
    ctx.fillRect(-size / 2, -size / 2, size, size);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = 'rgba(245,235,215,0.68)';
    ctx.lineWidth = 1.2;
    ctx.strokeRect(-size / 2 + size * 0.12, -size / 2 + size * 0.12, size * 0.76, size * 0.76);
    ctx.fillStyle = '#F5EBD7';
    ctx.font = `${Math.max(10, Math.round(size * 0.52))}px "SimSun",serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(Array.from(spec.ch || '山')[0], 0, 1);
    ctx.restore();
  }

  function drawAtlasDisclaimer(ctx, rect, spec) {
    const text = spec && spec.text ? spec.text : '示意舆图 · 方位与比例非精确';
    const y = (atlasNum(spec && spec.y, 95.5) / 100) * rect.height;
    const fs = Math.max(9, Math.min(12, rect.width / 120));
    ctx.save();
    ctx.font = `${fs}px -apple-system,"PingFang SC",sans-serif`;
    const textW = ctx.measureText(text).width;
    const left = rect.width * 0.5 - (textW + fs * 2.1) / 2;
    ctx.strokeStyle = 'rgba(166,106,69,0.50)';
    ctx.lineWidth = 1;
    ctx.strokeRect(left, y - fs * 0.9, fs * 1.45, fs * 1.6);
    ctx.strokeStyle = 'rgba(166,106,69,0.28)';
    ctx.strokeRect(left + 2.2, y - fs * 0.9 + 2.2, fs * 1.45 - 4.4, fs * 1.6 - 4.4);
    ctx.fillStyle = 'rgba(141,128,112,0.88)';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, left + fs * 2.1, y);
    ctx.restore();
  }

  function atlasDefaultTitle() {
    const land = (mapModel.regions || []).find(r => r.shape === 'land' && r.name);
    const base = land ? land.name.replace(/(?:大陆|大洲|之洲)$/g, '') : '山河';
    return { text: `${base}舆图`, sealCh: Array.from(base)[0] || '山' };
  }

  function drawAtlasFixedUI(ctx, rect) {
    const titleSpec = atlasTitleSpec();
    const title = drawAtlasCartouche(ctx, rect, titleSpec);
    const sealSpec = Object.assign({}, title.seal, ATLAS.seal || {});
    if (map2dLayer !== 'all' && titleSpec.sealCh) sealSpec.ch = titleSpec.sealCh;
    drawAtlasSeal(ctx, rect, sealSpec);
    if (ATLAS.compass !== false) {
      const compass = Object.assign({ x: 91.5, y: 87.5, size: 7.2, opacity: 0.46 }, ATLAS.compass || {});
      drawAtlasCompass(ctx, (compass.x / 100) * rect.width, (compass.y / 100) * rect.height,
        (compass.size / 100) * rect.width, atlasNum(compass.opacity, 0.46));
    }
    drawAtlasDisclaimer(ctx, rect, ATLAS.disclaimer);
  }

  function drawMap2dLegend(ctx, rect, markerSize) {
    // 图例改由页脚文字承担；画布内不压地图，避免挡题签/罗盘
  }

