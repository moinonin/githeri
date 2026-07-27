#!/usr/bin/env python3
"""
Dashboard Generator - Creates HTML dashboard from metrics database.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta


DB_PATH = Path("metrics/autonomous.db")
OUTPUT_PATH = Path("dashboard/autonomous.html")


def get_stats(conn) -> dict:
    """Get overall statistics."""
    cursor = conn.cursor()
    
    # Total runs
    cursor.execute("SELECT COUNT(*) FROM runs")
    total_runs = cursor.fetchone()[0]
    
    # Success rate
    cursor.execute("SELECT COUNT(*) FROM runs WHERE status = 'success'")
    success_runs = cursor.fetchone()[0]
    
    # Total tokens
    cursor.execute("SELECT SUM(tokens_total) FROM runs")
    total_tokens = cursor.fetchone()[0] or 0
    
    # Total cost
    cursor.execute("SELECT SUM(cost_usd) FROM runs")
    total_cost = cursor.fetchone()[0] or 0.0
    
    # Avg duration
    cursor.execute("SELECT AVG(duration_ms) FROM runs WHERE duration_ms > 0")
    avg_duration = cursor.fetchone()[0] or 0
    
    # Recent runs (last 7 days)
    cursor.execute("""
        SELECT status, cost_usd, duration_ms, tokens_total, timestamp
        FROM runs WHERE timestamp > datetime('now', '-7 days')
        ORDER BY timestamp DESC
    """)
    recent = cursor.fetchall()
    
    # Per-sprint stats
    cursor.execute("""
        SELECT sprint_id, 
               COUNT(*) as runs,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
               AVG(cost_usd) as avg_cost,
               AVG(duration_ms) as avg_duration,
               SUM(tokens_total) as total_tokens
        FROM runs WHERE timestamp > datetime('now', '-30 days')
        GROUP BY sprint_id ORDER BY MAX(timestamp) DESC
    """)
    sprints = cursor.fetchall()
    
    # Alerts (last 7 days)
    cursor.execute("""
        SELECT alert_type, severity, message, timestamp, acknowledged
        FROM alerts WHERE timestamp > datetime('now', '-7 days')
        ORDER BY timestamp DESC
    """)
    alerts = cursor.fetchall()
    
    return {
        'total_runs': total_runs,
        'success_runs': success_runs,
        'success_rate': (success_runs / total_runs * 100) if total_runs > 0 else 0,
        'total_tokens': total_tokens,
        'total_cost': total_cost,
        'avg_duration_ms': avg_duration,
        'recent_runs': recent,
        'sprints': sprints,
        'alerts': alerts
    }


def get_trend_data(conn, days: int = 30) -> dict:
    """Get trend data for charts."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT date(timestamp) as day,
               COUNT(*) as runs,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successes,
               SUM(cost_usd) as cost,
               SUM(tokens_total) as tokens,
               AVG(duration_ms) as avg_duration
        FROM runs
        WHERE timestamp > datetime('now', '-' || ? || ' days')
        GROUP BY day
        ORDER BY day
    """, (days,))
    
    daily = cursor.fetchall()
    
    return {
        'labels': [row[0] for row in daily],
        'runs': [row[1] for row in daily],
        'successes': [row[2] for row in daily],
        'cost': [row[3] for row in daily],
        'tokens': [row[4] for row in daily],
        'avg_duration': [row[5] for row in daily]
    }


def generate_dashboard(stats: dict, trends: dict) -> str:
    """Generate HTML dashboard."""
    
    # Color coding
    success_color = '#10b981'
    warning_color = '#f59e0b'
    danger_color = '#ef4444'
    
    success_rate = stats['success_rate']
    if success_rate >= 90:
        rate_color = success_color
    elif success_rate >= 70:
        rate_color = warning_color
    else:
        rate_color = danger_color
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autonomous Agent Observability Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #f8fafc; margin-bottom: 8px; }
        .subtitle { color: #94a3b8; margin-bottom: 24px; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
        .card h3 { color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .metric { font-size: 32px; font-weight: 700; }
        .metric-success { color: """ + success_color + """; }
        .metric-warning { color: """ + warning_color + """; }
        .metric-danger { color: """ + danger_color + """; }
        .metric-neutral { color: #64748b; }
        
        .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .chart-card { background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }
        .chart-card h4 { color: #94a3b8; margin-bottom: 12px; }
        canvas { max-height: 300px; }
        
        .tables { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        @media (max-width: 900px) { .charts, .tables { grid-template-columns: 1fr; } }
        
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-weight: 600; }
        tr:hover { background: #1e293b; }
        .status-success { color: """ + success_color + """; }
        .status-failed { color: """ + danger_color + """; }
        .severity-critical { color: """ + danger_color + """; font-weight: bold; }
        .severity-warning { color: """ + warning_color + """; }
        .severity-info { color: #3b82f6; }
        
        .alert { padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid; }
        .alert-critical { background: rgba(239, 68, 68, 0.1); border-color: """ + danger_color + """; }
        .alert-warning { background: rgba(245, 158, 11, 0.1); border-color: """ + warning_color + """; }
        .alert-info { background: rgba(59, 130, 246, 0.1); border-color: #3b82f6; }
        
        .footer { margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155; color: #64748b; font-size: 12px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Autonomous Agent Observability</h1>
            <p class="subtitle">Real-time metrics for AI-driven development</p>
        </header>
        
        <div class="grid">
            <div class="card">
                <h3>Total Runs</h3>
                <div class="metric metric-neutral">{stats['total_runs']}</div>
            </div>
            <div class="card">
                <h3>Success Rate</h3>
                <div class="metric" style="color: {rate_color};">{stats['success_rate']:.1f}%</div>
            </div>
            <div class="card">
                <h3>Total Tokens</h3>
                <div class="metric metric-neutral">{stats['total_tokens']:,}</div>
            </div>
            <div class="card">
                <h3>Total Cost</h3>
                <div class="metric metric-neutral">${stats['total_cost']:.4f}</div>
            </div>
            <div class="card">
                <h3>Avg Duration</h3>
                <div class="metric metric-neutral">{stats['avg_duration_ms']:.0f}ms</div>
            </div>
            <div class="card">
                <h3>Active Alerts</h3>
                <div class="metric {'metric-danger' if any(a[1] == 'critical' for a in stats['alerts']) else ('metric-warning' if stats['alerts'] else 'metric-neutral')}">
                    {len(stats['alerts'])}
                </div>
            </div>
        </div>
        
        <div class="charts">
            <div class="chart-card">
                <h4>📊 Runs & Success Rate (30 days)</h4>
                <canvas id="runsChart"></canvas>
            </div>
            <div class="chart-card">
                <h4>💰 Cost & Tokens (30 days)</h4>
                <canvas id="costChart"></canvas>
            </div>
        </div>
        
        <div class="charts">
            <div class="chart-card">
                <h4>⏱️ Average Duration (30 days)</h4>
                <canvas id="durationChart"></canvas>
            </div>
            <div class="chart-card">
                <h4>📈 Sprint Performance</h4>
                <canvas id="sprintChart"></canvas>
            </div>
        </div>
        
        <div class="tables">
            <div class="card">
                <h3>🚨 Active Alerts (7 days)</h3>
                <div style="max-height: 300px; overflow-y: auto;">
"""
    
    if stats['alerts']:
        for alert in stats['alerts']:
            severity_class = 'alert-' + alert[1]
            ack = ' ✅' if alert[4] else ''
            html += """
                    <div class="alert {severity_class}">
                        <strong>[{alert_type}]</strong> {message}
                        <br><small>{timestamp}{ack}</small>
                    </div>
""".format(severity_class='alert-' + alert[1], alert_type=alert[0].upper(), message=alert[2], timestamp=alert[3], ack=ack)
    else:
        html += '<p style="color: #64748b;">No active alerts ✅</p>'
    
    html += """
                </div>
            </div>
            
            <div class="card">
                <h3>📋 Recent Runs (7 days)</h3>
                <table>
                    <thead>
                        <tr><th>Time</th><th>Status</th><th>Cost</th><th>Duration</th><th>Tokens</th></tr>
                    </thead>
                    <tbody>
"""
    
    for run in stats['recent_runs'][:10]:
        status_class = 'status-success' if run[0] == 'success' else 'status-failed'
        html += """
                        <tr>
                            <td>{timestamp}</td>
                            <td class="{status_class}">{status}</td>
                            <td>${cost:.4f}</td>
                            <td>{duration}ms</td>
                            <td>{tokens:,}</td>
                        </tr>
""".format(timestamp=run[4][:16], status_class=status_class, status=run[0], cost=run[1], duration=run[2], tokens=run[3])
    
    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h3>🏃 Sprint Performance (30 days)</h3>
                <table>
                    <thead>
                        <tr><th>Sprint</th><th>Runs</th><th>Success %</th><th>Avg Cost</th><th>Avg Duration</th><th>Total Tokens</th></tr>
                    </thead>
                    <tbody>
"""
    
    for sprint in stats['sprints']:
        sprint_id, runs, successes, avg_cost, avg_duration, total_tokens = sprint
        success_pct = (successes / runs * 100) if runs > 0 else 0
        html += """
                        <tr>
                            <td>{sprint_id}</td>
                            <td>{runs}</td>
                            <td>{success_pct:.1f}%</td>
                            <td>${avg_cost:.4f}</td>
                            <td>{avg_duration:.0f}ms</td>
                            <td>{total_tokens:,}</td>
                        </tr>
""".format(sprint_id=sprint_id, runs=runs, success_pct=success_pct, avg_cost=avg_cost, avg_duration=avg_duration, total_tokens=total_tokens)
    
    html += """
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            Last updated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """ | 
            Autonomous Agent Observability Dashboard
        </div>
    </div>
    
    <script>
        // Chart colors
        const colors = {
            success: '""" + success_color + """',
            warning: '""" + warning_color + """',
            danger: '""" + danger_color + """',
            primary: '#3b82f6',
            grid: '#334155',
            text: '#94a3b8'
        };
        
        Chart.defaults.color = colors.text;
        Chart.defaults.borderColor = colors.grid;
        
        // Runs & Success Rate Chart
        new Chart(document.getElementById('runsChart'), {
            type: 'bar',
            data: {
                labels: """ + json.dumps(trends['labels']) + """,
                datasets: [{
                    label: 'Total Runs',
                    data: """ + json.dumps(trends['runs']) + """,
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: colors.primary,
                    borderWidth: 1,
                    yAxisID: 'y'
                }, {
                    label: 'Success Rate %',
                    data: """ + json.dumps([s/r*100 if r>0 else 0 for s,r in zip(trends['successes'], trends['runs'])]) + """,
                    type: 'line',
                    borderColor: colors.success,
                    backgroundColor: 'transparent',
                    yAxisID: 'y1',
                    tension: 0.3,
                    pointRadius: 3
                }]
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Runs' } },
                    y1: { type: 'linear', display: true, position: 'right', min: 0, max: 100, title: { display: true, text: 'Success %' } }
                }
            }
        });
        
        // Cost & Tokens Chart
        new Chart(document.getElementById('costChart'), {
            type: 'line',
            data: {
                labels: """ + json.dumps(trends['labels']) + """,
                datasets: [{
                    label: 'Cost ($)',
                    data: """ + json.dumps(trends['cost']) + """,
                    borderColor: colors.warning,
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    yAxisID: 'y',
                    tension: 0.3,
                    fill: true
                }, {
                    label: 'Tokens',
                    data: """ + json.dumps(trends['tokens']) + """,
                    borderColor: colors.primary,
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Cost ($)' } },
                    y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Tokens' } }
                }
            }
        });
        
        // Duration Chart
        new Chart(document.getElementById('durationChart'), {
            type: 'line',
            data: {
                labels: """ + json.dumps(trends['labels']) + """,
                datasets: [{
                    label: 'Avg Duration (ms)',
                    data: """ + json.dumps(trends['avg_duration']) + """,
                    borderColor: colors.danger,
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true, title: { display: true, text: 'ms' } } }
            }
        });
        
        // Sprint Performance Chart
        new Chart(document.getElementById('sprintChart'), {
            type: 'bar',
            data: {
                labels: """ + json.dumps([s[0] for s in stats['sprints']]) + """,
                datasets: [{
                    label: 'Runs',
                    data: """ + json.dumps([s[1] for s in stats['sprints']]) + """,
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: colors.primary,
                    borderWidth: 1
                }, {
                    label: 'Success Rate %',
                    data: """ + json.dumps([s[2]/s[1]*100 if s[1]>0 else 0 for s in stats['sprints']]) + """,
                    type: 'line',
                    borderColor: colors.success,
                    backgroundColor: 'transparent',
                    yAxisID: 'y1',
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Runs' } },
                    y1: { min: 0, max: 100, position: 'right', title: { display: true, text: 'Success %' } }
                }
            }
        });
    </script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML dashboard from metrics DB")
    parser.add_argument('--db', type=str, default=str(DB_PATH), help="Metrics database path")
    parser.add_argument('--output', type=str, default=str(OUTPUT_PATH), help="Output HTML path")
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    stats = get_stats(conn)
    trends = get_trend_data(conn)
    conn.close()
    
    html = generate_dashboard(stats, trends)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    
    print(f"✅ Dashboard generated: {output_path}")


if __name__ == '__main__':
    main()