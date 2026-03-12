# nar

`nar` is a multi-topic network auto research framework built on `ns-3`.

The repository is organized so each research topic has:
- a fixed simulation/evaluation harness,
- a small editable C++ surface,
- an automated keep/discard experiment loop.

Congestion control is the first implemented topic at `topics/cc`.

## Repository layout

```
nar/
├── third_party/ns-3-dev/      # git submodule (version-pinned ns-3)
├── lib/ns3.py                 # shared ns-3 helper utilities
├── topics/                    # one directory per research topic
│   └── cc/                    # congestion-control topic
├── artifacts/                 # runtime traces/results (gitignored)
└── .cursor/rules/             # project rules
```

## ns-3 dependency policy

`ns-3` is tracked as a git submodule at `third_party/ns-3-dev`. The parent repo
pins an exact commit, which locks everyone to the same simulator version.

Initialize submodules after cloning:

```bash
git submodule update --init --recursive
```

To bump ns-3 later:
1. Checkout a new ns-3 tag inside `third_party/ns-3-dev`.
2. Stage `third_party/ns-3-dev` in the parent repo.
3. Commit the updated submodule pointer.

## Setup

Requirements:
- Python 3.10+
- `uv`
- C/C++ toolchain available in `PATH` (or set `NAR_TOOLCHAIN_BIN`)

Install dependencies:

```bash
uv sync
```

Prepare congestion-control topic (one-time):

```bash
uv run topics/cc/prepare.py
```

Run one experiment:

```bash
uv run topics/cc/run.py
```

## Topic contract (for future expansion)

Every topic should follow:

```
topics/<name>/
├── program.md
├── prepare.py
├── run.py
├── evaluate.py
├── src/       # editable C++ files
└── infra/     # fixed scenario + baselines
```

with runtime output at:

```
artifacts/<name>/
```

This structure supports additional domains such as topology design and protocol
design while reusing the same submodule and shared helpers.
