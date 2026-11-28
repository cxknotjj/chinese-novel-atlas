/* Novel Atlas viewer · 版图、节奏、境界与伏笔
   职责：势力版图 / 章节节奏 / 境界表 / 伏笔 */
  /* ================= 势力版图 ================= */
  let powerOnlyOwned = false;

  function powerRowsData() {
    const tops = orgEntities.filter(o => {
      const parent = o.parent ? byId.get(o.parent) : null;
      return !parent || parent.type !== 'org';
    });
    return tops.map(o => {
      const subs = orgEntities.filter(x => x.id !== o.id && orgRootOf(x).id === o.id);
      const places = PLACES.filter(p => placeOwnerInfo(p).roots.some(r => r.id === o.id));
      const conflict = new Set(), alliance = new Set();
      D.relations.forEach(r => {
        if (r.type !== 'conflict' && r.type !== 'alliance') return;
        const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
        if (!so || !to || so.id === to.id) return;
        if (so.id === o.id) (r.type === 'conflict' ? conflict : alliance).add(to.name);
        if (to.id === o.id) (r.type === 'conflict' ? conflict : alliance).add(so.name);
      });
      const firsts = [o.first_ch, ...places.map(p => p.first_ch)].filter(x => typeof x === 'number');
      const first = firsts.length ? Math.min(...firsts) : null;
      return { org: o, subs, places, conflict: [...conflict], alliance: [...alliance], first };
    }).sort((a, b) => b.places.length - a.places.length ||
      (a.first || 9999) - (b.first || 9999) || a.org.name.localeCompare(b.org.name, 'zh'));
  }

  function renderPower() {
    const scrollTop = views.power.scrollTop;
    const rows = powerRowsData();
    const topCount = rows.length;
    const withPlaces = rows.filter(r => r.places.length).length;
    const disputed = PLACES.filter(p => placeOwnerInfo(p).disputed);
    const special = PLACES.filter(p => !placeOwnerInfo(p).roots.length && placeOwnerInfo(p).special);
    const unassigned = PLACES.filter(p => !placeOwnerInfo(p).roots.length && !placeOwnerInfo(p).special);
    const relEdges = D.relations.filter(r => {
      const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
      return so && to && so.id !== to.id && (r.type === 'conflict' || r.type === 'alliance');
    });
    const relPairs = [];
    const seenRel = new Set();
    relEdges.forEach(r => {
      const so = orgRootOf(byId.get(r.s)), to = orgRootOf(byId.get(r.t));
      const key = [r.type, ...[so.id, to.id].sort()].join('|');
      if (seenRel.has(key)) return;
      seenRel.add(key);
      relPairs.push({ type: r.type, a: so.name, b: to.name });
    });
    const visibleRows = powerOnlyOwned ? rows.filter(r => r.places.length) : rows;

    const placeChip = p => {
      const info = placeOwnerInfo(p);
      const direct = info.direct && info.roots[0] && info.direct.id !== info.roots[0].id
        ? ` · ${info.direct.name}辖` : '';
      return `<button class="power-place" data-power-place="${p.id}"
        title="${escHtml(p.desc || '')}">${escHtml(p.name)}<small>第${p.first_ch || '—'}章${escHtml(direct)}${info.disputed ? ' · 交界' : ''}</small></button>`;
    };

    views.power.innerHTML = `
      <div class="power-note">
        据点由 <b>places.attrs 的所属/所属势力/势力/门派</b> 加上 <b>parent 继承</b>得出；交界只在描述明确写「交界」时列双方；没有坐标，不做地图。
      </div>
      <div class="power-metrics">
        <div class="power-metric"><div class="v">${topCount}</div><div class="k">顶层势力</div></div>
        <div class="power-metric"><div class="v">${withPlaces}</div><div class="k">有据点记录</div></div>
        <div class="power-metric"><div class="v">${PLACES.length}</div><div class="k">地点总数</div></div>
        <div class="power-metric"><div class="v" style="color:${unassigned.length ? 'var(--danger)' : 'var(--ink)'}">${unassigned.length}</div><div class="k">未归属地点</div></div>
        <div class="power-metric"><div class="v">${disputed.length + special.length}</div><div class="k">交界/共管</div></div>
        <div class="power-metric"><div class="v">${relPairs.length}</div><div class="k">势力关系边</div></div>
      </div>
      <div class="power-toolbar">
        <span>显示</span>
        <button class="power-filter${powerOnlyOwned ? '' : ' on'}" data-power-scope="all">全部 ${topCount}</button>
        <button class="power-filter${powerOnlyOwned ? ' on' : ''}" data-power-scope="owned">仅有据点 ${withPlaces}</button>
        <span>· 无据点的势力保留为可核查的数据缺口</span>
      </div>
      <div class="power-wrap">
        <table class="power-table">
          <thead><tr><th>势力</th><th>据点</th><th>首现</th><th>档案 / 结局线索</th><th>势力关系</th></tr></thead>
          <tbody>
            ${visibleRows.map(r => `
              <tr class="${r.places.length ? '' : 'power-gap-row'}">
                <td>
                  <button class="power-org" data-power-org="${r.org.id}">${entityIcon(r.org.type, 'entity-icon-sm')}${escHtml(r.org.name)}</button>
                  ${r.subs.length ? `<span class="power-sub">下辖：${r.subs.slice(0, 4).map(x => escHtml(x.name)).join('、')}${r.subs.length > 4 ? '…' : ''}</span>` : ''}
                </td>
                <td><div class="power-places">${r.places.length ? r.places.slice().sort(byFirstCh).map(placeChip).join('') : '<span class="power-gap">未记录据点（数据缺口）</span>'}</div></td>
                <td>${r.first ? '第 ' + r.first + ' 章' : '—'}</td>
                <td><span class="power-status" title="${escHtml(r.org.desc || '')}">${escHtml((r.org.desc || '无档案').slice(0, 88))}</span></td>
                <td><div class="power-rel">
                  ${r.conflict.length ? `<span class="enemy">敌对</span>：${r.conflict.join('、')}` : ''}
                  ${r.conflict.length && r.alliance.length ? '<br>' : ''}
                  ${r.alliance.length ? `<span class="ally">同盟</span>：${r.alliance.join('、')}` : ''}
                  ${!r.conflict.length && !r.alliance.length ? '<span class="power-gap">未见同盟/敌对边</span>' : ''}
                </div></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="power-extra">
        <div class="power-extra-card">
          <h3>交界与共管（不强行归给单方）</h3>
          <div class="chips">${[...disputed, ...special].length ? [...disputed, ...special].map(p => placeChip(p)).join('') : '<span class="power-gap">无</span>'}</div>
          <p>落沙坡按描述列为七玄门/野狼帮交界；血色禁地及其子地点按「七派共管」单列。</p>
        </div>
        <div class="power-extra-card">
          <h3>未归属地点（${unassigned.length}）</h3>
          <div class="chips">${unassigned.length ? unassigned.slice().sort(byFirstCh).map(p => placeChip(p)).join('') : '<span class="power-gap">无</span>'}</div>
          <p>这些地点只有行政/地理 parent，没有可核实的势力归属；保留为数据缺口，不猜。</p>
        </div>
        <div class="power-extra-card">
          <h3>势力关系摘录</h3>
          <div class="chips">${relPairs.length ? relPairs.map(x => `<span class="geo-badge ${x.type === 'conflict' ? '' : ''}" style="border-color:${x.type === 'conflict' ? '#EBC9C4' : '#CFE0D2'};color:${x.type === 'conflict' ? 'var(--danger)' : 'var(--ok)'}">${x.type === 'conflict' ? '敌对' : '同盟'} · ${escHtml(x.a)} ↔ ${escHtml(x.b)}</span>`).join('') : '<span class="power-gap">无</span>'}</div>
          <p>来自 relations 的 alliance / conflict 边；只展示势力顶层，不把人物关系混进来。</p>
        </div>
      </div>
    `;

    views.power.querySelectorAll('[data-power-scope]').forEach(b => b.addEventListener('click', () => {
      powerOnlyOwned = b.dataset.powerScope === 'owned';
      renderPower();
    }));
    views.power.querySelectorAll('[data-power-org]').forEach(b => b.addEventListener('click', () => select(b.dataset.powerOrg)));
    views.power.querySelectorAll('[data-power-place]').forEach(b => b.addEventListener('click', () => openPlace(b.dataset.powerPlace)));
    views.power.scrollTop = scrollTop;
  }


  function svgLine() {
    if (!CHAPTERS.length) return '';
    const W = 860, H = 190, P = 34;
    const minC = CHAPTERS[0].ch, maxC = CURRENT_CH;
    const X = c => P + ((c - minC) / Math.max(maxC - minC, 1)) * (W - P * 2);
    const Y = t => H - P - t * (H - P * 2 - 8);

    let path = '';
    CHAPTERS.forEach((c, i) => {
      path += (i === 0 ? 'M' : 'L') + X(c.ch).toFixed(1) + ' ' + Y(c.tension).toFixed(1) + ' ';
    });
    const area = path + `L${X(CHAPTERS[CHAPTERS.length - 1].ch).toFixed(1)} ${Y(0)} L${X(CHAPTERS[0].ch).toFixed(1)} ${Y(0)} Z`;

    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">
      <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#A6314A" stop-opacity="0.18"/>
        <stop offset="100%" stop-color="#A6314A" stop-opacity="0"/>
      </linearGradient></defs>
      ${[0.25, 0.5, 0.75, 1].map(t => `
        <line x1="${P}" y1="${Y(t)}" x2="${W - P}" y2="${Y(t)}" stroke="#F0ECE2" stroke-width="1"/>
        <text x="${P - 8}" y="${Y(t) + 3}" font-size="9" fill="#B4B2A9" text-anchor="end">${t}</text>`).join('')}
      <path d="${area}" fill="url(#g1)"/>
      <path d="${path}" fill="none" stroke="#A6314A" stroke-width="1.6" stroke-linejoin="round"/>
      ${CHAPTERS.map(c => `
        <circle cx="${X(c.ch).toFixed(1)}" cy="${Y(c.tension).toFixed(1)}" r="3.2"
          fill="${EMOTION_COLOR[c.emotion] || '#B4B2A9'}" stroke="#fff" stroke-width="1.2">
          <title>第${c.ch}章 ${c.title} · 张力${c.tension}</title>
        </circle>`).join('')}
      <text x="${P}" y="${H - 8}" font-size="9" fill="#B4B2A9">第 1 章</text>
      <text x="${W - P}" y="${H - 8}" font-size="9" fill="#B4B2A9" text-anchor="end">第 ${CURRENT_CH} 章</text>
    </svg>`;
  }

  /* ================= 节奏 ================= */
  const CH_PAGE_SIZE = 30;
  let chPage = 0;

  function renderRhythm() {
    const hookRate = CHAPTERS.length ? CHAPTERS.filter(c => c.hook).length / CHAPTERS.length : 0;
    const avgWords = CHAPTERS.length
      ? Math.round(CHAPTERS.reduce((a, c) => a + c.words, 0) / CHAPTERS.length) : 0;
    const shuang = CHAPTERS.filter(c => c.emotion === '爽').map(c => c.ch);
    let gap = '—';
    if (shuang.length > 1) {
      const gs = [];
      for (let i = 1; i < shuang.length; i++) gs.push(shuang[i] - shuang[i - 1]);
      gs.sort((a, b) => a - b);
      gap = gs[Math.floor(gs.length / 2)] + ' 章';
    }
    const isFanqie = (D.meta.platform || '').includes('番茄');
    const hookWarn = isFanqie && hookRate < 0.8;
    const done = (D.meta.coverage && D.meta.coverage.chapters_done) || CHAPTERS.length;
    const sampled = CHAPTERS.length < done;
    const sortedCh = CHAPTERS.slice().sort((a, b) => b.tension - a.tension);
    const chPages = Math.max(1, Math.ceil(sortedCh.length / CH_PAGE_SIZE));
    chPage = Math.min(chPage, chPages - 1);
    const pageCh = sortedCh.slice(chPage * CH_PAGE_SIZE, (chPage + 1) * CH_PAGE_SIZE);

    views.rhythm.innerHTML = `
      ${sampled ? `<div class="sample-note">
        章节数据为抽样（${CHAPTERS.length} / ${done} 章），爽点间隔与钩子率仅供参考；全量分析后指标才准确。
      </div>` : ''}
      <div class="metric-row">
        <div class="metric ${hookWarn ? 'warn' : ''}">
          <div class="k">章末钩子率</div>
          <div class="v">${(hookRate * 100).toFixed(0)}%</div>
          <div class="b">${isFanqie ? '番茄基准 80%' : '起点基准 60%'}</div>
        </div>
        <div class="metric">
          <div class="k">爽点间隔</div>
          <div class="v">${gap}</div>
          <div class="b">${isFanqie ? '番茄基准 3 章' : '起点基准 10 章'}</div>
        </div>
        <div class="metric">
          <div class="k">平均章字数</div>
          <div class="v">${avgWords}</div>
          <div class="b">${isFanqie ? '番茄基准 4000' : '起点基准 6000'}</div>
        </div>
        <div class="metric">
          <div class="k">已分析章节</div>
          <div class="v">${CHAPTERS.length}</div>
          <div class="b">全书 ${D.meta.chapters} 章</div>
        </div>
      </div>

      <h2>张力曲线 <span class="n">每点一章，颜色为情绪</span></h2>
      <div class="rhythm-wrap">${svgLine()}</div>

      <h2>章节明细 <span class="n">按张力排序 · 第 ${chPage + 1} / ${chPages} 页</span></h2>
      <div class="ch-list">
        ${pageCh.map(c => `
          <div class="ch-row" data-ch="${c.ch}">
            <div class="ch-no">第 ${c.ch} 章</div>
            <div>
              <div class="ch-title">${c.title}</div>
              <div class="ch-hook">${c.hook || '无钩子'}</div>
            </div>
            <div class="ch-badge" style="color:${EMOTION_COLOR[c.emotion] || '#888'}">${c.emotion} · ${c.tension}</div>
          </div>`).join('')}
      </div>
      ${pagerHTML(sortedCh.length, chPage, CH_PAGE_SIZE, 'chpage')}
    `;
    views.rhythm.querySelectorAll('[data-ch]').forEach(row => {
      row.addEventListener('click', () => {
        const c = CHAPTERS.find(x => x.ch === +row.dataset.ch);
        if (c) showChapter(c);
      });
    });
    views.rhythm.querySelectorAll('[data-chpage]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      chPage = +b.dataset.chpage;
      renderRhythm();
      const h = [...views.rhythm.querySelectorAll('h2')].find(x => x.textContent.trim().startsWith('章节明细'));
      if (h) h.scrollIntoView({ block: 'start' });
    }));
  }

  function showChapter(c) {
    panelBody.innerHTML = `
      <h2 class="ent-name">第 ${c.ch} 章</h2>
      <div class="ent-meta">${c.title} · ${c.words} 字 · 张力 ${c.tension}</div>
      <div class="chips">
        <span class="chip" style="color:${EMOTION_COLOR[c.emotion] || '#888'}">${c.emotion}</span>
        ${c.hook_type ? `<span class="chip">钩子：${c.hook_type}</span>` : ''}
      </div>
      <p class="ent-desc">${c.summary}</p>
      ${c.hook ? `<div class="sec-title">章末钩子</div><div class="attrs">${c.hook}</div>` : ''}
      ${(c.battles || []).length ? `<div class="sec-title" style="margin-top:16px">战斗</div>
        ${c.battles.map(b => `<div class="attrs">${(byId.get(b.a || b.s) || {}).name || '未知'} vs ${(byId.get(b.b || b.t) || {}).name || '未知'}
          · 境界差 ${b.gap > 0 ? '+' : ''}${b.gap} · ${b.note}</div>`).join('')}` : ''}
    `;
    panel.classList.add('open');
    animatePanelBody();
  }

  /* ================= 境界 ================= */
  function renderRealms() {
    // 主角（关系最多者）置顶，其余按最终修为降序
    const mainId = [...deg.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    const chars = D.entities
      .filter(e => e.type === 'character' && (e.power_history || []).length)
      .sort((a, b) => {
        if (a.id === mainId) return -1;
        if (b.id === mainId) return 1;
        const pa = a.power_history[a.power_history.length - 1];
        const pb = b.power_history[b.power_history.length - 1];
        return levelNum(pb) - levelNum(pa);
      });

    const ladder = REALMS.map(r => {
      const st = r.stages || [];
      const base = realmBaseColor(r.id);
      const bars = st.length
        ? `<div class="rbar">${st.map((s, j) =>
            `<i style="background:${realmTone(r.id, st.length > 1 ? j / (st.length - 1) : 0)}" title="${s}"></i>`
          ).join('')}</div>`
        : '';
      const seen = st.length
        ? (D.entities.flatMap(e => e.power_history || []).filter(p => p.realm === r.id).length) : 0;
      return `
      <div class="realm-step" style="background:linear-gradient(135deg,${shade(base, 95)},${shade(base, 89)});border-color:${shade(base, 66)};border-left:3px solid ${shade(base, 48)}">
        <div class="rn" style="color:${shade(base, 32)}">${r.name}</div>
        <div class="rs">${st.length ? `${st.length} 个小阶` : '无细分'}${seen ? ` · ${seen} 条记录` : ''}</div>
        ${bars}
      </div>`;
    }).join('');

    const W = 800, P = 4;
    const minC = 1, maxC = CURRENT_CH;
    const X = c => P + ((c - minC) / Math.max(maxC - minC, 1)) * (W - P * 2);

    // 同一境界的相邻记录做浅→深渐变；跨境界时当前段止于已知色阶，
    // 下一段换新色相并回到浅色，避免把未证实的“巅峰”画出来。
    function realmSegFill(p, next) {
      const a = realmColorOf(p);
      if (next && next.realm === p.realm) {
        const b = realmColorOf(next);
        if (b !== a) return `linear-gradient(90deg, ${a} 0%, ${b} 100%)`;
      }
      return a;
    }

    const rows = chars.map(e => {
      const h = e.power_history;
      const segs = h.map((p, i) => {
        const from = p.ch;
        const to = (i + 1 < h.length) ? h[i + 1].ch : (e.last_ch || CURRENT_CH);
        return `<div class="gantt-seg" data-ent="${e.id}" style="left:${(X(from) / W * 100).toFixed(2)}%;
          width:${Math.max((X(to) - X(from)) / W * 100, 0.8).toFixed(2)}%;
          background:${realmSegFill(p, h[i + 1])}" title="${powerFull(p)} · 第${from}章${p.note ? ' · ' + p.note : ''}"></div>`;
      }).join('');
      const latest = h[h.length - 1];
      const isMain = e.id === mainId;
      return `<div class="gantt-row${isMain ? ' main' : ''}">
        <div class="gantt-name" data-ent="${e.id}">${e.name}${isMain ? ' ★' : ''}</div>
        <div class="gantt-track">${segs}</div>
        <div class="gantt-now">${powerFull(latest)}</div>
      </div>`;
    }).join('');

    const battles = [];
    CHAPTERS.forEach(c => (c.battles || []).forEach(b => battles.push(Object.assign({ ch: c.ch }, b))));

    views.realms.innerHTML = `
      <h2>境界阶梯 <span class="n">${REALMS.length} 级</span></h2>
      <div class="realm-ladder">${ladder}</div>

      <h2>各角色境界轨迹 <span class="n">横轴为章号</span></h2>
      <div class="gantt-note">同一境界内由浅到深；突破到下一境界后换色、重新从浅色开始。未记录到的小阶不推断为巅峰。</div>
      <div class="gantt">
        ${rows}
        <div class="gantt-axis" style="margin-left:78px">
          ${[1, 30, 60, 90, CURRENT_CH].map(c => `
            <span class="gantt-tick" style="left:${(X(c) / W * 100).toFixed(2)}%">${c}</span>`).join('')}
        </div>
      </div>

      ${battles.length ? `
      <h2>战斗记录 <span class="n">负值为越级挑战</span></h2>
      ${battles.map(b => {
        const pa = powerAtCh(b.a || b.s, b.ch), pb = powerAtCh(b.b || b.t, b.ch);
        const diff = levelNum(pa) - levelNum(pb);
        return `
        <div class="battle-row">
          <div class="ch-no" style="color:#9A9488">第 ${b.ch} 章</div>
          <div class="battle-vs">
            <span>${(byId.get(b.a || b.s) || {}).name || '未知'} <b>${powerFull(pa)}</b></span>
            <span class="vs">vs</span>
            <span>${(byId.get(b.b || b.t) || {}).name || '未知'} <b>${powerFull(pb)}</b></span>
          </div>
          <div style="color:${diff < 0 ? '#C0392B' : '#5A7A5E'}">
            ${diff < 0 ? `境界差 ${fbLayer(diff)} · 越级` : diff > 0 ? `境界差 +${fbLayer(diff)}` : '同阶'}
          </div>
        </div>`;
      }).join('')}` : ''}
    `;
    views.realms.querySelectorAll('[data-ent]').forEach(el => {
      el.addEventListener('click', () => select(el.dataset.ent));
    });
  }

  /* ================= 伏笔 ================= */
  const FS_PAGE_SIZE = 15;
  let fsPage = 0;
  let fsFilter = 'all';
  const FS_FILTER_LABEL = { all: '全部', overdue: '已超期', planted: '待回收', paid: '有回收章', dropped: '已放弃' };
  const chByCh = new Map(CHAPTERS.map(c => [c.ch, c]));

  function fsEvidence(f) {
    if (f.payoff_ch && f.payoff_ch !== f.plant_ch) {
      return {
        label: '回收章（抽取判定）', ch: f.payoff_ch,
        note: '看到第 ' + f.payoff_ch + ' 章有回收记录，正文语义仍需抽样复核'
      };
    }
    if (f.last_mention_ch && f.last_mention_ch !== f.plant_ch) {
      return {
        label: '最后提及 · 仅提及', ch: f.last_mention_ch,
        note: '之后再没出现，只能说明“又被提了一嘴”，不能视为已兑现'
      };
    }
    return { label: '无后续提及', ch: null, note: '埋下后未再出现，仍待回收或已被作者放弃' };
  }

  function fsEvidenceHTML(f) {
    const ev = fsEvidence(f);
    const c = ev.ch ? chByCh.get(ev.ch) : null;
    return `<div class="fs-evidence">
      <b>${ev.label}</b>${ev.ch ? ` · 第 ${ev.ch} 章` : ''}${c ? `《${c.title}》` : ''} · ${ev.note}
      ${c && c.summary ? `<span style="color:#A9A397">｜章节摘要：${c.summary.slice(0, 76)}</span>` : ''}
    </div>`;
  }

  function renderForeshadow() {
    const counts = { overdue: 0, planted: 0, paid: 0, dropped: 0 };
    FORESHADOWS.forEach(f => counts[fsStatus(f)]++);

    const order = { overdue: 0, planted: 1, dropped: 2, paid: 3 };
    const filtered = fsFilter === 'all'
      ? FORESHADOWS.slice()
      : FORESHADOWS.filter(f => fsStatus(f) === fsFilter);
    const sorted = filtered.sort((a, b) =>
      (order[fsStatus(a)] - order[fsStatus(b)]) || (b.importance - a.importance));
    const pages = Math.max(1, Math.ceil(sorted.length / FS_PAGE_SIZE));
    fsPage = Math.min(fsPage, pages - 1);
    const pageRows = sorted.slice(fsPage * FS_PAGE_SIZE, (fsPage + 1) * FS_PAGE_SIZE);
    const filterLabel = FS_FILTER_LABEL[fsFilter] || '全部';

    const maxC = Math.max(CURRENT_CH, ...FORESHADOWS.map(f => f.payoff_ch || 0));

    const doneTotal = (D.meta.coverage && D.meta.coverage.chapters_done) || CURRENT_CH;
    const partial = doneTotal < D.meta.chapters;
    const atCutoff = CURRENT_CH < doneTotal;
    views.foreshadow.innerHTML = `
      ${(partial || atCutoff) ? `<div class="sample-note">
        当前停在第 ${CURRENT_CH} 章${atCutoff ? `（档案已分析到第 ${doneTotal} 章，后续默认锁定）` : `（全书 ${D.meta.chapters} 章中的前 ${doneTotal} 章）`}。
        「超期」看的是<b>沉默时长</b>：距最后一次提及超过 ${FS_THRESHOLD} 章才会标红
        （阈值 = 当前进度 ${CURRENT_CH} 章 × 15%，下限 50）。
        埋得久但一直在提的主线伏笔不算超期；埋下去就再没管过的才会。
        当前进度之后的回收与提及已从视图移除。
      </div>` : ''}
      <div class="fs-summary" id="fsSummary">
        <div class="fs-stat${fsFilter === 'all' ? ' on' : ''}" data-fs-filter="all" role="button" tabindex="0">
          <div class="v">${FORESHADOWS.length}</div><div class="k">全部</div>
        </div>
        <div class="fs-stat alarm${fsFilter === 'overdue' ? ' on' : ''}" data-fs-filter="overdue" role="button" tabindex="0">
          <div class="v">${counts.overdue}</div>
          <div class="k">已超期（>${FS_THRESHOLD} 章未收）</div>
        </div>
        <div class="fs-stat${fsFilter === 'planted' ? ' on' : ''}" data-fs-filter="planted" role="button" tabindex="0">
          <div class="v">${counts.planted}</div><div class="k">待回收</div>
        </div>
        <div class="fs-stat${fsFilter === 'paid' ? ' on' : ''}" data-fs-filter="paid" role="button" tabindex="0">
          <div class="v">${counts.paid}</div><div class="k">有回收章</div>
        </div>
        <div class="fs-stat${fsFilter === 'dropped' ? ' on' : ''}" data-fs-filter="dropped" role="button" tabindex="0">
          <div class="v">${counts.dropped}</div><div class="k">已放弃</div>
        </div>
      </div>
      <div class="fs-meta" style="margin:2px 0 10px">
        判定口径：<b>有回收章</b>只认明确的回收章；只有“再次提及”仍归入待回收/超期，并单列证据；<b>无后续提及</b>表示埋下后再没出现。点上方数字卡只看该状态，点「全部」恢复。
      </div>

      <h2>伏笔台账 <span class="n">${filterLabel} · ${sorted.length} 条 · 第 ${fsPage + 1} / ${pages} 页</span></h2>
      ${pageRows.length ? pageRows.map(f => {
        const st = fsStatus(f);
        const meta = STATUS_META[st];
        const end = f.payoff_ch || CURRENT_CH;
        const leftPct = (f.plant_ch / maxC) * 100;
        const widthPct = Math.max(((end - f.plant_ch) / maxC) * 100, 1);
        const overPct = f.payoff_ch ? 0 : Math.max(((CURRENT_CH - f.plant_ch) / maxC) * 100 - widthPct, 0);
        return `
        <div class="fs-row">
          <div class="fs-head">
            <span class="fs-content">${f.content}</span>
            <span class="fs-badge" style="color:${meta.color};background:${meta.bg}">${meta.cn}</span>
          </div>
          <div class="fs-meta">
            第 ${f.plant_ch} 章埋${f.payoff_ch
              ? ` · 第 ${f.payoff_ch} 章收 · 跨 ${f.payoff_ch - f.plant_ch} 章`
              : ` · 已过 ${CURRENT_CH - f.plant_ch} 章`}${!f.payoff_ch && f.last_mention_ch
              ? ` · 最后提及第 ${f.last_mention_ch} 章（沉默 ${fsSilent(f)} 章）`
              : !f.payoff_ch ? ' · 埋下后再未提及' : ''}
            ${f.thread ? ` · 线索「${f.thread}」` : ''}
          </div>
          ${fsEvidenceHTML(f)}
          <div class="fs-bar">
            <div class="span" style="left:${leftPct}%;width:${widthPct}%;background:${meta.color}"></div>
            ${overPct > 0 && st === 'overdue' ? `<div class="over" style="left:${leftPct + widthPct}%;width:${overPct}%"></div>` : ''}
          </div>
        </div>`;
      }).join('') : `<div class="fs-empty">当前筛选下没有伏笔。点「全部」查看所有。</div>`}
      ${pagerHTML(sorted.length, fsPage, FS_PAGE_SIZE, 'fspage')}
    `;
    views.foreshadow.querySelectorAll('[data-fs-filter]').forEach(card => {
      const apply = () => {
        const next = card.dataset.fsFilter;
        if (next === fsFilter) return;
        fsFilter = next;
        fsPage = 0;
        renderForeshadow();
        views.foreshadow.scrollTop = 0;
      };
      card.addEventListener('click', apply);
      card.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); apply(); }
      });
    });
    views.foreshadow.querySelectorAll('[data-fspage]').forEach(b => b.addEventListener('click', () => {
      if (b.disabled) return;
      fsPage = +b.dataset.fspage;
      renderForeshadow();
      views.foreshadow.scrollTop = 0;
    }));
  }

