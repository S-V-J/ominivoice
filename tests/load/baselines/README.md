# Load Test Baselines

This directory stores baseline performance results for regression detection.

## Running Baselines

```bash
# Auth test baseline
k6 run --out json=baselines/auth-baseline.json tests/load/auth.js

# Agent CRUD baseline
k6 run --out json=baselines/agents-baseline.json tests/load/agents.js

# Voice WebSocket baseline
k6 run --out json=baselines/voice-baseline.json tests/load/voice.js
```

## CI Thresholds

| Metric | Threshold |
|--------|-----------|
| p95 latency | < 500ms |
| Error rate | < 0.1% |
| Register success | > 99% |
| Login success | > 99% |
| Agent CRUD success | > 99% |
| WebSocket connect | < 1000ms |

## Baseline Results Format

Store results as JSON files with timestamps:

```
baselines/
├── auth-baseline-2026-08-22.json
├── agents-baseline-2026-08-22.json
└── voice-baseline-2026-08-22.json
```

## Regression Detection

In CI, compare current run against latest baseline:

```bash
# Example: Check if p95 latency increased by > 20%
CURRENT_P95=$(jq '.metrics.http_req_duration.values.p95' current-results.json)
BASELINE_P95=$(jq '.metrics.http_req_duration.values.p95' baselines/auth-baseline-latest.json)

THRESHOLD=$(echo "$BASELINE_P95 * 1.2" | bc)
if (( $(echo "$CURRENT_P95 > $THRESHOLD" | bc -l) )); then
  echo "REGRESSION: p95 latency increased from ${BASELINE_P95}ms to ${CURRENT_P95}ms"
  exit 1
fi
```