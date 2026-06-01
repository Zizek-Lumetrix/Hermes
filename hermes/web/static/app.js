const width = document.getElementById('graph-container').clientWidth;
const height = document.getElementById('graph-container').clientHeight;

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

function loadGraph() {
  fetch('/api/graph')
    .then(r => r.json())
    .then(data => {
      if (!data.nodes || data.nodes.length === 0) {
        svg.append('text').attr('x', width/2).attr('y', height/2)
          .attr('text-anchor', 'middle').attr('fill', '#888')
          .text('No conclusions yet. Run the pipeline to build your knowledge graph.');
        return;
      }

      const link = g.selectAll('.links')
        .data(data.edges)
        .join('line')
        .attr('class', 'links')
        .attr('stroke-width', 1);

      const color = d3.scaleOrdinal()
        .domain(['AI', '能源安全', '中东局势', '地缘政治', '大模型安全', 'AI编程工具'])
        .range(['#4caf50', '#ff9800', '#f44336', '#9c27b0', '#2196f3', '#00bcd4']);

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

      // Labels
      const labels = g.selectAll('.node-label')
        .data(data.nodes)
        .join('text')
        .attr('class', 'node-label')
        .text(d => d.label.length > 30 ? d.label.slice(0, 28) + '...' : d.label)
        .attr('font-size', 10)
        .attr('dx', 12)
        .attr('dy', 4);

      simulation.nodes(data.nodes).on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        labels.attr('x', d => d.x).attr('y', d => d.y);
      });
      simulation.force('link', d3.forceLink(data.edges).distance(80));
      simulation.alpha(1).restart();
    });
}

function loadStream() {
  fetch('/api/stream?limit=20')
    .then(r => r.json())
    .then(data => {
      const container = document.getElementById('stream-entries');
      if (!data.entries || data.entries.length === 0) {
        container.innerHTML = '<div class="stream-entry">No updates yet. Run the pipeline to see results.</div>';
        return;
      }
      container.innerHTML = data.entries.map(e => {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleString() : '';
        return `<div class="stream-entry">
          <span class="type type-pipeline">${e.stage}</span>
          ${e.status} | ${e.item_count} items
          <span style="color:#888;float:right;">${ts}</span>
        </div>`;
      }).join('');
    });
}

function loadPredictions() {
  fetch('/api/predictions?status=all')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('scorecard-body');
      if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3">No predictions yet.</td></tr>';
        return;
      }
      tbody.innerHTML = data.map(p => `
        <tr>
          <td>${p.statement}</td>
          <td>${p.deadline}</td>
          <td>${p.backtest_result || '<em>pending</em>'}</td>
        </tr>
      `).join('');
    });
}

function confidenceColor(val) {
  if (val >= 0.7) return '#4caf50';
  if (val >= 0.5) return '#ff9800';
  return '#f44336';
}

function renderEvidence(conclusionData) {
  const c = conclusionData.conclusion;
  const items = conclusionData.items || [];
  const versions = conclusionData.versions || [];
  const confPct = (c.confidence * 100).toFixed(0);
  const confColor = confidenceColor(c.confidence);

  // Compute confidence breakdown
  const itemConfs = items.map(i => {
    const a = safeJson(i.analysis) || {};
    return a.confidence || 'medium';
  });
  const highCount = itemConfs.filter(x => x === 'high').length;
  const medCount = itemConfs.filter(x => x === 'medium').length;
  const lowCount = itemConfs.filter(x => x === 'low').length;

  let html = `
    <h3 style="margin-bottom:4px;">${c.statement}</h3>
    <p class="meta">领域: ${c.domain || '未知'} | 状态: ${c.status}</p>
    <div style="margin:8px 0;padding:8px 12px;background:#222;border-radius:6px;border-left:4px solid ${confColor};">
      <span style="font-size:24px;font-weight:bold;color:${confColor};">${confPct}%</span>
      <span style="color:#888;font-size:13px;margin-left:8px;">
        基于 ${items.length} 篇文章:
        ${highCount ? highCount + '篇高可靠 ' : ''}${medCount ? medCount + '篇中等 ' : ''}${lowCount ? lowCount + '篇低可靠' : ''}
      </span>
    </div>
    <p class="meta">确认: ${c.user_confirmation || '未标记'}</p>
  `;

  // Confidence trend
  if (versions.length > 1) {
    const trendValues = versions.map(v => (v.confidence * 100).toFixed(0));
    html += `<div style="margin-top:4px;font-size:13px;color:#aaa;">`
      + `Trend: ${trendValues.join(' → ')}%</div>`;
  }
  if (versions.length > 0) {
    html += `<details style="margin-top:12px;" open><summary>版本历史 (${versions.length})</summary>`;
    versions.forEach(v => {
      const d = new Date(v.created_at).toLocaleDateString();
      const desc = v.change_description || '';
      html += `<div class="version-line">`;
      html += `<strong>v${v.version} [${d}]</strong> ${(v.confidence * 100).toFixed(0)}%`;
      if (desc) html += `<div style="margin-top:4px;color:#bbb;line-height:1.5;">${desc}</div>`;
      html += `</div>`;
    });
    html += `</details>`;
  }

  // Supporting evidence
  const relatedItems = conclusionData.related_items || [];
  html += `<h4 style="margin-top:20px;border-top:1px solid #333;padding-top:12px;">直接证据 (${items.length})</h4>`;

  if (items.length === 0) {
    html += `<p class="meta">暂无直接关联文章</p>`;
  } else {
    items.forEach((item, idx) => {
      const analysis = safeJson(item.analysis) || {};
      const entities = safeJson(item.entities) || [];
      const confidenceLabel = analysis.confidence === 'high' ? '🟢' : analysis.confidence === 'medium' ? '🟡' : '';

      html += `<div class="evidence-card">`;
      html += `<div class="evidence-header">`;
      html += `<strong>${idx + 1}. ${analysis.title_cn || item.title}</strong>`;
      html += ` <span class="source-tag">${item.source}</span>`;
      if (confidenceLabel) html += ` <span>${confidenceLabel}</span>`;
      html += `</div>`;

      if (item.url) {
        html += `<div><a href="${item.url}" target="_blank" class="source-url">${item.title}</a></div>`;
      }

      // LLM critical analysis
      if (analysis.summary) {
        html += `<div class="analysis-section"><strong>分析摘要:</strong> ${analysis.summary}</div>`;
      }

      // Key points (source quality flags)
      if (analysis.key_points && analysis.key_points.length) {
        html += `<div class="analysis-section"><strong>关键质疑:</strong><ul>`;
        analysis.key_points.forEach(kp => { html += `<li>${kp}</li>`; });
        html += `</ul></div>`;
      }

      // Implications
      if (analysis.implications) {
        html += `<div class="analysis-section"><strong>启示:</strong> ${analysis.implications}</div>`;
      }

      // Entities
      if (entities.length) {
        const entLabels = entities.map(e => `${e.name} (${e.type})`).join(', ');
        html += `<div class="analysis-section"><strong>实体:</strong> ${entLabels}</div>`;
      }

      html += `</div>`;
    });
  }

  // Related items (same domain, broader context)
  if (relatedItems.length > 0) {
    html += `<details style="margin-top:16px;"><summary>同领域相关文章 (${relatedItems.length})</summary>`;
    relatedItems.forEach((item, idx) => {
      const analysis = safeJson(item.analysis) || {};
      html += `<div class="evidence-card" style="border-left-color:#555;">`;
      html += `<div class="evidence-header">${idx + 1}. ${analysis.title_cn || item.title} <span class="source-tag">${item.source}</span></div>`;
      if (analysis.summary) html += `<div class="analysis-section">${analysis.summary.slice(0, 150)}...</div>`;
      if (item.url) html += `<div><a href="${item.url}" target="_blank" class="source-url">查看原文</a></div>`;
      html += `</div>`;
    });
    html += `</details>`;
  }

  // Confirm / Challenge buttons
  html += `<div style="margin-top:20px;display:flex;gap:8px;">
    <button class="confirm-btn" onclick="confirmConclusion('${c.id}', 'confirmed')">确认 ✓</button>
    <button class="confirm-btn challenge" onclick="confirmConclusion('${c.id}', 'challenged')">质疑 ✗</button>
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
  fetch(`/api/graph/conclusion/${id}/confirm?value=${value}`, { method: 'POST' })
    .then(r => r.json())
    .then(() => openDrawer(id));
}

document.getElementById('drawer-close').addEventListener('click', () => {
  document.getElementById('drawer').classList.remove('open');
});

loadGraph();
loadStream();
loadPredictions();
