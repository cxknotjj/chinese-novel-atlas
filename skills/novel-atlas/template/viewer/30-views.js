/* Novel Atlas viewer · 视图切换、总览与疑点
   职责：setView / 首页 / 疑点索引 */
  /* ================= 视图切换 ================= */
  const stage = document.getElementById('stage');
  const views = {
    home: document.getElementById('home'),
    graph: stage,
    wiki: document.getElementById('wiki'),
    geo: document.getElementById('geo'),
    map: document.getElementById('map'),
    power: document.getElementById('power'),
    rhythm: document.getElementById('rhythm'),
    realms: document.getElementById('realms'),
    foreshadow: document.getElementById('foreshadow'),
    anomalies: document.getElementById('anomalies')
  };
  const VIEW_LABEL = {
    home: '总览', graph: '图谱', wiki: '百科', geo: '地点志', map: '地图',
    power: '版图', rhythm: '节奏', realms: '境界', foreshadow: '伏笔', anomalies: '疑点'
  };
  const isView = v => typeof v === 'string' &&
    Object.prototype.hasOwnProperty.call(VIEW_LABEL, v);
  let curView = 'home';

  /** URL 是视图的真相来源：?view=graph。
      同时兼容 #graph / #view=graph 这类把状态塞进 hash 的地址（hash 视为手动指定，优先）。 */
  function readViewParam() {
    let v = new URLSearchParams(location.search).get('view');
    const h = String(location.hash || '').replace(/^#\/?/, '');
    if (/^view=/.test(h)) v = h.slice(5);
    else if (isView(h)) v = h;
    return isView(v) ? v : 'home';
  }

  /** 只改地址栏：不刷新、不新增历史，刷新与分享都停在当前视图 */
  function syncViewUrl(v) {
    try {
      const url = new URL(location.href);
      if (v === 'home') url.searchParams.delete('view');
      else url.searchParams.set('view', v);
      // 进度也写进地址：任意时刻复制链接，对方看到的都是同一章
      url.searchParams.set('cutoff', String(cutoff));
      // 把 hash 里遗留的 atlas 状态迁回查询串并清掉，地址栏只保留一份真相
      const frag = String(location.hash || '').replace(/^#\/?/, '');
      const legacyCut = frag.match(/^cutoff[-=](\d+)/);
      if (legacyCut) url.searchParams.set('cutoff', legacyCut[1]);
      if (isView(frag) || /^(?:view=|cutoff[-=])/.test(frag)) url.hash = '';
      history.replaceState(null, '', url.toString());
    } catch (e) { /* file:// 等环境不支持时静默忽略，不影响页面 */ }
  }

  function setView(v) {
    if (!isView(v)) v = 'home';
    curView = v;
    syncViewUrl(v);
    if (D.meta && D.meta.title) {
      document.title = `${D.meta.title} · ${VIEW_LABEL[v]} · Novel Atlas`;
    }
    Object.keys(views).forEach(k => { views[k].hidden = k !== v; });
    document.querySelectorAll('.tab').forEach(t =>
      t.classList.toggle('on', t.dataset.view === v));
    if (v === 'home') renderHome();
    if (v === 'graph') { resize(); alpha = Math.max(alpha, 0.3); }
    if (v === 'wiki') renderWiki();
    if (v === 'geo') renderGeo();
    if (v === 'map') renderMap();
    if (v === 'power') renderPower();
    if (v === 'rhythm') renderRhythm();
    if (v === 'realms') renderRealms();
    if (v === 'foreshadow') renderForeshadow();
    if (v === 'anomalies') renderAnomalies();
  }
  document.querySelectorAll('.tab').forEach(t =>
    t.addEventListener('click', () => setView(t.dataset.view)));
  // 手动改 hash（或在地址被外部重写时）也能切视图：#graph / #view=map
  window.addEventListener('hashchange', () => {
    const v = readViewParam();
    if (v !== curView) setView(v);
  });

  /* ================= 总览 ================= */
  function statNumber(n) { return Number(n || 0).toLocaleString('zh-CN'); }

  /* ---------- 证据覆盖率 ----------
     读者可见指标：多少条目真的带坐标，而不是只听「有证据」。
     口径：实体/地点看首现章；关系看首现章 + 证据坐标；伏笔看埋设章 + 埋设段落。
     全部按当前阅读进度统计，所以拖动进度条会一起变。 */
  const posInt = n => typeof n === 'number' && Number.isFinite(n) && n > 0;
  const coordText = v => typeof v === 'string' && /^ch\d+(?::p\d+)?$/i.test(v.trim());
  const paraText = v => typeof v === 'string' && /^ch\d+:p\d+$/i.test(v.trim());

  function evidenceCoverage() {
    const rows = [
      { key: '实体', list: D.entities, ok: e => posInt(e.first_ch) },
      { key: '关系', list: D.relations,
        ok: r => posInt(r.first_ch) || (r.evidence || []).some(coordText),
        para: r => (r.evidence || []).some(paraText) },
      { key: '地点', list: D.places, ok: p => posInt(p.first_ch) },
      { key: '伏笔', list: D.foreshadows,
        ok: f => posInt(f.plant_ch) || coordText(f.plant_quote),
        para: f => paraText(f.plant_quote) }
    ].map(r => {
      const total = r.list.length;
      const coord = r.list.filter(r.ok).length;
      return { key: r.key, total, coord, para: r.para ? r.list.filter(r.para).length : null };
    });
    const total = rows.reduce((n, r) => n + r.total, 0);
    const coord = rows.reduce((n, r) => n + r.coord, 0);
    const paraTotal = rows.reduce((n, r) => n + (r.para === null ? 0 : r.total), 0);
    const para = rows.reduce((n, r) => n + (r.para === null ? 0 : r.para), 0);
    return { rows, total, coord, para, paraTotal, pct: total ? Math.round(coord / total * 100) : 0 };
  }

  function evidenceCardHTML(ev) {
    const paraRows = ev.rows.filter(r => r.para !== null);
    const note = ev.total
      ? (paraRows.length
        ? `段级坐标（chN:pM）：${paraRows.map(r => `${r.key} ${r.para}/${r.total}`).join(' · ')}。`
        : '坐标精确到章节。')
      : '当前进度还没有可统计的条目。';
    const gap = ev.total - ev.coord;
    return `<div class="evidence-card${gap ? ' warn' : ''}">
      <div class="evidence-head">
        <span class="evidence-kicker" title="实体/地点=首现章；关系=首现章+证据坐标；伏笔=埋设章+埋设段落；按当前阅读进度统计">EVIDENCE COVERAGE · 证据覆盖率</span>
        <b class="evidence-pct">${ev.pct}%</b>
      </div>
      <div class="evidence-bar"><i style="width:${ev.pct}%"></i></div>
      <div class="evidence-grid">
        ${ev.rows.map(r => `<span><b>${r.key}</b> ${r.coord} / ${r.total}</span>`).join('')}
      </div>
      <div class="evidence-note">${gap
        ? `${gap} 条缺章节坐标，已在覆盖率里扣除；其余都能回到原文。`
        : `全部 ${ev.total} 条记录都带章节坐标。`}${note}</div>
    </div>`;
  }

  function renderHome() {
    const home = views.home;
    if (!home) return;
    const chars = D.entities.filter(e => e.type === 'character');
    const anomalyN = (D.anomalies || []).length;
    const mapLevel = (D._mapLevels && D._mapLevels.global) || 'M1';
    const meta = FULL_D.meta || {};
    const done = (meta.coverage && meta.coverage.chapters_done) || maxChapter(FULL_D);
    const total = meta.chapters || maxChapter(FULL_D);
    const entries = [
      ['graph', '人物图谱', `${chars.length} 个角色`, '按关系网络看人，点击节点看档案'],
      ['wiki', '设定百科', `${D.concepts.length} 条设定`, '人物、势力、地点、概念、境界速查'],
      ['geo', '地点志', `${D.places.length} 个地点`, '按 parent 层级展开，带首现章与证据'],
      ['map', `世界地图`, `${mapLevel} 证据等级`, '按阅读进度显示地点与路线，不剧透'],
      ['power', '势力版图', `${D.entities.filter(e => e.type === 'org').length} 个势力`, '据点、同盟、敌对与未归属缺口'],
      ['rhythm', '节奏曲线', `${D.chapters.length} 章`, '钩子率、爽点间隔、张力与章末钩子'],
      ['realms', '境界轨迹', `${D.realms.length} 级体系`, '每个角色的突破章与越级战斗'],
      ['foreshadow', '伏笔台账', `${D.foreshadows.length} 条`, '埋设、回收、沉默时长与原文证据']
    ];
    home.innerHTML = `
      <section class="home-hero">
        <div class="home-kicker">NOVEL ATLAS · 读者世界档案</div>
        <h1 class="home-title">${escHtml(meta.title || '未命名')}</h1>
        <div class="home-sub">${escHtml(meta.note || '把一本已完结的小说拆成可查询、可追溯的世界档案。')}</div>
        <div class="home-meta">
          <span>${escHtml(meta.author || '')}</span>
          <span>${escHtml(meta.genre || '')} · ${escHtml(meta.platform || '')}</span>
          <span><b>${escHtml(String(meta.status || '完结'))}</b></span>
          <span>${(meta.chars / 10000).toFixed(0)} 万字 · 全书 ${total} 章</span>
          <span>档案覆盖 <b>${done}</b> / ${total} 章</span>
        </div>
      </section>

      <div class="home-grid">
        <div class="home-card static">
          <div class="hc-k">你现在读到</div>
          <div class="hc-v">第 ${cutoff} 章</div>
          <div class="hc-n">${cutoff < maxChapter(FULL_D)
            ? '后续内容已锁定，拖动上方进度条继续'
            : done < total ? `档案覆盖到第 ${done} 章；后续尚未分析` : '全书已解锁，可随意回看章节'}</div>
        </div>
        <div class="home-card ${anomalyN ? 'alarm' : ''}" data-home-view="anomalies">
          <div class="hc-k">作品疑点索引</div>
          <div class="hc-v">${anomalyN} 条</div>
          <div class="hc-n">每条都带原文/章节证据，不是判决，供读者自行复核</div>
        </div>
        <div class="home-card" data-home-view="foreshadow">
          <div class="hc-k">伏笔回收</div>
          <div class="hc-v">${D.foreshadows.filter(f => f.payoff_ch).length} 条已回收</div>
          <div class="hc-n">${D.foreshadows.filter(f => !f.payoff_ch).length} 条在当前进度仍未回收</div>
        </div>
        <div class="home-card" data-home-view="map">
          <div class="hc-k">世界地图</div>
          <div class="hc-v">${mapLevel}</div>
          <div class="hc-n">${D._mapLevels ? D._mapLevels.reason : '按地图证据自动分级'}</div>
        </div>
      </div>

      ${evidenceCardHTML(evidenceCoverage())}

      <h2>世界入口 <span class="n">八个视图，共用同一份世界档案</span></h2>
      <div class="home-grid">
        ${entries.map(([v, title, count, desc]) => `
          <div class="home-card" data-home-view="${v}">
            <div class="hc-k">${escHtml(count)}</div>
            <div class="hc-v">${escHtml(title)}</div>
            <div class="hc-n">${escHtml(desc)}</div>
          </div>`).join('')}
      </div>

      <div class="home-note">
        <b>阅读原则：</b>所有视图都只显示第 1–${cutoff} 章读者已知的内容。
        地图坐标是叙事示意，不是经纬度；疑点是数据候选，不是对作品的判决。
      </div>
    `;
    home.querySelectorAll('[data-home-view]').forEach(el => {
      el.addEventListener('click', () => setView(el.dataset.homeView));
    });
  }

  /* ================= 疑点索引 ================= */
  let anomalyFilter = 'all';
  const anomalyStateKey = id => 'novel-atlas.anomaly.' + id;
  function anomalyState(id) {
    try { return localStorage.getItem(anomalyStateKey(id)) || ''; } catch (e) { return ''; }
  }
  function setAnomalyState(id, state) {
    try { localStorage.setItem(anomalyStateKey(id), state); } catch (e) {}
    renderAnomalies();
  }
  function renderAnomalies() {
    const wrap = views.anomalies;
    if (!wrap) return;
    const all = D.anomalies || [];
    const sev = { high: 0, warning: 0, info: 0 };
    all.forEach(a => { sev[a.severity] = (sev[a.severity] || 0) + 1; });
    const filtered = anomalyFilter === 'warning'
      ? all.filter(a => a.severity !== 'info')
      : anomalyFilter === 'foreshadow'
        ? all.filter(a => a.kind === 'foreshadow_unresolved')
        : anomalyFilter === 'other'
          ? all.filter(a => a.kind !== 'foreshadow_unresolved' && a.kind !== 'entity_after_last')
          : all;
    wrap.innerHTML = `
      <h2>作品疑点索引 <span class="n">${all.length} 条 · 第 1–${cutoff} 章范围内</span></h2>
      <div class="home-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px">
        <div class="home-card"><div class="hc-k">高优先</div><div class="hc-v">${sev.high || 0}</div><div class="hc-n">明确冲突或高置信候选</div></div>
        <div class="home-card"><div class="hc-k">待复核</div><div class="hc-v">${sev.warning || 0}</div><div class="hc-n">需要回原文确认</div></div>
        <div class="home-card"><div class="hc-k">线索型</div><div class="hc-v">${sev.info || 0}</div><div class="hc-n">越级、别名、关系等候选</div></div>
      </div>
      <div class="fs-meta" style="margin:4px 0 12px">
        只标注，不给改稿建议。每条疑点必须带章节坐标或原文片段；点证据可跳到对应章节。
      </div>
      <div class="power-toolbar">
        <span>筛选</span>
        ${[['all','全部'],['warning','高优先/待复核'],['foreshadow','伏笔未回收'],['other','其他线索']].map(([k,n]) =>
          `<button class="power-filter${anomalyFilter === k ? ' on' : ''}" data-anomaly-filter="${k}">${n}</button>`).join('')}
      </div>
      ${filtered.length ? filtered.map(a => {
        const state = anomalyState(a.id);
        const sevCn = { high: '高优先', warning: '待复核', info: '线索' }[a.severity] || a.severity;
        const range = (() => {
          const r = a.chapter_range || [];
          if (!r.length) return '';
          return r[0] === r[r.length - 1] ? String(r[0]) : `${r[0]}–${r[r.length - 1]}`;
        })();
        const ev = (a.evidence || []).map(e =>
          `<div><button class="geo-jump" data-anomaly-ch="${escHtml(String(e.coordinate || '').replace(/^ch/i, '').split(':')[0])}">${escHtml(e.coordinate || '')}</button>
            ${escHtml(e.quote || '')}</div>`).join('');
        return `<div class="anomaly-card ${state === 'verified' ? 'verified' : ''}">
          <div class="anomaly-head">
            <span class="anomaly-sev ${escHtml(a.severity)}">${sevCn}</span>
            <span class="chip">${escHtml(a.kind_cn || a.kind)}</span>
            <span class="chip">置信 ${escHtml(a.confidence || '—')}</span>
            ${range ? `<span class="chip">第 ${escHtml(range)} 章</span>` : ''}
            ${state === 'verified' ? '<span class="chip">已核实</span>' : state === 'rejected' ? '<span class="chip">已标误报</span>' : ''}
          </div>
          <div class="ac-title">${escHtml(a.title || '')}</div>
          <div class="ac-meta">${escHtml(a.detail || '')}</div>
          <div class="ac-ev">${ev || '暂无坐标证据'}</div>
          <div class="ac-note">${escHtml(a.reader_note || '')}</div>
          <div class="ac-actions">
            <button data-anomaly-verify="${escHtml(a.id)}">标记已核实</button>
            <button data-anomaly-reject="${escHtml(a.id)}">标为误报</button>
          </div>
        </div>`;
      }).join('') : '<div class="anomaly-empty">当前进度没有可展示的疑点。继续阅读或换一本分析完整的书。</div>'}
    `;
    wrap.querySelectorAll('[data-anomaly-filter]').forEach(b => b.addEventListener('click', () => {
      anomalyFilter = b.dataset.anomalyFilter;
      renderAnomalies();
    }));
    wrap.querySelectorAll('[data-anomaly-verify]').forEach(b => b.addEventListener('click', () => setAnomalyState(b.dataset.anomalyVerify, 'verified')));
    wrap.querySelectorAll('[data-anomaly-reject]').forEach(b => b.addEventListener('click', () => setAnomalyState(b.dataset.anomalyReject, 'rejected')));
    wrap.querySelectorAll('[data-anomaly-ch]').forEach(b => b.addEventListener('click', () => {
      const n = Number(b.dataset.anomalyCh);
      const c = CHAPTERS.find(x => x.ch === n);
      if (c) showChapter(c);
    }));
  }

