from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NS3_DIR = REPO_ROOT / "third_party" / "ns-3-dev"
NS3_SUBMODULE_PATH = "third_party/ns-3-dev"


def toolchain_env() -> dict[str, str]:
    env: dict[str, str] = {}
    extra_bin = os.environ.get("NAR_TOOLCHAIN_BIN") or os.environ.get("NET_AUTORESEARCH_TOOLCHAIN_BIN")
    if extra_bin:
        env["PATH"] = extra_bin + os.pathsep + os.environ.get("PATH", "")
    return env


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture_output,
        timeout=timeout,
        env=full_env,
    )


def ensure_submodule() -> None:
    if NS3_DIR.exists():
        return
    run_cmd(
        ["git", "submodule", "update", "--init", "--recursive", "--", NS3_SUBMODULE_PATH],
        cwd=REPO_ROOT,
    )
    if not NS3_DIR.exists():
        raise RuntimeError(f"ns-3 submodule is missing at {NS3_DIR}.")


def ensure_python3_shim() -> Path:
    py_dir = Path(sys.executable).parent
    if os.name == "nt":
        py3_bat = py_dir / "python3.bat"
        py3_exe = py_dir / "python3.exe"
        if not py3_bat.exists():
            py3_bat.write_text("@echo off\r\npython %*\r\n", encoding="utf-8")
        if not py3_exe.exists():
            shutil.copy2(py_dir / "python.exe", py3_exe)
    return py_dir


def ns3_env(include_python_shim: bool = False) -> dict[str, str]:
    env = toolchain_env()
    if include_python_shim:
        py_dir = ensure_python3_shim()
        env["PATH"] = str(py_dir) + os.pathsep + env.get("PATH", os.environ.get("PATH", ""))
    return env


def configure_ns3() -> None:
    stale_cache = NS3_DIR / "cmake-cache"
    stale_include = NS3_DIR / "build" / "include"
    if stale_cache.exists():
        shutil.rmtree(stale_cache, ignore_errors=True)
    if stale_include.exists():
        shutil.rmtree(stale_include, ignore_errors=True)

    run_cmd(
        [
            sys.executable,
            "ns3",
            "configure",
            "--enable-examples",
            "--disable-python-bindings",
        ],
        cwd=NS3_DIR,
        env=ns3_env(include_python_shim=True),
    )


def build_ns3(
    check: bool = True,
    capture_output: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [sys.executable, "ns3", "build"],
        cwd=NS3_DIR,
        check=check,
        capture_output=capture_output,
        timeout=timeout,
        env=ns3_env(),
    )

