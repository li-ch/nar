"""
One-time setup for congestion-control topic.

Actions:
1) Ensure ns-3 submodule is initialized at third_party/ns-3-dev
2) Scaffold contrib/auto-cc from topic sources
3) Configure and build ns-3
4) Run Cubic baseline and write topics/cc/infra/baselines/cubic_baseline.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

TOPIC_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOPIC_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.ns3 import NS3_DIR, build_ns3, configure_ns3, ensure_submodule, ns3_env, run_cmd

TRACES_DIR = REPO_ROOT / "artifacts" / "cc" / "traces"
MODULE_NAME = "auto-cc"


def ensure_ns3() -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    ensure_submodule()
    if not NS3_DIR.exists():
        raise RuntimeError(
            f"ns-3 submodule is missing at {NS3_DIR}. Run `git submodule update --init --recursive`."
        )


def scaffold_module() -> Path:
    module_dir = NS3_DIR / "contrib" / MODULE_NAME
    model_dir = module_dir / "model"
    examples_dir = module_dir / "examples"
    module_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = {
        TOPIC_DIR / "infra" / "module-scaffold" / "CMakeLists.txt": module_dir / "CMakeLists.txt",
        TOPIC_DIR / "src" / "cc-algo.h": model_dir / "cc-algo.h",
        TOPIC_DIR / "src" / "cc-algo.cc": model_dir / "cc-algo.cc",
        TOPIC_DIR / "infra" / "scenario.cc": examples_dir / "scenario.cc",
    }
    for src, dst in files_to_copy.items():
        if not src.exists():
            raise FileNotFoundError(f"Required file missing for scaffold: {src}")
        shutil.copy2(src, dst)
    return module_dir


def configure_and_build() -> None:
    configure_ns3()
    build_ns3()


def run_cubic_baseline() -> None:
    baseline_file = TOPIC_DIR / "infra" / "baselines" / "cubic_baseline.json"
    if baseline_file.exists():
        print(f"Baseline already exists: {baseline_file}")
        return

    if TRACES_DIR.exists():
        for p in TRACES_DIR.glob("*.csv"):
            p.unlink()

    run_cmd(
        [
            sys.executable,
            "ns3",
            "run",
            "auto-cc-scenario --algorithm=TcpCubic --output_dir="
            + str(TRACES_DIR).replace("\\", "/"),
        ],
        cwd=NS3_DIR,
        env=ns3_env(),
    )

    run_cmd(
        [
            sys.executable,
            str(TOPIC_DIR / "evaluate.py"),
            "--trace-dir",
            str(TRACES_DIR),
            "--write-baseline",
            str(baseline_file),
            "--quiet",
        ],
        cwd=REPO_ROOT,
    )
    with open(baseline_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Baseline written with keys: {sorted(data.keys())}")


def main() -> None:
    print(f"Topic dir: {TOPIC_DIR}")
    print(f"ns-3 path: {NS3_DIR}")
    ensure_ns3()
    scaffold_module()
    configure_and_build()
    run_cubic_baseline()
    print("Setup complete.")


if __name__ == "__main__":
    main()
