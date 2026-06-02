// == State ==
const state = {
  conclusions: [],
  domains: [],
  categories: [],
  categoryFilter: null,
  sortBy: 'created_at',
  surpriseItems: [],
  predictions: [],
  health: null,
};

function getDomainColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 55%, 50%)`;
}

// == Utilities ==
function formatTimeAgo(ts) {
  if (!ts) return '';
  const diffMs = new Date() - new Date(ts);
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay > 30) return Math.floor(diffDay / 30) + 'mo ago';
  if (diffDay > 0) return diffDay + 'd ago';
  if (diffHr > 0) return diffHr + 'h ago';
  if (diffMin > 0) return diffMin + 'm ago';
  return 'just now';
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function confidenceColor(val) {
  if (val >= 0.7) return '#4caf50';
  if (val >= 0.5) return '#ff9800';
  return '#f44336';
}

// == Dashboard ==
function loadDashboard() {
  Promise.all([
    fetch('/api/graph').then(r => r.json()).catch(() => ({ nodes: [], edges: [], domains: [] })),
    fetch('/api/surprise?limit=20').then(r => r.json()).catch(() => []),
    fetch('/api/predictions?status=all').then(r => r.json()).catch(() => []),
    fetch('/api/health').then(r => r.json()).catch(() => ({ status: 'error', message: 'connection failed' })),
    fetch('/api/categories').then(r => r.json()).catch(() => []),
  ]).then(([graphData, surpriseData, predictionsData, healthData, categoriesData]) => {
    state.conclusions = graphData.nodes || [];
    state.domains = graphData.domains || [];
    state.categories = categoriesData || [];
    state.surpriseItems = surpriseData || [];
    state.predictions = predictionsData || [];
    state.health = healthData;

    renderStats();
    renderCategoryFilter();
    renderConclusionCards();
    renderSidePanel();
  });
}

function renderStats() {
  const nodes = state.conclusions;
  const total = nodes.length;
  const reviewable = nodes.filter(n => (n.conclusion_type || 'descriptive') === 'predictive');
  const unmarked = reviewable.filter(n => !n.user_confirmation).length;
  const confirmed = reviewable.filter(n => n.user_confirmation === 'confirmed').length;
  const challenged = reviewable.filter(n => n.user_confirmation === 'challenged').length;
  const avgConf = total > 0 ? nodes.reduce((s, n) => s + (n.confidence || 0), 0) / total : 0;
  const healthOk = state.health && state.health.status === 'ok';

  const cards = [
    { value: total, sub: `${confirmed} confirmed, ${challenged} challenged`, label: 'Total Conclusions', cls: '' },
    { value: unmarked, sub: `${reviewable.length} predictive`, label: 'Needs Review', cls: unmarked > 0 ? 'attention' : '' },
    { value: confirmed, sub: `${(total > 0 ? confirmed / total * 100 : 0).toFixed(0)}% of total`, label: 'Confirmed', cls: '' },
    { value: (avgConf * 100).toFixed(0) + '%', sub: `${nodes.filter(n => n.confidence >= 0.7).length} high-confidence`, label: 'Avg Confidence', cls: '' },
    { value: healthOk ? 'OK' : 'ERR', sub: state.health ? (state.health.message || '') : 'checking...', label: 'Pipeline Health', cls: healthOk ? '' : 'warning' },
  ];

  document.getElementById('stats-bar').innerHTML = cards.map(c =>
    `<div class="stat-card ${c.cls}"><span class="stat-value">${c.value}</span><span class="stat-sub">${c.sub}</span><span class="stat-label">${c.label}</span></div>`
  ).join('');
}

function renderCategoryFilter() {
  const counts = {};
  state.conclusions.forEach(n => {
    const c = n.category || '未分类';
    counts[c] = (counts[c] || 0) + 1;
  });

  const allActive = !state.categoryFilter;
  let html = `<span class="domain-filter-label">Category:</span>`;
  html += `<span class="domain-pill${allActive ? ' active' : ''}" data-category="">All<span class="pill-count">${state.conclusions.length}</span></span>`;

  const order = ['人工智能', '科技与安全', '国际与地缘', '能源与气候', '经济与产业', '社会与治理'];
  const sorted = Object.entries(counts).sort((a, b) => {
    const ia = order.indexOf(a[0]);
    const ib = order.indexOf(b[0]);
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return b[1] - a[1];
  });

  sorted.forEach(([category, count]) => {
    const active = state.categoryFilter === category;
    html += `<span class="domain-pill${active ? ' active' : ''}" data-category="${escapeHtml(category)}">${escapeHtml(category)}<span class="pill-count">${count}</span></span>`;
  });

  document.getElementById('domain-filter').innerHTML = html;

  document.querySelectorAll('#domain-filter .domain-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const c = pill.dataset.category;
      state.categoryFilter = c || null;
      renderCategoryFilter();
      renderConclusionCards();
    });
  });
}

function renderConclusionCards() {
  let nodes = [...state.conclusions];

  if (state.categoryFilter) {
    nodes = nodes.filter(n => (n.category || '未分类') === state.categoryFilter);
  }

  if (state.sortBy === 'created_at') {
    nodes.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  } else if (state.sortBy === 'confidence') {
    nodes.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
  } else if (state.sortBy === 'confirmation') {
    const order = { undefined: 0, null: 0, challenged: 1, confirmed: 2 };
    nodes.sort((a, b) => (order[a.user_confirmation] ?? 0) - (order[b.user_confirmation] ?? 0));
  }

  const container = document.getElementById('conclusion-list');
  if (nodes.length === 0) {
    container.innerHTML = '<div class="empty-state">No conclusions match the current filter.</div>';
    return;
  }
  container.innerHTML = nodes.map(n => renderCard(n)).join('');

  container.querySelectorAll('.conclusion-card').forEach(card => {
    card.addEventListener('click', () => openDrawer(card.dataset.id));
  });
}

function conclusionTypeLabel(ctype) {
  if (ctype === 'predictive') return '预测';
  if (ctype === 'evaluative') return '评估';
  return '描述';
}

function conclusionTypeClass(node) {
  const ctype = node.conclusion_type || 'descriptive';
  if (ctype === 'predictive') {
    if (node.user_confirmation === 'confirmed') return 'confirmed';
    if (node.user_confirmation === 'challenged') return 'challenged';
    return 'unmarked';
  }
  return ctype; // 'descriptive' or 'evaluative'
}

function renderCard(node) {
  const confPct = ((node.confidence || 0) * 100).toFixed(0);
  const confColor = confidenceColor(node.confidence || 0);
  const statusClass = conclusionTypeClass(node);
  const statusLabel = conclusionTypeLabel(node.conclusion_type || 'descriptive');
  const domainLabel = node.domain || '';
  const domainColor = getDomainColor(domainLabel);
  const categoryLabel = node.category || '';
  const timeAgo = formatTimeAgo(node.created_at);
  const versionInfo = node.version_count > 1 ? ` · v${node.version_count}` : '';

  let domainHtml = '';
  if (categoryLabel) {
    domainHtml += `<span class="card-domain-tag" style="border-color:#888;color:#aaa;font-size:10px;">${escapeHtml(categoryLabel)}</span>`;
  }
  if (domainLabel) {
    domainHtml += `<span class="card-domain-tag" style="border-color:${domainColor};color:${domainColor};">${escapeHtml(domainLabel)}</span>`;
  }

  return `<div class="conclusion-card ${statusClass}" data-id="${escapeHtml(node.id)}">
    <div class="card-statement">${escapeHtml(node.label)}</div>
    <div class="card-meta">
      ${domainHtml}
      <span class="card-confidence">
        <span class="confidence-bar"><span class="confidence-fill" style="width:${confPct}%;background:${confColor};"></span></span>
        ${confPct}%
      </span>
      <span class="card-type-tag ${statusClass}">${statusLabel}</span>
      <span class="card-version">${versionInfo}</span>
      <span class="card-time">${timeAgo}</span>
    </div>
  </div>`;
}

function renderSidePanel() {
  const healthOk = state.health && state.health.status === 'ok';
  const topSurprises = state.surpriseItems.slice(0, 5);
  const pendingPreds = state.predictions.filter(p => !p.backtest_result && p.deadline);
  const verifiedPreds = state.predictions.filter(p => p.backtest_result);

  let html = '';

  // Pipeline status
  html += `<div class="side-section"><h3>Pipeline</h3>`;
  html += `<div class="side-stat"><span>Health</span><span class="ss-val ${healthOk ? 'health-ok' : 'health-err'}">${healthOk ? 'OK' : 'Error'}</span></div>`;
  html += `<div class="side-stat"><span>Conclusions</span><span class="ss-val">${state.conclusions.length}</span></div>`;
  html += `<div class="side-stat"><span>Domains</span><span class="ss-val">${state.domains.length}</span></div>`;
  html += `</div>`;

  // Top surprises
  html += `<div class="side-section"><h3>Top Surprises</h3>`;
  if (topSurprises.length === 0) {
    html += `<div class="side-item"><div class="si-title">No high-surprise items yet.</div></div>`;
  } else {
    topSurprises.forEach(item => {
      const analysis = safeJson(item.analysis) || {};
      const pct = ((item.surprise_score || 0) * 100).toFixed(0);
      html += `<div class="side-item"><div class="si-title">${escapeHtml((analysis.title_cn || item.title || '').slice(0, 60))}</div><div class="si-meta">surprise ${pct}% · ${escapeHtml(item.domain || '')}</div></div>`;
    });
  }
  html += `</div>`;

  // Prediction summary
  html += `<div class="side-section"><h3>Predictions</h3>`;
  html += `<div class="side-stat"><span>Pending</span><span class="ss-val">${pendingPreds.length}</span></div>`;
  html += `<div class="side-stat"><span>Verified</span><span class="ss-val">${verifiedPreds.length}</span></div>`;
  const correct = verifiedPreds.filter(p => p.backtest_result === 'correct').length;
  if (verifiedPreds.length > 0) {
    html += `<div class="side-stat"><span>Accuracy</span><span class="ss-val">${(correct / verifiedPreds.length * 100).toFixed(0)}%</span></div>`;
  }
  html += `</div>`;

  document.getElementById('side-panel').innerHTML = html;
}

// -- Tab switching --
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'dashboard') loadDashboard();
    else if (btn.dataset.tab === 'graph') loadGraph();
    else if (btn.dataset.tab === 'predictions') loadPredictions();
    else if (btn.dataset.tab === 'stream') loadStream();
  });
});

// -- Sort buttons --
document.querySelectorAll('.sort-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.sortBy = btn.dataset.sort;
    renderConclusionCards();
  });
});

// -- Toast --
function showToast(msg, type) {
  const el = document.getElementById('confirm-toast');
  el.textContent = msg;
  el.className = type + ' show';
  clearTimeout(el._timeout);
  el._timeout = setTimeout(() => { el.className = ''; }, 2500);
}

// -- Knowledge Graph --
let graphLoaded = false;
let graphLoading = false;
let graphSimulation = null;
let graphNodeData = null;
let graphSvg = null;

function updateGraphNodeStyles() {
  if (!graphSvg || !graphNodeData) return;
  graphSvg.selectAll('circle.nodes')
    .attr('stroke', d => {
      if (d.user_confirmation === 'confirmed') return '#4caf50';
      if (d.user_confirmation === 'challenged') return '#f44336';
      return 'none';
    })
    .attr('stroke-width', d => d.user_confirmation ? 3 : 0);
}

function loadGraph() {
  if (graphLoaded || graphLoading) return;
  graphLoading = true;

  const container = document.getElementById('graph-container');
  const width = container.clientWidth;
  const height = container.clientHeight || 600;

  container.innerHTML = '';

  const svg = d3.select('#graph-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.3, 3]).on('zoom', (e) => g.attr('transform', e.transform)));

  const color = d3.scaleOrdinal()
    .domain(['AI编程工具', '大模型安全', '网络安全', '科技产业', '中东局势', '能源安全', '气候环境', '经济金融', '地缘政治'])
    .range(['#4caf50', '#2196f3', '#00bcd4', '#e91e63', '#f44336', '#ff9800', '#8bc34a', '#ffc107', '#9c27b0']);

  fetch('/api/graph')
    .then(r => r.json())
    .then(data => {
      if (!data.nodes || data.nodes.length === 0) {
        svg.append('text').attr('x', width/2).attr('y', height/2)
          .attr('text-anchor', 'middle').attr('fill', '#888')
          .text('No conclusions yet. Run the pipeline to build your knowledge graph.');
        graphLoaded = true;
        graphLoading = false;
        return;
      }

      graphLoaded = true;
      graphLoading = false;
      graphNodeData = data.nodes;
      graphSvg = svg;

      // Pre-resolve edge node references
      const nodeById = {};
      data.nodes.forEach(n => { nodeById[n.id] = n; });
      const resolvedEdges = data.edges.map(e => ({
        ...e,
        source: nodeById[e.source] || e.source,
        target: nodeById[e.target] || e.target,
      }));
      const validEdges = resolvedEdges.filter(e =>
        typeof e.source === 'object' && typeof e.target === 'object'
      );

      // Build domain → center position map for grouping forces
      const domains = data.domains || [];
      const domainCenters = {};
      const margin = 140;
      const usableW = width - margin * 2;
      const usableH = height - margin * 2;
      const cols = Math.ceil(Math.sqrt(domains.length));
      const rows = Math.ceil(domains.length / cols);
      domains.forEach((d, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        domainCenters[d] = {
          x: margin + usableW * (col + 0.5) / cols,
          y: margin + usableH * (row + 0.5) / rows,
        };
      });

      // Add legend
      const legendHtml = domains.map(d =>
        `<div class="legend-item"><span class="legend-swatch" style="background:${color(d)};"></span>${d}</div>`
      ).join('');
      const legendDiv = document.createElement('div');
      legendDiv.id = 'graph-legend';
      legendDiv.innerHTML = legendHtml;
      container.appendChild(legendDiv);

      // Info text
      svg.append('text').attr('x', 10).attr('y', 18)
        .attr('fill', '#888').attr('font-size', 12)
        .text(data.nodes.length + ' conclusions, ' + validEdges.length + ' cross-domain links');

      // Cross-domain edges only
      const crossLink = g.selectAll('line.cross')
        .data(validEdges)
        .join('line')
        .attr('class', 'links cross')
        .attr('stroke', '#ff9800')
        .attr('stroke-width', d => 1 + d.strength * 3)
        .attr('stroke-dasharray', '6,3')
        .attr('opacity', 0.5);
      crossLink.append('title').text(d => '语义关联 ' + (d.strength * 100).toFixed(0) + '%');

      const node = g.selectAll('.nodes')
        .data(data.nodes)
        .join('circle')
        .attr('class', 'nodes')
        .attr('r', d => 8 + (d.confidence || 0.5) * 12)
        .attr('fill', d => color(d.domain || 'other'))
        .attr('stroke', '#fff')
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.9)
        .call(d3.drag()
          .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
          .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

      node.on('click', (e, d) => openDrawer(d.id));
      node.append('title').text(d => d.label);

      const labels = g.selectAll('.node-label')
        .data(data.nodes)
        .join('text')
        .attr('class', 'node-label')
        .text(d => d.label.length > 35 ? d.label.slice(0, 33) + '...' : d.label)
        .attr('font-size', 11)
        .attr('dx', 14)
        .attr('dy', 4);

      const simulation = d3.forceSimulation(data.nodes)
        .force('charge', d3.forceManyBody().strength(-500))
        .force('collision', d3.forceCollide(d => 16 + (d.confidence || 0.5) * 14))
        .force('link', d3.forceLink(validEdges).distance(120).strength(0.3))
        .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
        .force('x', d3.forceX(d => {
          const c = domainCenters[d.domain];
          return c ? c.x : width / 2;
        }).strength(0.15))
        .force('y', d3.forceY(d => {
          const c = domainCenters[d.domain];
          return c ? c.y : height / 2;
        }).strength(0.15))
        .on('tick', () => {
          crossLink.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
              .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
          node.attr('cx', d => d.x).attr('cy', d => d.y);
          labels.attr('x', d => d.x).attr('y', d => d.y);
        });

      simulation.alpha(1).restart();
      graphSimulation = simulation;
      updateGraphNodeStyles();
    })
    .catch((err) => {
      console.error('Graph load error:', err);
      svg.append('text').attr('x', width/2).attr('y', height/2)
        .attr('text-anchor', 'middle').attr('fill', '#f44336')
        .text('数据库连接失败，请检查数据库是否运行');
      svg.append('text').attr('x', width/2).attr('y', height/2 + 24)
        .attr('text-anchor', 'middle').attr('fill', '#888').attr('font-size', 12)
        .text(err.message || '');
      graphLoading = false;
    });
}

// -- Predictions Tab --
function loadPredictions() {
  fetch('/api/predictions?status=all')
    .then(r => r.json())
    .then(data => {
      const now = new Date();
      const active = (data || []).filter(p => !p.backtest_result && p.deadline && new Date(p.deadline) > now);
      const needsVerify = (data || []).filter(p => !p.backtest_result && p.deadline && new Date(p.deadline) <= now);
      const verified = (data || []).filter(p => p.backtest_result);

      // Active with countdown
      const pBody = document.getElementById('pending-body');
      if (active.length === 0) {
        pBody.innerHTML = '<tr><td colspan="3" style="color:#888;">No active predictions.</td></tr>';
      } else {
        pBody.innerHTML = active.map(p => {
          const deadline = new Date(p.deadline);
          const daysRemaining = Math.ceil((deadline - now) / (1000 * 60 * 60 * 24));
          return `<tr>
            <td>${p.statement}</td>
            <td>${p.deadline}</td>
            <td>${daysRemaining} day${daysRemaining !== 1 ? 's' : ''}</td>
          </tr>`;
        }).join('');
      }

      // Needs Verification
      const nBody = document.getElementById('needs-verify-body');
      if (needsVerify.length === 0) {
        nBody.innerHTML = '<tr><td colspan="3" style="color:#888;">All caught up.</td></tr>';
      } else {
        nBody.innerHTML = needsVerify.map(p => {
          return `<tr id="pred-row-${p.id}">
            <td>${p.statement}</td>
            <td><span class="countdown">${p.deadline}</span></td>
            <td>
              <button class="verify-btn" data-id="${p.id}" data-result="correct" style="color:#4caf50;">Correct</button>
              <button class="verify-btn" data-id="${p.id}" data-result="partially_correct" style="color:#ffc107;">Partially</button>
              <button class="verify-btn" data-id="${p.id}" data-result="incorrect" style="color:#f44336;">Incorrect</button>
              <button class="verify-btn" data-id="${p.id}" data-result="unverifiable" style="color:#888;">Unverifiable</button>
            </td>
          </tr>`;
        }).join('');
      }

      // Verified
      const vBody = document.getElementById('verified-body');
      if (verified.length === 0) {
        vBody.innerHTML = '<tr><td colspan="3" style="color:#888;">No verified predictions yet.</td></tr>';
      } else {
        vBody.innerHTML = verified.map(p => {
          const resultClass = `result-${p.backtest_result}`;
          return `<tr>
            <td>${p.statement}</td>
            <td>${p.deadline}</td>
            <td class="${resultClass}">${p.backtest_result}</td>
          </tr>`;
        }).join('');
      }

      // Attach verify button handlers
      document.querySelectorAll('.verify-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const predId = btn.dataset.id;
          const result = btn.dataset.result;
          const row = document.getElementById('pred-row-' + predId);
          btn.disabled = true;
          btn.textContent = '...';
          fetch(`/api/predictions/${predId}/verify?result=${result}`, { method: 'POST' })
            .then(r => r.json())
            .then(resp => {
              if (resp.status === 'ok') {
                if (row) row.remove();
                showToast('Prediction verified as ' + result.replace(/_/g, ' '), 'success');
              } else {
                btn.disabled = false;
                btn.textContent = result;
                showToast(resp.error || 'Verification failed', 'error');
              }
            })
            .catch(() => {
              btn.disabled = false;
              btn.textContent = result;
            });
        });
      });
    });
}

// -- Activity Stream --
function loadStream() {
  fetch('/api/stream?limit=30')
    .then(r => r.json())
    .then(data => {
      const container = document.getElementById('stream-entries');
      if (!data.entries || data.entries.length === 0) {
        container.innerHTML = '<p style="color:#888;padding:24px;">No pipeline runs yet.</p>';
        return;
      }
      container.innerHTML = data.entries.map(e => {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleString() : '';
        const statusClass = e.status === 'ok' ? '#4caf50' : e.status === 'error' ? '#f44336' : '#ffc107';
        return `<div style="padding:6px 0;border-bottom:1px solid #1a1a1a;font-size:13px;">
          <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin-right:8px;background:#2a2a2a;color:${statusClass};">${e.stage}</span>
          ${e.status} | ${e.item_count} items
          <span style="color:#666;float:right;">${ts}</span>
        </div>`;
      }).join('');
    });
}

// -- Evidence Drawer --
function renderEvidence(conclusionData) {
  const c = conclusionData.conclusion;
  const items = conclusionData.items || [];
  const versions = conclusionData.versions || [];
  const confPct = (c.confidence * 100).toFixed(0);
  const confColor = confidenceColor(c.confidence);

  const itemConfs = items.map(i => {
    const a = safeJson(i.analysis) || {};
    return a.confidence || 'medium';
  });
  const highCount = itemConfs.filter(x => x === 'high').length;
  const medCount = itemConfs.filter(x => x === 'medium').length;
  const lowCount = itemConfs.filter(x => x === 'low').length;

  const confirmStatus = c.user_confirmation;
  const confirmLabel = confirmStatus === 'confirmed' ? '已确认 ✓' : confirmStatus === 'challenged' ? '已质疑 ✗' : '未标记';
  const confirmBadgeClass = confirmStatus === 'confirmed' ? 'confirmed' : confirmStatus === 'challenged' ? 'challenged' : 'unmarked';

  let html = `
    <h3 style="margin-bottom:4px;">${c.statement}</h3>
    <p class="meta">领域: ${c.domain || '未知'} | 状态: ${c.status} <span class="confirmation-badge ${confirmBadgeClass}">${confirmLabel}</span></p>
    <div style="margin:8px 0;padding:8px 12px;background:#222;border-radius:6px;border-left:4px solid ${confColor};">
      <span style="font-size:24px;font-weight:bold;color:${confColor};">${confPct}%</span>
      <span style="color:#888;font-size:13px;margin-left:8px;">
        基于 ${items.length} 篇文章:
        ${highCount ? highCount + '篇高可靠 ' : ''}${medCount ? medCount + '篇中等 ' : ''}${lowCount ? lowCount + '篇低可靠' : ''}
      </span>
    </div>
`;

  if (conclusionData.counter_evidence) {
    html += `<div style="margin:8px 0;padding:8px 12px;background:#2a1a1a;border-radius:6px;border-left:4px solid #f44336;">
      <strong style="color:#f44336;">反对意见</strong>
      <div style="margin-top:4px;color:#ccc;">${conclusionData.counter_evidence}</div>
    </div>`;
  }

  if (versions.length > 1) {
    const trendValues = versions.map(v => (v.confidence * 100).toFixed(0));
    html += `<div style="margin-top:4px;font-size:13px;color:#aaa;">`
      + `Trend: ${trendValues.join(' → ')}%</div>`;
  }
  if (versions.length > 0) {
    html += `<details style="margin-top:12px;" open><summary>版本历史 (${versions.length})</summary>`;
    versions.forEach(v => {
      const d = new Date(v.created_at).toLocaleDateString();
      html += `<div class="version-line">`;
      html += `<strong>v${v.version} [${d}]</strong> ${(v.confidence * 100).toFixed(0)}%`;
      html += `</div>`;
    });
    html += `</details>`;
  }

  html += `<h4 style="margin-top:20px;border-top:1px solid #333;padding-top:12px;">直接证据 (${items.length})</h4>`;

  if (items.length === 0) {
    html += `<p class="meta">暂无直接关联文章</p>`;
  } else {
    items.forEach((item, idx) => {
      const analysis = safeJson(item.analysis) || {};
      const entities = safeJson(item.entities) || [];

      html += `<div class="evidence-card">`;
      html += `<div class="evidence-header">`;
      html += `<strong>${idx + 1}. ${analysis.title_cn || item.title}</strong>`;
      html += ` <span class="source-tag">${item.source}</span>`;
      if (item.domain_proposed) {
        html += ` <span class="source-tag" style="background:#332200;color:#ff9800;" title="提议的新领域">提议: ${item.domain_proposed}</span>`;
      }
      html += `</div>`;

      if (item.url) {
        html += `<div><a href="${item.url}" target="_blank" class="source-url">查看原文</a></div>`;
      }
      if (analysis.summary) {
        html += `<div class="analysis-section"><strong>分析摘要:</strong> ${analysis.summary}</div>`;
      }
      if (analysis.key_points && analysis.key_points.length) {
        html += `<div class="analysis-section"><strong>关键质疑:</strong><ul>`;
        analysis.key_points.forEach(kp => { html += `<li>${kp}</li>`; });
        html += `</ul></div>`;
      }
      if (analysis.implications) {
        html += `<div class="analysis-section"><strong>启示:</strong> ${analysis.implications}</div>`;
      }
      if (entities.length) {
        const entLabels = entities.map(e => `${e.name} (${e.type})`).join(', ');
        html += `<div class="analysis-section"><strong>实体:</strong> ${entLabels}</div>`;
      }
      html += `</div>`;
    });
  }

  const relatedItems = conclusionData.related_items || [];
  html += `<h4 style="margin-top:20px;border-top:1px solid #333;padding-top:12px;">同领域相关文章 (${relatedItems.length})</h4>`;

  if (relatedItems.length === 0) {
    html += `<p class="meta">暂无同领域相关文章</p>`;
  } else {
    relatedItems.forEach((item, idx) => {
      const analysis = safeJson(item.analysis) || {};
      html += `<div class="evidence-card" style="opacity:0.8;">`;
      html += `<div class="evidence-header">`;
      html += `<strong>${idx + 1}. ${analysis.title_cn || item.title}</strong>`;
      html += ` <span class="source-tag">${item.source}</span>`;
      html += ` <span class="source-tag" style="margin-left:4px;background:#2a1a1a;color:#ff9800;">${item.domain || ''}</span>`;
      html += `</div>`;
      if (item.url) {
        html += `<div><a href="${item.url}" target="_blank" class="source-url">查看原文</a></div>`;
      }
      if (analysis.summary) {
        html += `<div class="analysis-section">${analysis.summary.slice(0, 150)}</div>`;
      }
      html += `</div>`;
    });
  }

  const ctype = c.conclusion_type || 'descriptive';
  if (ctype === 'predictive') {
    const isConfirmed = confirmStatus === 'confirmed';
    const isChallenged = confirmStatus === 'challenged';
    html += `<div style="margin-top:20px;display:flex;gap:8px;" id="confirm-buttons">
      <button class="confirm-btn${isConfirmed ? ' confirmed-active' : ''}" id="btn-confirm" onclick="confirmConclusion('${c.id}', 'confirmed')">${isConfirmed ? '✓ 已确认' : '确认 ✓'}</button>
      <button class="confirm-btn challenge${isChallenged ? ' challenged-active' : ''}" id="btn-challenge" onclick="confirmConclusion('${c.id}', 'challenged')">${isChallenged ? '✗ 已质疑' : '质疑 ✗'}</button>
    </div>`;
  } else if (ctype === 'evaluative') {
    const isUseful = confirmStatus === 'confirmed';
    const isDisagree = confirmStatus === 'challenged';
    html += `<div style="margin-top:20px;display:flex;gap:8px;" id="confirm-buttons">
      <button class="confirm-btn${isUseful ? ' confirmed-active' : ''}" id="btn-confirm" onclick="confirmConclusion('${c.id}', 'confirmed')">${isUseful ? '✓ 有用' : '有用 ✓'}</button>
      <button class="confirm-btn challenge${isDisagree ? ' challenged-active' : ''}" id="btn-challenge" onclick="confirmConclusion('${c.id}', 'challenged')">${isDisagree ? '✗ 不认同' : '不认同 ✗'}</button>
    </div>`;
  }

  return html;
}

function safeJson(v) {
  if (!v) return null;
  if (typeof v === 'object') return v;
  try { return JSON.parse(v); } catch(e) { return null; }
}

function openDrawer(nodeId) {
  fetch(`/api/graph/conclusion/${nodeId}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert(data.error); return; }
      document.getElementById('drawer-content').innerHTML = renderEvidence(data);
      document.getElementById('drawer').classList.add('open');
    });
}

function confirmConclusion(id, value) {
  const btnConfirm = document.getElementById('btn-confirm');
  const btnChallenge = document.getElementById('btn-challenge');
  const label = value === 'confirmed' ? '确认' : '质疑';

  if (btnConfirm) { btnConfirm.disabled = true; btnConfirm.textContent = value === 'confirmed' ? '保存中...' : btnConfirm.textContent; }
  if (btnChallenge) { btnChallenge.disabled = true; btnChallenge.textContent = value === 'challenged' ? '保存中...' : btnChallenge.textContent; }

  fetch(`/api/graph/conclusion/${id}/confirm?value=${value}`, { method: 'POST' })
    .then(r => {
      if (!r.ok) throw new Error('API error ' + r.status);
      return r.json();
    })
    .then(data => {
      if (data.status === 'ok') {
        // Update graph node data and re-style
        if (graphNodeData) {
          const gnode = graphNodeData.find(n => n.id === id);
          if (gnode) gnode.user_confirmation = value;
        }
        updateGraphNodeStyles();

        // Update dashboard state and re-render
        if (state.conclusions.length > 0) {
          const dnode = state.conclusions.find(n => n.id === id);
          if (dnode) dnode.user_confirmation = value;
          renderStats();
          renderConclusionCards();
        }

        showToast(label + '已保存', 'success');
        openDrawer(id);
      } else {
        showToast('保存失败: ' + (data.error || 'unknown'), 'error');
        openDrawer(id);
      }
    })
    .catch(err => {
      showToast('网络错误，请重试', 'error');
      openDrawer(id);
    });
}

document.getElementById('drawer-close').addEventListener('click', () => {
  document.getElementById('drawer').classList.remove('open');
});

// -- Initial load --
loadDashboard();
