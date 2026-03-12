"""
Per-experiment orchestrator.

Workflow:
1) Copy editable C++ files into ns-3 contrib module
2) Incremental build
3) Run fixed scenarios
4) Evaluate traces and print summary
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

TOPIC_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOPIC_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ns3 import NS3_DIR, build_ns3, ns3_env, run_cmd

TRACES_DIR = REPO_ROOT / "artifacts" / "cc" / "traces"
MODULE_DIR = NS3_DIR / "contrib" / "auto-cc"
BASELINE_FILE = TOPIC_DIR / "infra" / "baselines" / "cubic_baseline.json"
TOTAL_BUDGET_SEC = 180.0


def ensure_ready() -> None:
    if not NS3_DIR.exists():
        raise RuntimeError(f"Missing ns-3 tree at {NS3_DIR}. Run `uv run topics/cc/prepare.py` first.")
    if not BASELINE_FILE.exists():
        raise RuntimeError(f"Missing baseline file at {BASELINE_FILE}. Run `uv run topics/cc/prepare.py` first.")


def copy_sources() -> None:
    model_dir = MODULE_DIR / "model"
    examples_dir = MODULE_DIR / "examples"
    model_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(TOPIC_DIR / "src" / "cc-algo.h", model_dir / "cc-algo.h")
    shutil.copy2(TOPIC_DIR / "src" / "cc-algo.cc", model_dir / "cc-algo.cc")
    shutil.copy2(TOPIC_DIR / "infra" / "scenario.cc", examples_dir / "scenario.cc")
    shutil.copy2(TOPIC_DIR / "infra" / "module-scaffold" / "CMakeLists.txt", MODULE_DIR / "CMakeLists.txt")


def clear_traces() -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    for p in TRACES_DIR.glob("*.csv"):
        try:
            p.unlink()
        except PermissionError:
            # On Windows a recently exited process can briefly keep a handle.
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one nar congestion-control experiment")
    parser.add_argument("--algorithm", default="TcpAutoCC", help="Algorithm type for ns-3")
    args = parser.parse_args()

    t_start = time.time()
    cenv = ns3_env()
    ensure_ready()
    copy_sources()
    clear_traces()

    # Build
    t0 = time.time()
    build = build_ns3(check=False, capture_output=True)
    build_seconds = time.time() - t0
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        raise SystemExit(1)

    # Enforce global budget for simulation + evaluation.
    elapsed = time.time() - t_start
    remaining = TOTAL_BUDGET_SEC - elapsed
    if remaining <= 0:
        raise RuntimeError("Budget exceeded before simulation start.")

    t1 = time.time()
    trace_arg = str(TRACES_DIR).replace("\\", "/")
    sim = run_cmd(
        [
            sys.executable,
            "ns3",
            "run",
            f"auto-cc-scenario --algorithm={args.algorithm} --output_dir={trace_arg}",
        ],
        cwd=NS3_DIR,
        timeout=remaining,
        env=cenv,
        check=False,
        capture_output=True,
    )
    sim_seconds = time.time() - t1
    if sim.returncode != 0:
        sys.stderr.write(sim.stdout)
        sys.stderr.write(sim.stderr)
        raise SystemExit(1)

    elapsed = time.time() - t_start
    remaining = TOTAL_BUDGET_SEC - elapsed
    if remaining <= 0:
        raise RuntimeError("Budget exceeded before evaluation.")

    eval_proc = run_cmd(
        [
            sys.executable,
            str(TOPIC_DIR / "evaluate.py"),
            "--trace-dir",
            str(TRACES_DIR),
            "--baseline-file",
            str(BASELINE_FILE),
            "--build-seconds",
            str(build_seconds),
            "--sim-seconds",
            str(sim_seconds),
            "--total-seconds",
            str(time.time() - t_start),
        ],
        cwd=REPO_ROOT,
        timeout=remaining,
        check=False,
        capture_output=True,
    )
    if eval_proc.returncode != 0:
        sys.stderr.write(eval_proc.stdout)
        sys.stderr.write(eval_proc.stderr)
        raise SystemExit(1)

    # Surface a concise, machine-readable block.
    sys.stdout.write(eval_proc.stdout)

    # Best-effort cleanup.
    clear_traces()


if __name__ == "__main__":
    main()
