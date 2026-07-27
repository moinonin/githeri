#!/usr/bin/env python3
"""
Alerting System - Detects anomalies in cost, failure rate, latency.
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta


DB_PATH = Path("metrics/autonomous.db")


def check_anomalies(conn, sprint_id: str = None) -> list:
    """Check for anomalies and return list of alerts."""
    cursor = conn.cursor()
    alerts = []
    
    where_sprint = f"AND sprint_id = '{sprint_id}'" if sprint_id else ""
    
    # 1. Cost spike: last run cost > 2x 7-day average
    cursor.execute(f"""
        SELECT AVG(cost_usd) as avg_cost, sprint_id
        FROM runs 
        WHERE timestamp > datetime('now', '-7 days') {where_sprint}
        GROUP BY sprint_id
    """)
    avg_costs = cursor.fetchall()
    
    cursor.execute(f"""
        SELECT cost_usd, sprint_id FROM runs 
        WHERE timestamp = (SELECT MAX(timestamp) FROM runs WHERE 1=1 {where_sprint})
    """)
    last_costs = cursor.fetchall()
    
    for avg_row in avg_costs:
        sprint = avg_row[1]
        avg_cost = avg_row[0]
        if avg_cost == 0:
            continue
            
        last_cost = next((r[0] for r in last_costs if r[1] == sprint), 0)
        if last_cost > 0 and last_cost > 2 * avg_cost:
            alerts.append({
                'type': 'cost_spike',
                'severity': 'critical',
                'message': f'Sprint {sprint}: Last run cost ${last_cost:.4f} exceeds 2x 7-day avg ${avg_cost:.4f}',
                'sprint_id': sprint
            })
    
    # 2. Failure rate: last 5 runs > 20% failure
    cursor.execute(f"""
        SELECT sprint_id, status FROM runs 
        WHERE 1=1 {where_sprint}
        ORDER BY timestamp DESC LIMIT 5
    """)
    recent = cursor.fetchall()
    
    sprints_in_recent = set(r[0] for r in recent)
    for sprint in sprints_in_recent:
        sprint_runs = [r for r in recent if r[0] == sprint]
        if len(sprint_runs) >= 3:
            failed = sum(1 for r in sprint_runs if r[1] == 'failed')
            if failed / len(sprint_runs) > 0.2:
                alerts.append({
                    'type': 'failure_rate',
                    'severity': 'warning',
                    'message': f'Sprint {sprint}: Failure rate {failed}/{len(sprint_runs)} > 20%',
                    'sprint_id': sprint
                })
    
    # 3. Latency spike: last run duration > 2x 7-day p95
    cursor.execute(f"""
        SELECT duration_ms FROM runs 
        WHERE timestamp > datetime('now', '-7 days') {where_sprint} AND duration_ms > 0
    """)
    durations = [r[0] for r in cursor.fetchall()]
    
    if durations:
        durations.sort()
        p95 = durations[int(len(durations) * 0.95)]
        
        cursor.execute(f"""
            SELECT duration_ms, sprint_id FROM runs 
            WHERE 1=1 {where_sprint}
            ORDER BY timestamp DESC LIMIT 1
        """)
        last = cursor.fetchone()
        if last and last[0] > 0 and last[0] > 2 * p95:
            alerts.append({
                'type': 'latency',
                'severity': 'warning',
                'message': f'Sprint {last[1]}: Duration {last[0]}ms exceeds 2x p95 ({p95}ms)',
                'sprint_id': last[1]
            })
    
    # Record alerts in database
    for alert in alerts:
        cursor.execute("""
            INSERT INTO alerts (alert_type, severity, message, sprint_id)
            VALUES (?, ?, ?, ?)
        """, (alert['type'], alert['severity'], alert['message'], alert['sprint_id']))
    
    conn.commit()
    return alerts


def send_email_alert(alerts: list, email: str):
    """Send email alert (placeholder - requires SMTP config)."""
    if not email or not alerts:
        return
    
    # This is a placeholder - would need SMTP config
    print(f"📧 Would send email to {email} with {len(alerts)} alerts")


def main():
    parser = argparse.ArgumentParser(description="Check for anomalies in autonomous runs")
    parser.add_argument('--db', type=str, default=str(DB_PATH), help="Metrics database path")
    parser.add_argument('--sprint', help="Sprint ID to check (optional)")
    parser.add_argument('--email', help="Email to send alerts (requires SMTP config)")
    parser.add_argument('--json', action='store_true', help="Output JSON")
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    alerts = check_anomalies(conn, args.sprint)
    conn.close()
    
    if args.json:
        print(json.dumps(alerts, indent=2))
    else:
        if not alerts:
            print("✅ No anomalies detected")
        else:
            print(f"🚨 {len(alerts)} anomaly(ies) detected:")
            for alert in alerts:
                icon = "🔴" if alert['severity'] == 'critical' else "🟡"
                print(f"  {icon} [{alert['severity'].upper()}] {alert['message']}")
    
    if args.email:
        send_email_alert(alerts, args.email)


if __name__ == '__main__':
    import json
    main()