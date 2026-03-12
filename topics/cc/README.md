# Congestion Control Topic

This topic runs autonomous congestion-control research on `ns-3`.

## Editable surface

Primary file to mutate:
- `topics/cc/src/cc-algo.cc`

Optional companion header:
- `topics/cc/src/cc-algo.h`

## Fixed harness

Do not modify during experiments:
- `topics/cc/infra/scenario.cc`
- `topics/cc/evaluate.py`
- `topics/cc/run.py`

## Metrics

The evaluator reports:
- throughput (`throughput_mbps`)
- latency (`avg_rtt_ms`, `p99_rtt_ms`)
- fairness (`fairness_index`)
- adaptation speed (`adaptation_s`)
- combined score (`score`, higher is better)

## Commands

One-time setup:

```bash
uv run topics/cc/prepare.py
```

Run one experiment:

```bash
uv run topics/cc/run.py
```
