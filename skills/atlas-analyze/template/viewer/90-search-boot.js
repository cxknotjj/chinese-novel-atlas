/* Novel Atlas viewer · 搜索与启动
   职责：全书搜索 / 启动参数 / loop 初始化 */
  /* ================= 全书搜索 ================= */
  const searchInput = document.getElementById('search');
  const searchPanel = document.getElementById('searchPanel');
  function searchText(obj, fields) {
    return fields.map(k => {
      const v = obj[k];
      if (Array.isArray(v)) return v.join(' ');
      return v == null ? '' : String(v);
    }).join(' ').toLowerCase();
  }
  function indexEntries(data, cutoffCh, all) {
    const out = [];
    (data.entities || []).forEach(e => {
      if (!all && typeof e.first_ch === 'number' && e.first_ch > cutoffCh) return;
      out.push({
        kind: e.type === 'character' ? '人物' : e.type === 'org' ? '势力' : e.type === 'item' ? '器物' : '妖兽',
        id: e.id, name: e.name, desc: e.desc || '',
        text: searchText(e, ['name', 'aliases', 'desc', 'group']),
        first: e.first_ch
      });
    });
    (data.places || []).forEach(p => {
      if (!all && typeof p.first_ch === 'number' && p.first_ch > cutoffCh) return;
      out.push({ kind: '地点', id: p.id, name: p.name, desc: p.desc || '',
        text: searchText(p, ['name', 'desc']), first: p.first_ch });
    });
    (data.concepts || []).forEach(c => {
      if (!all && typeof c.first_ch === 'number' && c.first_ch > cutoffCh) return;
      out.push({ kind: '设定', id: c.id, name: c.name, desc: c.desc || '',
        text: searchText(c, ['name', 'desc', 'rules', 'limits']), first: c.first_ch });
    });
    (data.foreshadows || []).forEach(f => {
      if (!all && typeof f.plant_ch === 'number' && f.plant_ch > cutoffCh) return;
      out.push({ kind: '伏笔', id: f.id, name: f.content || '未命名伏笔', desc: f.thread || '',
        text: searchText(f, ['content', 'thread', 'note']), first: f.plant_ch, foreshadow: f });
    });
    (data.anomalies || []).forEach(a => {
      out.push({ kind: '疑点', id: a.id, name: a.title || '', desc: a.kind_cn || '',
        text: searchText(a, ['title', 'detail', 'reader_note', 'kind_cn']),
        first: (a.chapter_range || [])[0], anomaly: a });
    });
    (data.chapters || []).forEach(c => {
      if (!all && c.ch > cutoffCh) return;
      out.push({ kind: '章节', id: String(c.ch), name: `第 ${c.ch} 章 ${c.title || ''}`,
        desc: c.summary || '', text: searchText(c, ['title', 'summary', 'hook']),
        first: c.ch, chapter: c });
    });
    return out;
  }
  let searchIndexCache = null;
  function getSearchIndex() {
    if (!searchIndexCache) searchIndexCache = indexEntries(D, cutoff, false);
    return searchIndexCache;
  }
  function futureSearch(q) {
    const max = maxChapter(FULL_D);
    if (cutoff >= max) return [];
    const out = [];
    const visible = new Set(getSearchIndex().map(x => x.id));
    const full = indexEntries(FULL_D, max, true);
    full.forEach(x => {
      if (visible.has(x.id) || !x.text.includes(q)) return;
      const first = typeof x.first === 'number' ? x.first : null;
      if (!first || first <= cutoff) return;
      out.push({ kind: x.kind, first });
    });
    return out;
  }
  function hideSearch() {
    if (searchPanel) searchPanel.hidden = true;
  }
  function searchResultClick(item) {
    hideSearch();
    if (!item) return;
    if (item.chapter) { showChapter(item.chapter); return; }
    if (item.foreshadow) { setView('foreshadow'); return; }
    if (item.anomaly) { setView('anomalies'); return; }
    const rec = allById.get(item.id);
    if (!rec) return;
    if (rec._kind === 'entity') { setView('graph'); select(item.id, { center: true }); }
    else if (rec._kind === 'place') openPlace(item.id);
    else renderLite(rec);
  }
  function doSearch(raw) {
    const q = String(raw || '').trim().toLowerCase();
    if (!q) { hideSearch(); return; }
    const visible = getSearchIndex().filter(x => x.text.includes(q)).slice(0, 24);
    const future = futureSearch(q).slice(0, 10);
    const rows = visible.map(x => `
      <div class="sp-row" data-sp-id="${escHtml(x.id)}" data-sp-kind="${escHtml(x.kind)}">
        <div class="sp-kind">${escHtml(x.kind)}</div>
        <div class="sp-main">
          <div class="sp-name">${escHtml(x.name)}</div>
          <div class="sp-desc">${escHtml((x.desc || '').slice(0, 90))}</div>
        </div>
      </div>`).join('');
    const locked = future.map(x => `
      <div class="sp-row sp-locked">
        <div class="sp-kind">${escHtml(x.kind)}</div>
        <div class="sp-main">
          <div class="sp-name">第 ${x.first} 章后解锁</div>
          <div class="sp-desc">当前进度不展示未来内容</div>
        </div>
      </div>`).join('');
    searchPanel.innerHTML = `
      <div class="sp-title">全书搜索 · ${visible.length + future.length} 条命中</div>
      ${rows}${locked}
      ${!visible.length && !future.length ? '<div class="sp-empty">没有找到。试试人物名、地点、伏笔关键词或章节标题。</div>' : ''}
    `;
    searchPanel.hidden = false;
    searchPanel.querySelectorAll('[data-sp-id]').forEach(el => {
      el.addEventListener('click', () => {
        const item = visible.find(x => x.id === el.dataset.spId && x.kind === el.dataset.spKind);
        searchResultClick(item);
      });
    });
  }
  if (searchInput && searchPanel) {
    searchInput.addEventListener('input', e => doSearch(e.target.value));
    searchInput.addEventListener('keydown', e => {
      if (e.key === 'Escape') { searchInput.value = ''; hideSearch(); searchInput.blur(); }
      if (e.key === 'Enter') {
        const first = searchPanel.querySelector('.sp-row:not(.sp-locked)');
        if (first) first.click();
      }
    });
    document.addEventListener('click', e => {
      if (!searchPanel.contains(e.target) && e.target !== searchInput) hideSearch();
    });
  }

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
      d.textContent = `W=${W|0} H=${H|0} dpr=${DPR} parent=${r.width|0}x${r.height|0}\nview k=${view.k.toFixed(3)} x=${view.x|0} y=${view.y|0}\nnodes ${nodes.length} bbox x[${minX|0},${maxX|0}] y[${minY|0},${maxY|0}]\translated center=(${((minX+maxX)/2*view.k+view.x)|0},${((minY+maxY)/2*view.k+view.y)|0})\ndoc ${document.documentElement.scrollWidth}x${document.documentElement.scrollHeight} inner ${innerWidth}x${innerHeight}`;
    }, 400);
  }

  window.addEventListener('resize', resize);
  resize();
  updateGraphTools();
  renderWiki();
  const bootQuery = new URLSearchParams(location.search);
  let bootZoomPending = Number(bootQuery.get('zoom'));
  if (!Number.isFinite(bootZoomPending) || bootZoomPending <= 0) bootZoomPending = 0;
  if (bootQuery.get('edit') === '1') mapEditMode = true;
  if (bootQuery.get('slice')) mapSlice = bootQuery.get('slice');
  setView(readViewParam());
  requestAnimationFrame(loop);
  for (let i = 0; i < 900; i++) tick();
  spreadLayoutAspect();
  fitView();
  alpha = 0.03;
