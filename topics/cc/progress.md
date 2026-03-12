# cc topic — experiment progress (branch: nar/cc/mar12)

## Score board

| iter | commit | score | fairness | status | description |
|------|--------|-------|----------|--------|-------------|
| baseline | 005b468 | 0.6879 | 0.949 | baseline | Unmodified NewReno-like cc-algo.cc |
| iter1 | 4e34cb5 | 0.6898 | ~0.960 | keep | Delay-gradient CA using `tcb->m_minRtt` (broken: minRtt=0, gradient rarely fired) |
| iter2 | 6e5abb4 | 0.6911 | 0.966 | keep | Own `m_baseRtt` via `PktsAcked`; gradient now uses true propagation delay |
| iter3 | 5269e31 | 0.6830 | — | discard | LEDBAT-style CA: cwnd oscillated below ssThresh, rebuilt queue continuously |
| iter4a | 50f09e9 | 0.6000 | 0.510 | discard | SS gating (no growth when queue high): killed fairness, flows starved |
| iter4b | fda75a5 | 0.6440 | 0.730 | discard | Delay-proportional ssThresh: hurt fairness; confirmed delay metric invariant |
| iter5 | 6d1bbb8 | 0.6894 | 0.957 | discard | Tight gradient kTarget=5ms kCeil=20ms: over-suppressed late-starting flows |
| iter5b | 836cebe | **0.6944** | 0.982 | **keep** | Looser gradient kTarget=12ms kCeil=50ms (linear); fairness +0.033 vs baseline |
| iter6 | 5c5c8bb | 0.6890 | 0.955 | discard | kTarget=15ms kCeil=60ms: threshold too high, gradient rarely fired |
| iter7 | 4811c43 | 0.6874 | 0.947 | discard | kTarget=12ms kCeil=70ms: wider ramp reduced moderation of established flows |
| iter8 | e9da063 | **0.6949** | 0.984 | **keep** | Squared scale `t²` (kTarget=12ms kCeil=50ms); more aggressive suppression |
| iter9 | 2f9f373 | 0.6865 | 0.943 | discard | Cubic scale `t³`: over-suppressed ALL flows including late ones |
| iter10 | c899d0a | 0.6940 | 0.980 | discard | `t²` kTarget=10ms: earlier onset → worse than 12ms |
| iter11 | 62bd7b6 | 0.6933 | 0.976 | discard | `t²` kTarget=13ms: slightly later onset → worse than 12ms |
| iter12 | ee370c9 | 0.6904 | 0.962 | discard | `t²` kCeil=40ms narrower ramp: too aggressive cutoff |
| iter13 | 64c1ada | 0.6941 | 0.980 | discard | SS brake for established flows: backfired, slowed new flows too |

**Current best: iter8 — score 0.6949, fairness 0.984**

---

## Key discoveries

### 1. Delay is invariant (critical insight)
`avg_rtt_ms` = **54.86 ms** in every experiment, identical to the Cubic baseline (54.857 ms).
FqCoDel with its CoDel AQM controls bottleneck queue depth deterministically regardless of CC algorithm. The delay score term (weight 0.30) is effectively **zero** for any algorithm running on this topology.

### 2. Score breakdown (iter8)
```
score = 0.30 * (throughput / cubic_tp)       → 0.30 * (9.64/9.638) ≈ 0.300
      + 0.30 * (1 - delay / cubic_delay)     → 0.30 * (1 - 54.86/54.857) ≈ 0.000
      + 0.20 * fairness                       → 0.20 * 0.984         = 0.197
      + 0.20 * (1 - adaptation_s / 10)       → 0.20 * 0.99          = 0.198
                                                                 total = 0.695
```

### 3. Metric sources (from evaluate.py)
- `throughput_mbps` and `avg_rtt_ms` — **scenario_a only** (single flow, 60 s)
- `fairness_index` — **scenario_b only** (5 staggered flows: start t=2,6,10,14,18 s)
- `adaptation_s` — **scenario_c only** (bandwidth halves at t=30 s, restores at t=45 s)

### 4. Structural fairness ceiling
Jain's fairness index is computed from `throughput_mbps = total_rx_bytes / 60s`. With 5 flows running for 58/54/50/46/42 seconds respectively, equal per-second rates give:

```
J_max = (58+54+50+46+42)² / (5 × (58²+54²+50²+46²+42²)) = 62500/63300 ≈ 0.987
```

Achieving J=1.0 is structurally impossible. Current best (0.984) is 0.003 below ceiling.

### 5. Adaptation is already at minimum
`adaptation_s = 0.10 s` = one timeseries sample interval after t=45 s. Cannot improve.

### 6. Throughput at Cubic parity
Our throughput (9.64 Mbps) ≈ Cubic's (9.638 Mbps) in scenario_a (single flow on 10 Mbps link). Both are bounded by the link capacity.

---

## Current algorithm (iter8)

```cpp
// Slow start: standard NewReno (+1 MSS per ACK)
// New flows (m_baseRtt=0): no delay gradient applied

// Congestion avoidance: squared delay-gradient
double scale = 1.0;
double qd_ms = (lastRtt - m_baseRtt).GetMilliSeconds();
const double kTarget = 12.0;  // start scaling at 12 ms of queuing
const double kCeil   = 50.0;  // zero growth at 50 ms of queuing
if (qd_ms >= kCeil)
    scale = 0.0;
else if (qd_ms > kTarget)
{
    double t = (kCeil - qd_ms) / (kCeil - kTarget);
    scale = t * t;  // squared for steeper suppression
}
cwnd += max(1, mss²/cwnd) * segmentsAcked * scale;

// PktsAcked: track all-time minimum RTT as m_baseRtt
// GetSsThresh: standard max(2*MSS, bytesInFlight/2)
```

**Why it works:** Flows that started earlier have a lower `m_baseRtt` (measured when the queue was empty). Later-starting flows begin when some queue already exists, so their `m_baseRtt` is higher. At the same absolute RTT, earlier flows see higher `qd_ms` → lower `scale` → slower CA growth → later flows catch up.

---

## kTarget/kCeil sensitivity (linear scale)

| kTarget | kCeil | fairness | score |
|---------|-------|----------|-------|
| 5 ms | 20 ms | 0.957 | 0.6894 |
| 8 ms | 30 ms | 0.966 | 0.6911 |
| **12 ms** | **50 ms** | **0.982** | **0.6944** |
| 15 ms | 60 ms | 0.955 | 0.6890 |

## Scale exponent sensitivity (kTarget=12ms, kCeil=50ms)

| exponent | fairness | score |
|----------|----------|-------|
| t¹ (linear) | 0.982 | 0.6944 |
| **t² (squared)** | **0.984** | **0.6949** |
| t³ (cubic) | 0.943 | 0.6865 |

## kTarget sweep with t² scale

| kTarget | fairness | score |
|---------|----------|-------|
| 10 ms | 0.980 | 0.6940 |
| **12 ms** | **0.984** | **0.6949** |
| 13 ms | 0.976 | 0.6933 |

## kCeil sweep with t² scale (kTarget=12ms)

| kCeil | fairness | score |
|-------|----------|-------|
| 40 ms | 0.962 | 0.6904 |
| **50 ms** | **0.984** | **0.6949** |
| 70 ms | 0.947 | 0.6874 |

---

## Score ceiling analysis

| component | current | theoretical max | gap |
|-----------|---------|-----------------|-----|
| throughput (×0.30) | 0.300 | 0.300 | ~0 |
| delay (×0.30) | 0.000 | 0.000 (invariant) | 0 |
| fairness (×0.20) | 0.197 | 0.197 (J=0.987) | 0.001 |
| adaptation (×0.20) | 0.198 | 0.200 | 0.002 |
| **total** | **0.6949** | **~0.6954** | **~0.0005** |

Remaining headroom is approximately **0.0005 score points**.

---

## Failed directions (do not retry)

- **LEDBAT-style active cwnd reduction in CA** — oscillates below ssThresh → throughput loss
- **Slow start gating** (no SS growth when qd high) — starves fairness, flows can't ramp up
- **Delay-proportional ssThresh** — all flows equally affected on loss, no fairness benefit
- **kCeil widening** (≥ 70ms) — too loose, gradient rarely fires, reverts toward baseline
- **t³ scale** — over-suppresses all flows including late ones (fairness collapses to 0.943)
- **SS brake for established flows** — delays new-flow SS ramp-up too (fairness 0.980)
