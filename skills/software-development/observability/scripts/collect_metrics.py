#!/usr/bin/env python3
"""
Metrics Collector - Collects token usage, latency, success rates from autonomous runs.
"""

import argparse
import json
import sqlite3
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


DB_PATH = Path("metrics/autonomous.db")


def init_db():
    """Initialize the metrics database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            sprint_id TEXT NOT NULL,
            task_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            duration_ms INTEGER,
            tokens_total INTEGER,
            tokens_prompt INTEGER,
            tokens_completion INTEGER,
            cost_usd REAL,
            model TEXT,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stages (
            id INTEGER PRIMARY KEY,
            run_id INTEGER,
            stage_num INTEGER,
            name TEXT,
            status TEXT,
            duration_ms INTEGER,
            tokens INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            sprint_id TEXT,
            acknowledged BOOLEAN DEFAULT FALSE
        )
    """)
    conn.commit()
    return conn


def parse_runbook(runbook_path: Path) -> Dict[str, Any]:
    """Parse RUNBOOK.md for execution metrics."""
    if not runbook_path.exists():
        return {}
    
    content = runbook_path.read_text()
    results = {
        'stages': [],
        'total_duration_ms': 0,
        'status': 'unknown',
        'failures': [],
        'retries': 0
    }
    
    # Parse execution log table
    in_log = False
    for line in content.split('\n'):
        if '| Cmd#' in line and 'Start' in line and 'End' in line:
            in_log = True
            continue
        if in_log and line.startswith('|'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 7:
                cmd_num = parts[0]
                start = parts[2]
                end = parts[3]
                exit_code = parts[4]
                retry = parts[5]
                output = parts[6]
                
                try:
                    results['stages'].append({
                        'cmd': cmd_num,
                        'start': start,
                        'end': end,
                        'exit': int(exit_code) if exit_code.isdigit() else exit_code,
                        'retry': int(retry) if retry.isdigit() else 0,
                        'output': output[:200]
                    })
                    if exit_code != '0':
                        results['failures'].append(cmd_num)
                    if retry != '0':
                        results['retries'] += int(retry)
                except ValueError:
                    pass
        elif in_log and not line.startswith('|'):
            in_log = False
    
    # Parse goal verification
    in_goals = False
    passed = 0
    total = 0
    for line in content.split('\n'):
        if '### Local Goal Checks' in line:
            in_goals = True
            continue
        if in_goals and line.startswith('- **L'):
            total += 1
            if 'PASS' in line and '✅' in line:
                passed += 1
    
    results['goals_passed'] = passed
    results['goals_total'] = total
    results['status'] = 'success' if passed == total and total > 0 else 'failed' if total > 0 else 'unknown'
    
    return results


def collect_from_spec(spec_path: Path) -> Dict[str, Any]:
    """Extract metadata from spec."""
    if not spec_path.exists():
        return {}
    
    import yaml
    with open(spec_path) as f:
        spec = yaml.safe_load(f.read())
    
    return {
        'task_id': spec.get('task_id', ''),
        'summary': spec.get('summary', ''),
        'goals': len(spec.get('local_goals', [])),
        'depends_on': spec.get('depends_on', [])
    }


def record_run(conn, run_data: Dict[str, Any]) -> int:
    """Record a run in the database."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO runs (sprint_id, task_id, timestamp, status, duration_ms, 
                         tokens_total, tokens_prompt, tokens_completion, 
                         cost_usd, model, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_data.get('sprint_id', ''),
        run_data.get('task_id', ''),
        datetime.now().isoformat(),
        run_data.get('status', 'unknown'),
        run_data.get('duration_ms', 0),
        run_data.get('tokens_total', 0),
        run_data.get('tokens_prompt', 0),
        run_data.get('tokens_completion', 0),
        run_data.get('cost_usd', 0.0),
        run_data.get('model', ''),
        run_data.get('error', '')
    ))
    run_id = cursor.lastrowid
    
    # Record stages
    for stage in run_data.get('stages', []):
        conn.execute("""
            INSERT INTO stages (run_id, stage_num, name, status, duration_ms, tokens)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_id, stage.get('cmd', 0), stage.get('name', ''), 
              stage.get('status', ''), stage.get('duration_ms', 0), stage.get('tokens', 0)))
    
    conn.commit()
    return run_id


def check_anomalies(conn, sprint_id: str) -> list:
    """Check for anomalies and record alerts."""
    alerts = []
    cursor = conn.cursor()
    
    # Cost spike: last run cost > 2x avg of last 7
    cursor.execute("""
        SELECT AVG(cost_usd) FROM runs 
        WHERE sprint_id = ? AND timestamp > datetime('now', '-7 days')
    """, (sprint_id,))
    avg_cost = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT cost_usd FROM runs 
        WHERE sprint_id = ? ORDER BY timestamp DESC LIMIT 1
    """, (sprint_id,))
    last_cost = cursor.fetchone()
    if last_cost and last_cost[0] > 0 and avg_cost > 0:
        if last_cost[0] > 2 * avg_cost:
            alerts.append({
                'type': 'cost_spike',
                'severity': 'critical',
                'message': f'Last run cost ${last_cost[0]:.4f} exceeds 2x 7-day avg ${avg_cost:.4f}'
            })
    
    # Failure rate: last 5 runs
    cursor.execute("""
        SELECT status FROM runs 
        WHERE sprint_id = ? ORDER BY timestamp DESC LIMIT 5
    """, (sprint_id,))
    recent = cursor.fetchall()
    if len(recent) >= 3:
        failed = sum(1 for r in recent if r[0] == 'failed')
        if failed / len(recent) > 0.2:
            alerts.append({
                'type': 'failure_rate',
                'severity': 'warning',
                'message': f'Failure rate {failed}/{len(recent)} > 20%'
            })
    
    # Record alerts
    for alert in alerts:
        conn.execute("""
            INSERT INTO alerts (alert_type, severity, message, sprint_id)
            VALUES (?, ?, ?, ?)
        """, (alert['type'], alert['severity'], alert['message'], sprint_id))
    
    conn.commit()
    return alerts


def main():
    parser = argparse.ArgumentParser(description="Collect metrics from autonomous runs")
    parser.add_argument('--runbook', type=Path, help="Path to RUNBOOK.md")
    parser.add_argument('--spec', type=Path, help="Path to spec.yaml")
    parser.add_argument('--sprint-id', required=True, help="Sprint identifier")
    parser.add_argument('--model', default='qwen2.5-coder:7b-instruct', help="Model name")
    parser.add_argument('--tokens-total', type=int, default=0, help="Total tokens used")
    parser.add_argument('--tokens-prompt', type=int, default=0, help="Prompt tokens")
    parser.add_argument('--tokens-completion', type=int, default=0, help="Completion tokens")
    parser.add_argument('--cost', type=float, default=0.0, help="Cost in USD")
    parser.add_argument('--duration', type=int, default=0, help="Duration in ms")
    parser.add_argument('--error', default='', help="Error message if failed")
    args = parser.parse_args()
    
    conn = init_db()
    
    # Collect data
    run_data = {
        'sprint_id': args.sprint_id,
        'task_id': '',
        'status': 'success' if not args.error else 'failed',
        'duration_ms': args.duration,
        'tokens_total': args.tokens_total,
        'tokens_prompt': args.tokens_prompt,
        'tokens_completion': args.tokens_completion,
        'cost_usd': args.cost,
        'model': args.model,
        'error': args.error,
        'stages': []
    }
    
    if args.runbook:
        runbook_data = parse_runbook(args.runbook)
        run_data['stages'] = runbook_data.get('stages', [])
        run_data['status'] = runbook_data.get('status', run_data['status'])
    
    if args.spec:
        spec_data = collect_from_spec(args.spec)
        run_data['task_id'] = spec_data.get('task_id', '')
    
    # Record run
    run_id = record_run(conn, run_data)
    print(f"✅ Recorded run {run_id} for sprint {args.sprint_id}")
    
    # Check anomalies
    alerts = check_anomalies(conn, args.sprint_id)
    if alerts:
        for alert in alerts:
            print(f"⚠️  ALERT [{alert['severity'].upper()}]: {alert['message']}")
    else:
        print("✅ No anomalies detected")
    
    conn.close()


if __name__ == '__main__':
    main()