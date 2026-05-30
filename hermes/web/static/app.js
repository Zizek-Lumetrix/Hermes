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

function openDrawer(nodeId) {
  fetch(`/api/graph/conclusion/${nodeId}`)
    .then(r => r.json())
    .then(data => {
      const c = data.conclusion;
      document.getElementById('drawer-content').innerHTML = `
        <h3>${c.statement}</h3>
        <p style="color:#888;">Domain: ${c.domain || 'none'} | Confidence: ${(c.confidence * 100).toFixed(0)}%</p>
        <p style="color:#888;">Status: ${c.status} | Confirmation: ${c.user_confirmation || 'none'}</p>
        <h4 style="margin-top:16px;">Version History</h4>
        ${data.versions.map(v => `<p style="font-size:13px;padding:4px 0;">v${v.version} (${new Date(v.created_at).toLocaleDateString()}): ${v.statement.slice(0, 60)}... [${(v.confidence * 100).toFixed(0)}%]</p>`).join('')}
        <div style="margin-top:16px;">
          <button class="confirm-btn" onclick="confirmConclusion('${c.id}', 'confirmed')">✓ Confirm</button>
          <button class="confirm-btn" onclick="confirmConclusion('${c.id}', 'challenged')">✗ Challenge</button>
        </div>
      `;
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
