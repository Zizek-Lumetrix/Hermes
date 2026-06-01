// -- Tab switching --
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'graph') loadGraph();
    else if (btn.dataset.tab === 'surprise') loadSurprise();
    else if (btn.dataset.tab === 'predictions') loadPredictions();
    else if (btn.dataset.tab === 'stream') loadStream();
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
  const height = container.clientHeight || 400;

  // Clear any previous SVG (in case of re-render)
  container.innerHTML = '';

  const svg = d3.select('#graph-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const g = svg.append('g');
  svg.call(d3.zoom().on('zoom', (e) => g.attr('transform', e.transform)));

  const simulation = d3.forceSimulation()
    .force('charge', d3.forceManyBody().strength(-100))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide(30));

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

      // Pre-resolve links: replace string source/target with node objects
      // so D3 forceLink never needs to look up IDs
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

      const sameEdges = validEdges.filter(e => e.type === 'same_domain');
      const crossEdges = validEdges.filter(e => e.type === 'cross_domain');

      const sameDomain = sameEdges.length;
      const crossDomain = crossEdges.length;
      svg.append('text').attr('x', 10).attr('y', 18)
        .attr('fill', '#888').attr('font-size', 12)
        .text(data.nodes.length + ' nodes | same-domain: ' + sameDomain + ' | cross-domain: ' + crossDomain + (crossDomain === 0 ? ' (try lower threshold)' : ''));

      const sameLink = g.selectAll('line.same')
        .data(sameEdges)
        .join('line')
        .attr('class', 'links same')
        .attr('stroke', '#4a4a4a')
        .attr('stroke-width', 1.2)
        .attr('opacity', 0.6);
      sameLink.append('title').text('同领域');

      const crossLink = g.selectAll('line.cross')
        .data(crossEdges)
        .join('line')
        .attr('class', 'links cross')
        .attr('stroke', '#ff9800')
        .attr('stroke-width', 2.5)
        .attr('stroke-dasharray', '8,4')
        .attr('opacity', 0.9);
      crossLink.append('title').text(d => '语义关联 ' + (d.strength * 100).toFixed(0) + '%');

      const color = d3.scaleOrdinal()
        .domain(['AI编程工具', '大模型安全', '网络安全', '科技产业', '中东局势', '能源安全', '气候环境', '经济金融', '地缘政治'])
        .range(['#4caf50', '#2196f3', '#00bcd4', '#e91e63', '#f44336', '#ff9800', '#8bc34a', '#ffc107', '#9c27b0']);

      const node = g.selectAll('.nodes')
        .data(data.nodes)
        .join('circle')
        .attr('class', 'nodes')
        .attr('r', d => 6 + (d.confidence || 0.5) * 10)
        .attr('fill', d => color(d.domain || 'other'))
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
        .text(d => d.label.length > 30 ? d.label.slice(0, 28) + '...' : d.label)
        .attr('font-size', 10)
        .attr('dx', 12)
        .attr('dy', 4);

      const allLinks = g.selectAll('line.links');

      simulation.nodes(data.nodes).on('tick', () => {
        allLinks.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        labels.attr('x', d => d.x).attr('y', d => d.y);
      });
      simulation.force('link', d3.forceLink(validEdges).distance(80));
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

// -- Surprise Tab --
function loadSurprise() {
  fetch('/api/surprise?limit=20')
    .then(r => r.json())
    .then(data => {
      const panel = document.getElementById('surprise-panel');
      if (!data || data.length === 0) {
        panel.innerHTML = '<p style="color:#888;padding:24px;">No high-surprise items yet. Run the pipeline to discover unexpected intelligence.</p>';
        return;
      }
      panel.innerHTML = data.map(item => {
        const analysis = safeJson(item.analysis) || {};
        const surprisePct = (item.surprise_score * 100).toFixed(0);
        const domainBadge = item.domain ? `<span class="source-tag" style="margin-left:4px;background:#2a1a1a;color:#f44336;">${item.domain}</span>` : '';
        const proposedBadge = item.domain_proposed ? `<span class="source-tag" style="margin-left:4px;background:#332200;color:#ff9800;" title="提议的新领域">提议: ${item.domain_proposed}</span>` : '';
        return `<div class="surprise-card">
          <span class="score">${surprisePct}%</span>
          <strong>${analysis.title_cn || item.title}</strong>
          <span class="source-tag" style="margin-left:8px;">${item.source}</span>
          ${domainBadge}${proposedBadge}
          <div class="analysis-section">${(analysis.summary || '').slice(0, 200)}</div>
          ${analysis.key_points && analysis.key_points.length ? `<div class="analysis-section"><strong>关键点:</strong><ul>${analysis.key_points.map(kp => `<li>${kp}</li>`).join('')}</ul></div>` : ''}
          ${analysis.implications ? `<div class="analysis-section"><strong>启示:</strong> ${analysis.implications}</div>` : ''}
          ${item.url ? `<div style="margin-top:4px;"><a href="${item.url}" target="_blank" class="source-url">${item.title}</a></div>` : ''}
        </div>`;
      }).join('');
    });
}

// -- Predictions Tab --
function loadPredictions() {
  fetch('/api/predictions?status=all')
    .then(r => r.json())
    .then(data => {
      const now = new Date();
      const pending = (data || []).filter(p => !p.backtest_result && p.deadline);
      const verified = (data || []).filter(p => p.backtest_result);

      // Pending with countdown
      const pBody = document.getElementById('pending-body');
      if (pending.length === 0) {
        pBody.innerHTML = '<tr><td colspan="3" style="color:#888;">No pending predictions.</td></tr>';
      } else {
        pBody.innerHTML = pending.map(p => {
          const deadline = new Date(p.deadline);
          const daysRemaining = Math.ceil((deadline - now) / (1000 * 60 * 60 * 24));
          const countdown = daysRemaining > 0
            ? `${daysRemaining} days`
            : daysRemaining === 0 ? 'Today' : 'Overdue';
          const cdClass = daysRemaining <= 0 ? 'countdown' : '';
          return `<tr>
            <td>${p.statement}</td>
            <td>${p.deadline}</td>
            <td class="${cdClass}">${countdown}</td>
          </tr>`;
        }).join('');
      }

      // Verified
      const vBody = document.getElementById('verified-body');
      if (verified.length === 0) {
        vBody.innerHTML = '<tr><td colspan="3" style="color:#888;">No verified predictions yet. Predictions need time to accumulate.</td></tr>';
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

// -- Confidence color --
function confidenceColor(val) {
  if (val >= 0.7) return '#4caf50';
  if (val >= 0.5) return '#ff9800';
  return '#f44336';
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

  const isConfirmed = confirmStatus === 'confirmed';
  const isChallenged = confirmStatus === 'challenged';
  html += `<div style="margin-top:20px;display:flex;gap:8px;" id="confirm-buttons">
    <button class="confirm-btn${isConfirmed ? ' confirmed-active' : ''}" id="btn-confirm" onclick="confirmConclusion('${c.id}', 'confirmed')">${isConfirmed ? '✓ 已确认' : '确认 ✓'}</button>
    <button class="confirm-btn challenge${isChallenged ? ' challenged-active' : ''}" id="btn-challenge" onclick="confirmConclusion('${c.id}', 'challenged')">${isChallenged ? '✗ 已质疑' : '质疑 ✗'}</button>
  </div>`;

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
  const clickedBtn = value === 'confirmed' ? btnConfirm : btnChallenge;
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
          const node = graphNodeData.find(n => n.id === id);
          if (node) node.user_confirmation = value;
        }
        updateGraphNodeStyles();
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

// Initial load: graph tab is active
loadGraph();
