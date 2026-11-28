/* Novel Atlas viewer · 百科与地点志
   职责：百科分页 / 地点树 / 地点详情 */
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

