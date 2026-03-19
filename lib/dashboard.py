"""Generate self-contained HTML dashboard for memory metrics."""

import json


def generate_dashboard(data):
    """Generate a single-file HTML dashboard with Chart.js charts.

    Args:
        data: Dict from metrics.query_report(), enriched with per-session injections.

    Returns:
        Complete HTML string.
    """
    if not data:
        return _empty_html()

    sessions_json = json.dumps(data.get("sessions", []))
    daily_tokens_json = json.dumps(data.get("daily_tokens", []))
    daily_relevance_json = json.dumps(data.get("daily_relevance", []))
    layers_json = json.dumps(data.get("layers", []))
    relevance_json = json.dumps(data.get("relevance", {}))
    top_citations_json = json.dumps(data.get("top_citations", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Memory Metrics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
       background: #0d1117; color: #c9d1d9; padding: 20px; }}
h1 {{ color: #58a6ff; margin-bottom: 4px; font-size: 24px; }}
.subtitle {{ color: #8b949e; margin-bottom: 24px; font-size: 14px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
.card h2 {{ color: #58a6ff; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;
            margin-bottom: 12px; }}
.stat {{ font-size: 32px; font-weight: bold; color: #f0f6fc; }}
.stat-label {{ font-size: 12px; color: #8b949e; margin-top: 2px; }}
.stat-row {{ display: flex; gap: 24px; margin-bottom: 8px; }}
.stat-item {{ flex: 1; }}
.chart-container {{ position: relative; height: 250px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 2px solid #30363d; color: #8b949e;
      cursor: pointer; user-select: none; }}
th:hover {{ color: #58a6ff; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; }}
tr:hover {{ background: #1c2128; }}
tr.expandable {{ cursor: pointer; }}
.detail-row {{ display: none; }}
.detail-row.open {{ display: table-row; }}
.detail-row td {{ padding: 4px 12px 4px 32px; font-size: 12px; color: #8b949e; }}
.bar {{ display: inline-block; height: 14px; border-radius: 3px; min-width: 2px; }}
.bar-strong {{ background: #3fb950; }}
.bar-partial {{ background: #d29922; }}
.bar-weak {{ background: #f85149; }}
.pct {{ font-size: 12px; color: #8b949e; margin-left: 4px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
.badge-l1 {{ background: #1f3a5f; color: #58a6ff; }}
.badge-l2 {{ background: #2a1f3f; color: #bc8cff; }}
.badge-l3 {{ background: #1f3f2a; color: #3fb950; }}
.badge-l4 {{ background: #3f2a1f; color: #f0883e; }}
.empty {{ text-align: center; padding: 60px 20px; color: #8b949e; }}
.citation-item {{ padding: 6px 0; border-bottom: 1px solid #21262d; }}
.citation-text {{ font-style: italic; color: #8b949e; font-size: 12px; }}
.citation-count {{ color: #58a6ff; font-weight: bold; }}
</style>
</head>
<body>

<h1>Memory Metrics Dashboard</h1>
<p class="subtitle">Last {data['since_days']} days &middot; Generated {_now()}</p>

<!-- Summary Cards -->
<div class="grid">
  <div class="card">
    <h2>Overview</h2>
    <div class="stat-row">
      <div class="stat-item">
        <div class="stat">{data['session_count']}</div>
        <div class="stat-label">Sessions</div>
      </div>
      <div class="stat-item">
        <div class="stat">{data['total_injections']}</div>
        <div class="stat-label">Injections</div>
      </div>
      <div class="stat-item">
        <div class="stat">{_fmt_tokens(data['total_tokens'])}</div>
        <div class="stat-label">Tokens Burned</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Usage Signals</h2>
    <div class="stat-row">
      <div class="stat-item">
        <div class="stat">{data['citation_rate']}%</div>
        <div class="stat-label">Citation Rate</div>
      </div>
      <div class="stat-item">
        <div class="stat">{data['dedup_rate']}%</div>
        <div class="stat-label">Dedup Hit Rate</div>
      </div>
      <div class="stat-item">
        <div class="stat">{data['empty_rate']}%</div>
        <div class="stat-label">Empty Rate</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Relevance Distribution</h2>
    {_relevance_bars(data['relevance'])}
  </div>
</div>

<!-- Charts -->
<div class="grid">
  <div class="card">
    <h2>Token Burn per Day</h2>
    <div class="chart-container">
      <canvas id="tokenChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Relevance Trend</h2>
    <div class="chart-container">
      <canvas id="relevanceChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Layer Breakdown</h2>
    <div class="chart-container">
      <canvas id="layerChart"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Top Cited Memories</h2>
    {_citations_html(data.get('top_citations', []))}
  </div>
</div>

<!-- Session Table -->
<div class="card" style="margin-top: 16px;">
  <h2>Sessions</h2>
  <table id="sessionTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Date</th>
        <th onclick="sortTable(1)">Project</th>
        <th onclick="sortTable(2)">Injections</th>
        <th onclick="sortTable(3)">Tokens</th>
        <th onclick="sortTable(4)">Citations</th>
      </tr>
    </thead>
    <tbody id="sessionBody">
    </tbody>
  </table>
</div>

<script>
// Data
const sessions = {sessions_json};
const dailyTokens = {daily_tokens_json};
const dailyRelevance = {daily_relevance_json};
const layers = {layers_json};
const relevance = {relevance_json};

// Render session table
const tbody = document.getElementById('sessionBody');
sessions.forEach((s, idx) => {{
  const tr = document.createElement('tr');
  tr.className = 'expandable';
  tr.innerHTML = `
    <td>${{s.ended_at ? s.ended_at.substring(0, 16) : '?'}}</td>
    <td>${{s.project || '?'}}</td>
    <td>${{s.total_injections}}</td>
    <td>${{s.total_tokens}}</td>
    <td>${{s.citation_count || 0}}</td>
  `;
  tr.addEventListener('click', () => {{
    const details = document.querySelectorAll('.detail-' + idx);
    details.forEach(d => d.classList.toggle('open'));
  }});
  tbody.appendChild(tr);

  // Injection details (hidden by default)
  if (s.injections && s.injections.length > 0) {{
    s.injections.forEach(inj => {{
      const dr = document.createElement('tr');
      dr.className = 'detail-row detail-' + idx;
      const layerClass = 'badge-' + (inj.layer || '').toLowerCase();
      dr.innerHTML = `
        <td><span class="badge ${{layerClass}}">${{inj.layer}}</span> ${{inj.event}}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
            title="${{(inj.query||'').replace(/"/g, '&quot;')}}">${{(inj.query||'').substring(0, 60)}}</td>
        <td>${{inj.filtered_count}}/${{inj.result_count}} results &middot; ${{inj.duration_ms}}ms</td>
        <td>${{inj.token_estimate}} tok</td>
        <td>${{inj.avg_relevance != null ? inj.avg_relevance.toFixed(2) : '-'}}</td>
      `;
      tbody.appendChild(dr);
    }});
  }}
}});

// Charts (only if Chart.js loaded)
if (typeof Chart !== 'undefined') {{
  const chartColors = {{
    blue: '#58a6ff', purple: '#bc8cff', green: '#3fb950',
    orange: '#f0883e', red: '#f85149', gray: '#8b949e'
  }};

  // Token burn chart
  new Chart(document.getElementById('tokenChart'), {{
    type: 'bar',
    data: {{
      labels: dailyTokens.map(d => d.day),
      datasets: [{{
        label: 'Tokens',
        data: dailyTokens.map(d => d.tokens),
        backgroundColor: chartColors.blue + '80',
        borderColor: chartColors.blue,
        borderWidth: 1
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
        y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});

  // Relevance trend chart
  new Chart(document.getElementById('relevanceChart'), {{
    type: 'line',
    data: {{
      labels: dailyRelevance.map(d => d.day),
      datasets: [{{
        label: 'Avg Relevance',
        data: dailyRelevance.map(d => d.avg_relevance),
        borderColor: chartColors.green,
        backgroundColor: chartColors.green + '20',
        fill: true, tension: 0.3, pointRadius: 3
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
        y: {{ min: 0, max: 1, ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});

  // Layer pie chart
  new Chart(document.getElementById('layerChart'), {{
    type: 'doughnut',
    data: {{
      labels: layers.map(l => l.layer),
      datasets: [{{
        data: layers.map(l => l.cnt),
        backgroundColor: [chartColors.blue, chartColors.purple, chartColors.green, chartColors.orange]
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ color: '#c9d1d9', padding: 12 }} }}
      }}
    }}
  }});
}}

// Table sorting
function sortTable(col) {{
  const table = document.getElementById('sessionTable');
  const rows = Array.from(table.querySelectorAll('tbody tr.expandable'));
  const dir = table.dataset.sortDir === 'asc' ? 'desc' : 'asc';
  table.dataset.sortDir = dir;
  rows.sort((a, b) => {{
    let va = a.cells[col].textContent.trim();
    let vb = b.cells[col].textContent.trim();
    const na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) {{ va = na; vb = nb; }}
    if (va < vb) return dir === 'asc' ? -1 : 1;
    if (va > vb) return dir === 'asc' ? 1 : -1;
    return 0;
  }});
  const tbody = table.querySelector('tbody');
  rows.forEach(r => {{
    tbody.appendChild(r);
    // Move associated detail rows after their parent
    const idx = r.className.match(/expandable/);
    if (idx) {{
      const details = tbody.querySelectorAll('.detail-row');
    }}
  }});
}}
</script>

<!-- Fallback table if Chart.js CDN unavailable -->
<noscript>
<div class="card" style="margin-top: 16px;">
  <h2>Charts require JavaScript</h2>
  <p>Data is still visible in the session table above.</p>
</div>
</noscript>

</body>
</html>"""


def _empty_html():
    return """<!DOCTYPE html>
<html><head><title>Memory Metrics</title>
<style>body{font-family:sans-serif;background:#0d1117;color:#c9d1d9;display:flex;
justify-content:center;align-items:center;height:100vh;}
.msg{text-align:center;}.cmd{color:#58a6ff;font-family:monospace;}</style>
</head><body><div class="msg"><h1>No Metrics Data</h1>
<p>Enable metrics collection:</p>
<p class="cmd">set-memory metrics --enable</p>
<p>Then use Claude Code normally. Metrics are collected automatically.</p>
</div></body></html>"""


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _relevance_bars(rel):
    total = rel.get("strong", 0) + rel.get("partial", 0) + rel.get("weak", 0)
    if total == 0:
        return '<div style="color:#8b949e">No data</div>'

    s_pct = rel["strong"] / total * 100
    p_pct = rel["partial"] / total * 100
    w_pct = rel["weak"] / total * 100

    return f"""
    <div style="margin-bottom:8px">
      <div>&gt;0.7 (strong)
        <span class="bar bar-strong" style="width:{s_pct*1.5}px"></span>
        <span class="pct">{s_pct:.0f}% ({rel['strong']})</span>
      </div>
    </div>
    <div style="margin-bottom:8px">
      <div>0.3-0.7 (partial)
        <span class="bar bar-partial" style="width:{p_pct*1.5}px"></span>
        <span class="pct">{p_pct:.0f}% ({rel['partial']})</span>
      </div>
    </div>
    <div>
      <div>&lt;0.3 (weak)
        <span class="bar bar-weak" style="width:{w_pct*1.5}px"></span>
        <span class="pct">{w_pct:.0f}% ({rel['weak']})</span>
      </div>
    </div>"""


def _citations_html(citations):
    if not citations:
        return '<div style="color:#8b949e;padding:12px 0">No citations found</div>'

    items = []
    for cit in citations:
        text = cit["text"][:80]
        items.append(
            f'<div class="citation-item">'
            f'<span class="citation-count">{cit["count"]}x</span> '
            f'<span class="citation-text">"{text}"</span>'
            f'</div>'
        )
    return "\n".join(items)
