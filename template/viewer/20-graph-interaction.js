/* Novel Atlas viewer · 图谱交互与详情面板
   职责：命中测试 / 拖拽 / 选择 / 侧栏详情 */
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

