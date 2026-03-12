# nar topics/cc

Autonomous congestion-control research loop using `ns-3`.

## Setup

Before experimentation, complete this setup with the user:

1. **Agree on a run tag** (example: `mar12`).
2. **Create branch**: `git checkout -b nar/cc/<tag>`.
3. **Read in-scope files**:
   - `topics/cc/src/cc-algo.h`
   - `topics/cc/src/cc-algo.cc`
   - `topics/cc/infra/scenario.cc`
   - `topics/cc/evaluate.py`
   - `topics/cc/run.py`
4. **Verify ns-3 setup exists**:
   - Check `third_party/ns-3-dev`.
   - If missing, ask human to run `git submodule update --init --recursive`.
5. **Initialize results.tsv** if absent:
   - `artifacts/cc/results.tsv`
   - Header: `commit	score	build_ok	status	description`
6. **Run baseline first**:
   - `uv run topics/cc/run.py > run.log 2>&1`
   - Parse `score` from log.
   - Record as baseline.

## Rules

What you can modify:
- `topics/cc/src/cc-algo.cc` (primary editable surface)
- `topics/cc/src/cc-algo.h` (if required)

What you cannot modify during experiment loop:
- `topics/cc/infra/scenario.cc`
- `topics/cc/evaluate.py`
- `topics/cc/run.py`
- baseline files

Goal:
- **Maximize `score`** (higher is better).

Time budget:
- `topics/cc/run.py` enforces a strict 3-minute wall-clock budget.

## Experiment Loop

LOOP FOREVER:

1. Inspect current git state and baseline score.
2. Edit `topics/cc/src/cc-algo.cc` with one networking idea.
3. Commit the change.
4. Run experiment: `uv run topics/cc/run.py > run.log 2>&1`
5. Parse key lines:
   - `score`
   - `throughput_mbps`
   - `avg_rtt_ms`
   - `fairness_index`
   - `adaptation_s`
6. If missing score output, treat as failure:
   - `build_ok = 0`
   - status = `crash`
7. Log to `artifacts/cc/results.tsv`:
   - `commit	score	build_ok	status	description`
8. Keep/discard policy:
   - If score improved: status = `keep`
   - If score worse or equal: status = `discard`, reset commit

Never stop the loop unless the human interrupts.

## Research Directions

Prioritize these ideas:

1. Delay-sensitive control:
   - Use RTT trend or queueing delay growth to cap cwnd growth.
2. Hybrid loss+delay:
   - Loss for hard backoff, delay for proactive moderation.
3. Pacing-informed behavior:
   - Estimate delivery rate and avoid bursty overshoot.
4. AIMD schedule variants:
   - Adaptive additive and multiplicative factors by congestion phase.
5. State-aware strategies:
   - Different logic in startup, drain, and steady-state.

## Common Pitfalls

- Integer overflow in cwnd math.
- Divide-by-zero when RTT or bytes-in-flight is zero.
- Starvation/unfairness in multi-flow scenarios.
- Overly aggressive growth that improves throughput but tanks fairness/delay.
- Build breakage from missing includes or wrong ns3 namespace usage.
