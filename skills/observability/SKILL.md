---
name: observability
description: "Cost/performance observability for autonomous agent: token tracking, latency, success rates, anomaly alerting"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [observability, metrics, dashboard, alerting, cost-tracking]
    related_skills: [ci-cd-integration, code-review-agent, spec-forge]
---

# Observability Dashboard

## What This Is

End-to-end observability for the autonomous coding agent:
1. **Token Tracking** - Per-feature token usage and cost
2. **Latency Monitoring** - Execution time per stage
3. **Success Rate Tracking** - Pass/fail rates per sprint
4. **Anomaly Detection** - Cost spikes, failure rates, latency regressions

## When To Use

- After implementing autonomous features
- For cost optimization
- To detect performance regressions
- For capacity planning

## Installation

```bash
cp -r skills/software-development/observability ~/.hermes/skills/observability
```

## Usage

### Collect Metrics

```bash
python skills/software-development/observability/scripts/collect_metrics.py \
  --runbook docs/sprints/sprint8/RUNBOOK.md \
  --spec sprints/sprint8.spec.yaml
```

### Generate Dashboard

```bash
python skills/software-development/observability/scripts/generate_dashboard.py \
  --output dashboard/autonomous.html
```

### Check Alerts

```bash
python skills/software-development/observability/scripts/alerting.py \
  --db metrics/autonomous.db
```

## Data Model

### SQLite Schema (metrics/autonomous.db)

```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    sprint_id TEXT NOT NULL,
    task_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT,  -- success, failed, partial
    duration_ms INTEGER,
    tokens_total INTEGER,
    tokens_prompt INTEGER,
    tokens_completion INTEGER,
    cost_usd REAL,
    model TEXT,
    error TEXT
);

CREATE TABLE stages (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,
    stage_num INTEGER,
    name TEXT,
    status TEXT,
    duration_ms INTEGER,
    tokens INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT,  -- cost_spike, failure_rate, latency
    severity TEXT,    -- warning, critical
    message TEXT,
    sprint_id TEXT,
    acknowledged BOOLEAN DEFAULT FALSE
);
```

## Dashboard

The dashboard (`dashboard/autonomous.html`) provides:
- **Real-time**: Current run status, token burn rate
- **Historical**: Trends over 7/30/90 days
- **Per-sprint**: Token cost, success rate, latency
- **Anomalies**: Highlighted with severity

## Alerting Rules

| Alert Type | Condition | Severity |
|------------|-----------|----------|
| Cost Spike | Daily cost > 2x 7-day avg | Critical |
| Failure Rate | Sprint failure > 20% | Warning |
| Latency | Stage > 2x 7-day p95 | Warning |
| Token Burn | Hourly > 100k tokens | Warning |

## Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| L1 | `python skills/software-development/observability/scripts/collect_metrics.py --help` | Exits 0 |
| L2 | `sqlite3 metrics/autonomous.db '.schema'` | Tables exist |
| L3 | `ls dashboard/autonomous.html` | File exists |
| L4 | `python skills/software-development/observability/scripts/alerting.py --db metrics/autonomous.db` | Exits 0 |