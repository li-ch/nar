# Autoresearch Project Deep Dive

## Executive Overview

This repository is a compact experimental framework for autonomous LLM training research. It is intentionally small and script-driven: one file (`train.py`) is the mutable experimentation surface, while one file (`prepare.py`) provides fixed data and evaluation infrastructure for fair comparisons.

The core operating model is:
- Train for a fixed 5-minute wall-clock budget.
- Evaluate on a fixed validation shard with a vocab-size-independent metric (`val_bpb`).
- Keep/discard edits based on metric movement.

For its stated purpose (rapid autonomous iteration on one GPU), the design is coherent and pragmatic. For engineering robustness, the main gaps are the absence of tests, static checks, and CI.

## Repository Shape

Top-level files and roles:
- `README.md`: project context, setup, and design rationale.
- `prepare.py`: fixed constants, data download, tokenizer build, dataloader, and `evaluate_bpb`.
- `train.py`: model, optimizer, schedules, training loop, and reporting.
- `program.md`: autonomous experimentation protocol for the agent loop.
- `analysis.ipynb`: local results analysis notebook.
- `pyproject.toml` + `uv.lock`: dependency and lock state.

This is a flat-layout research repo (no package/module tree), optimized for direct script execution.

## Tech Stack and Runtime Assumptions

- Language/runtime: Python `>=3.10`
- Package manager: `uv`
- DL framework: PyTorch `2.9.1` (CUDA wheel index configured)
- Attention kernels: `kernels` package + FA3 interface selection at runtime
- Data/tokenization: `pyarrow`, `requests`, `rustbpe`, `tiktoken`
- Analysis: `numpy`, `pandas`, `matplotlib`

Strong assumptions:
- Single NVIDIA CUDA GPU is required.
- Training/eval paths are GPU-first (no CPU/MPS fallback in current scripts).

## System Architecture

### 1) Fixed Infrastructure Layer (`prepare.py`)

`prepare.py` acts as the reproducibility anchor:
- Defines fixed global constants:
  - `MAX_SEQ_LEN = 2048`
  - `TIME_BUDGET = 300`
  - `EVAL_TOKENS = 40 * 524288`
- Downloads dataset shards to `~/.cache/autoresearch/data`
- Trains tokenizer and persists artifacts to `~/.cache/autoresearch/tokenizer`
- Exposes runtime utilities imported by `train.py`:
  - `Tokenizer`
  - `make_dataloader(...)`
  - `evaluate_bpb(...)`

Important data split decision:
- Validation uses a pinned shard (`shard_06542.parquet`).
- Training excludes this shard.

### 2) Experiment Layer (`train.py`)

`train.py` is where experiments happen:
- Builds GPT-like architecture from a small set of top-level knobs (depth, aspect ratio, head dim, attention window pattern).
- Uses hybrid optimizer behavior:
  - Muon-style updates for matrix parameters.
  - AdamW-style updates for embeddings/head/scalar params.
- Applies progress-based schedules over a fixed-time run.
- Prints machine-readable end-of-run summary, including `val_bpb`, timing, VRAM, MFU, steps, and params.

The script is intentionally self-contained and avoids a config system or CLI for rapid edits.

## Main Data/Training Flows

## A) Data Preparation
1. Download selected training shards plus pinned validation shard.
2. Train BPE tokenizer from training split only.
3. Build `token_bytes.pt` lookup for byte-length-aware evaluation.
4. Store artifacts in user cache.

## B) Runtime Dataloader
1. Read parquet row groups.
2. Tokenize in batches and prepend BOS per document.
3. Pack documents into fixed-length rows using best-fit strategy.
4. Crop shortest doc when no full fit exists.
5. Create contiguous input/target tensors and yield CUDA batches.

This design prioritizes near-100% token utilization and deterministic input shape.

## C) Training + Evaluation
1. Initialize model and optimizer from static hyperparameter section.
2. Compute gradient accumulation from `TOTAL_BATCH_SIZE`.
3. Train until tracked training time reaches `TIME_BUDGET` (after warmup/compile-excluded early steps).
4. Run fixed `evaluate_bpb(...)` pass over validation tokens.
5. Emit summary metrics for experiment bookkeeping.

## D) Autonomous Agent Loop (`program.md`)
1. Create experiment branch.
2. Modify `train.py`.
3. Commit and run.
4. Parse metrics from logs.
5. Log result to `results.tsv`.
6. Keep or discard commit based on `val_bpb`.

## Design Strengths

- **Clear mutation boundary**: one editable file (`train.py`) reduces accidental scope creep.
- **Fair experiment comparator**: fixed time budget + fixed eval harness.
- **Low operational overhead**: no distributed systems complexity.
- **Reproducible dependencies**: lockfile-backed installs.
- **Practical reporting**: end-of-run summary is easy to parse and automate.

## Risks and Fragility Points

1. **Platform coupling**
   - Hard dependency on CUDA-capable NVIDIA setup.
   - No fallback paths for non-supported hardware.

2. **Kernel/runtime brittleness**
   - Runtime FA3 backend selection may break with package/driver drift.
   - `torch.compile` can produce version-sensitive failures.

3. **Data/schema assumptions**
   - Assumes parquet files have a `text` column and stable shard format.
   - No schema/version validation layer before training.

4. **Artifact trust model**
   - Tokenizer loaded with `pickle`; safe in trusted local workflows but not hardened against tampered artifacts.
   - Remote shard download retries exist, but there is no explicit checksum verification.

5. **No quality gates**
   - No tests, linting, type checking, or CI.
   - Autonomous edits can regress behavior without early detection.

6. **Complex packing logic without tests**
   - Best-fit/cropping dataloader logic is performance-friendly but nontrivial; edge-case regressions are hard to detect manually.

## Quality and Maintainability Assessment

Current maturity level: **research prototype**.

What is good:
- Narrowed problem scope and clear user/agent workflow.
- Strong conceptual docs for the experimentation model.
- Logical separation of fixed infra vs editable experiment surface.

What is missing:
- Verification safety net (tests + CI).
- Static code quality controls.
- Operational docs for failure handling and environment support matrix.

## Recommended Improvements (Prioritized)

1. **Add minimal CI checks**
   - Run `uv sync --frozen`.
   - Run lint/type checks.
   - Run a tiny smoke test target.

2. **Introduce static quality tooling**
   - Add `ruff` (lint/format).
   - Add `pyright` or `mypy` (type checks).

3. **Create targeted tests for critical invariants**
   - Dataloader output shapes and BOS alignment.
   - Tokenizer encode/decode roundtrip behavior.
   - Training step smoke (small tensor/model path).
   - Schedule behavior at boundary conditions.

4. **Harden data/artifact integrity**
   - Validate shard integrity with checksums or manifest.
   - Document trusted-local assumption for tokenizer artifacts.

5. **Improve contributor and ops docs**
   - Add `CONTRIBUTING.md` with required checks and experiment conventions.
   - Add troubleshooting for CUDA/kernel/runtime failures.

6. **Fill metadata/policy basics**
   - Add explicit `LICENSE` file (README says MIT).
   - Add `SECURITY.md` with reporting scope and trust assumptions.

## Suggested Follow-up Deep Dives

- Benchmark how dataloader packing policy affects token distribution and gradient signal.
- Add a lightweight experiment dashboard on top of `results.tsv`.
- Evaluate introducing a tiny config abstraction while preserving single-file edit ergonomics.

## Practical Commands (Current Workflow)

- Setup: `uv sync`
- Prepare data/tokenizer: `uv run prepare.py`
- Run one experiment: `uv run train.py`
- Analyze notebook output: open `analysis.ipynb`

