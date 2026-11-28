/* Novel Atlas viewer · 图谱画布与渲染
   职责：力导向布局 / 节点绘制 / 关系线 / 相机 */
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

