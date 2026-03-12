from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

TOPIC_DIR = Path(__file__).resolve().parent


def jain_fairness(values: list[float]) -> float:
    vals = [max(0.0, float(v)) for v in values]
    if not vals:
        return 0.0
    s = sum(vals)
    s2 = sum(v * v for v in vals)
    if s2 <= 0:
        return 0.0
    return (s * s) / (len(vals) * s2)


def load_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing summary file: {path}")
    return pd.read_csv(path)


def load_timeseries(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing timeseries file: {path}")
    return pd.read_csv(path)


def compute_raw_metrics(trace_dir: Path) -> dict[str, float]:
    a = load_summary(trace_dir / "scenario_a_summary.csv")
    b = load_summary(trace_dir / "scenario_b_summary.csv")
    c_ts = load_timeseries(trace_dir / "scenario_c_timeseries.csv")

    throughput_mbps = float(a["throughput_mbps"].mean()) if not a.empty else 0.0
    avg_rtt_ms = float(a["avg_delay_ms"].mean()) if not a.empty else 0.0
    p99_rtt_ms = float(a["avg_delay_ms"].quantile(0.99)) if not a.empty else 0.0

    fairness = jain_fairness(b["throughput_mbps"].tolist()) if not b.empty else 0.0

    # Adaptation: after bandwidth recovers at t=45s, how long to reach 90% of
    # pre-drop throughput (estimated from [20s, 30s)).
    c_flow0 = c_ts[c_ts["flow_id"] == 0].copy()
    pre_drop = c_flow0[(c_flow0["timestamp_s"] >= 20.0) & (c_flow0["timestamp_s"] < 30.0)]
    post_restore = c_flow0[c_flow0["timestamp_s"] >= 45.0]
    baseline_tp = float(pre_drop["throughput_mbps"].mean()) if not pre_drop.empty else 0.0
    threshold = 0.9 * baseline_tp
    adaptation_s = 10.0
    if threshold > 0 and not post_restore.empty:
        reached = post_restore[post_restore["throughput_mbps"] >= threshold]
        if not reached.empty:
            adaptation_s = max(0.0, float(reached.iloc[0]["timestamp_s"]) - 45.0)

    return {
        "throughput_mbps": throughput_mbps,
        "avg_rtt_ms": avg_rtt_ms,
        "p99_rtt_ms": p99_rtt_ms,
        "fairness_index": fairness,
        "adaptation_s": adaptation_s,
    }


def norm_ratio(n: float, d: float, cap: float = 2.0) -> float:
    if d <= 0:
        return 0.0
    return max(0.0, min(n / d, cap))


def compute_score(raw: dict[str, float], baseline: dict[str, float]) -> float:
    w_t, w_d, w_f, w_a = 0.3, 0.3, 0.2, 0.2
    norm_throughput = norm_ratio(raw["throughput_mbps"], baseline["throughput_mbps"])
    norm_delay = norm_ratio(raw["avg_rtt_ms"], baseline["avg_rtt_ms"])
    fairness = max(0.0, min(raw["fairness_index"], 1.0))
    adaptation = 1.0 - max(0.0, min(raw["adaptation_s"] / 10.0, 1.0))
    return w_t * norm_throughput + w_d * (1.0 - norm_delay) + w_f * fairness + w_a * adaptation


def print_summary(metrics: dict[str, float]) -> None:
    print("---")
    print(f"score:            {metrics['score']:.4f}")
    print(f"throughput_mbps:  {metrics['throughput_mbps']:.2f}")
    print(f"avg_rtt_ms:       {metrics['avg_rtt_ms']:.2f}")
    print(f"p99_rtt_ms:       {metrics['p99_rtt_ms']:.2f}")
    print(f"fairness_index:   {metrics['fairness_index']:.3f}")
    print(f"adaptation_s:     {metrics['adaptation_s']:.2f}")
    if "build_seconds" in metrics:
        print(f"build_seconds:    {metrics['build_seconds']:.1f}")
    if "sim_seconds" in metrics:
        print(f"sim_seconds:      {metrics['sim_seconds']:.1f}")
    if "total_seconds" in metrics:
        print(f"total_seconds:    {metrics['total_seconds']:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate nar congestion-control traces")
    parser.add_argument("--trace-dir", required=True, type=Path)
    parser.add_argument(
        "--baseline-file",
        type=Path,
        default=TOPIC_DIR / "infra" / "baselines" / "cubic_baseline.json",
    )
    parser.add_argument("--write-baseline", type=Path, default=None)
    parser.add_argument("--build-seconds", type=float, default=None)
    parser.add_argument("--sim-seconds", type=float, default=None)
    parser.add_argument("--total-seconds", type=float, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    raw = compute_raw_metrics(args.trace_dir)

    if args.write_baseline is not None:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        with open(args.write_baseline, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
        if not args.quiet:
            print(f"Wrote baseline metrics to {args.write_baseline}")
        return

    if not args.baseline_file.exists():
        raise FileNotFoundError(f"Baseline file not found: {args.baseline_file}")

    with open(args.baseline_file, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    score = compute_score(raw, baseline)
    metrics = dict(raw)
    metrics["score"] = score
    if args.build_seconds is not None:
        metrics["build_seconds"] = args.build_seconds
    if args.sim_seconds is not None:
        metrics["sim_seconds"] = args.sim_seconds
    if args.total_seconds is not None:
        metrics["total_seconds"] = args.total_seconds
    else:
        metrics["total_seconds"] = time.time() - t0

    if not args.quiet:
        print_summary(metrics)


if __name__ == "__main__":
    main()
