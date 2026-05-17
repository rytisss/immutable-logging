# `immutable_logging` Python Package Design

**Date:** 2026-05-17
**Branch:** `feature/packaging`
**Status:** Approved

## Goal

Turn the existing immutable-log code (currently flat Python modules at the repo root) into an installable Python package named `immutable_logging`. Users will install it from git (`pip install git+https://...`) and use the building-block handlers directly. PyPI publishing is set up but deferred.

## Decisions

| Decision | Choice |
| --- | --- |
| Public API style | Low-level only: handlers + verify function, no convenience wrapper |
| Package name | `immutable_logging` |
| immudb dependency | Optional extra: `pip install immutable_logging[immudb]` |
| Distribution (initial) | Git/wheel install only; PyPI deferred but pipeline ready |
| Build tool | `setuptools` with `pyproject.toml` |
| Source layout | `src/` layout |
| Python floor | `>=3.10` |
| Demo `main.py` | Move to `examples/basic_usage.py` |
| CLI | Yes — `verify-logs` console script |

## File Layout

```
immutable-log/
├── pyproject.toml
├── README.md                   # updated install + import paths
├── LICENSE
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── src/
│   └── immutable_logging/
│       ├── __init__.py         # re-exports public API
│       ├── integrity.py        # IntegrityHandler (renamed from integrity_handler.py)
│       ├── immudb.py           # ImmuDBHandler (renamed from immudb_handler.py)
│       ├── verify.py           # verify_log_integrity + VerifyResult
│       └── cli.py              # entry point for the `verify-logs` console script
├── tests/
│   ├── test_integrity.py       # moved from test_integrity_handler.py
│   ├── test_immudb.py          # moved from test_immudb_handler.py
│   └── test_verify.py          # moved from test_verify_logs.py
├── examples/
│   └── basic_usage.py          # moved from main.py
└── (requirements.txt removed — pyproject.toml is the source of truth)
```

Module renames are cosmetic. Public class names (`ImmuDBHandler`, `IntegrityHandler`) are unchanged. The `immutable_logging` namespace already provides context, so `immutable_logging.integrity` reads better than `immutable_logging.integrity_handler`.

The `IntegrityAwareRotatingHandler` from the current `main.py` is **not** part of the package — it was demo-level glue. The example file will still show how to compose it.

## Public API

```python
from immutable_logging import (
    IntegrityHandler,        # logging.Handler — SHA-256 hash chain to .integrity sidecar
    ImmuDBHandler,           # logging.Handler — writes to immudb (requires [immudb] extra)
    verify_log_integrity,    # (log_path) -> VerifyResult
    VerifyResult,            # dataclass
)
```

Submodule imports also work and are preferred for the optional handler:

```python
from immutable_logging.immudb import ImmuDBHandler  # ImportError if immudb-py not installed
```

### `VerifyResult`

Existing fields: `passed: bool`, `tampered: int`, `missing: int`, `no_integrity_file: bool`.

New: `.summary: str` property — one human-readable line, e.g.:
- `"OK: 1,247 entries verified"`
- `"FAILED: 3 tampered, 1 missing"`
- `"No previous integrity file found"`

The CLI prints `result.summary` so there's one source of truth between programmatic and shell use.

### CLI

`verify-logs <log_path>` — wraps `verify_log_integrity`, prints `result.summary` to stdout, exits 0 if `result.passed`, non-zero otherwise. Registered via `[project.scripts]` in `pyproject.toml`.

### Missing-extra handling

`immutable_logging.immudb` does `import immudb` at the top — `ImportError: No module named 'immudb'` if the extra isn't installed.

`from immutable_logging import ImmuDBHandler` uses a module-level `__getattr__` (PEP 562) in `__init__.py` to lazy-import `ImmuDBHandler` only when accessed. If `immudb-py` is missing, the `__getattr__` raises a friendlier error: `"ImmuDBHandler requires the [immudb] extra. Install with: pip install immutable_logging[immudb]"`. This means `import immutable_logging` itself never fails because immudb isn't installed.

## Dependencies (`pyproject.toml`)

- `requires-python = ">=3.10"`
- `dependencies = []` — base install has no runtime deps. `IntegrityHandler` and `verify_log_integrity` only use the stdlib.
- `[project.optional-dependencies]`:
  - `immudb = ["immudb-py>=1.5,<2"]` — floor matches the current pin in `requirements.txt` (`immudb-py==1.5.0`); upper bound guards against breaking changes in a future 2.x.
  - `dev = ["pytest>=7", "build"]`.
- `[project.scripts]`: `verify-logs = "immutable_logging.cli:main"`.
- Version: start at `0.1.0`. Stored as `__version__` in `src/immutable_logging/__init__.py` and read via `dynamic = ["version"]` so there's one source of truth.

## GitHub Actions Pipeline

### `ci.yml` — runs on every push and PR

- Matrix: Python 3.10, 3.11, 3.12, 3.13 on `ubuntu-latest`
- Steps: install with `pip install -e .[immudb,dev]`, run `pytest`
- Build wheel + sdist with `python -m build` and upload as a workflow artifact (lets you grab a built wheel from any green run without PyPI)

immudb-dependent tests are marked `@pytest.mark.immudb`. They're skipped in CI when no immudb server is reachable (matches the handler's existing graceful-fallback behavior).

### `release.yml` — triggered on git tags matching `v*`

- Builds wheel + sdist
- Publishes to PyPI using **trusted publishing** (OIDC) — no API token stored as a GitHub secret
- Configured now but inert until a tag is pushed

When ready to publish for real, one-time steps:
1. Reserve `immutable_logging` on PyPI (create the project).
2. Add this repo as a trusted publisher in the PyPI project settings.
3. Push a `v0.1.0` tag.

## Tests

Move existing tests under `tests/` and update imports:
- `from immudb_handler import ...` → `from immutable_logging.immudb import ...`
- `from integrity_handler import ...` → `from immutable_logging.integrity import ...`
- `from verify_logs import ...` → `from immutable_logging.verify import ...`

Tag immudb-server-required tests with `@pytest.mark.immudb`. Register the marker in `pyproject.toml` so pytest doesn't warn.

No new tests added — that's scope creep for this packaging work.

## README Changes

- Add an **Installation** section near the top. (Replace `<owner>` with the actual GitHub owner during implementation by reading `git remote get-url origin`.)
  - `pip install git+https://github.com/<owner>/immutable-log` (base, hash chain only)
  - `pip install 'immutable_logging[immudb] @ git+https://github.com/<owner>/immutable-log'` (with immudb)
- Update existing code snippets to use `from immutable_logging import ...`
- Existing Mode A / Mode B / Docker / auditor documentation stays as-is

## Out of Scope

- Publishing to PyPI (workflow set up but won't fire until a tag is pushed)
- High-level convenience function (`setup_immutable_logger`) — user chose low-level only
- Refactoring handler internals
- Adding new tests
- Changing existing logging/integrity/immudb behavior

## Acceptance

Done when:
- [ ] `pip install -e .` succeeds in a fresh venv on Python 3.10–3.13
- [ ] `pip install -e .[immudb]` succeeds and `from immutable_logging import ImmuDBHandler` works
- [ ] Without the `[immudb]` extra, `from immutable_logging import ImmuDBHandler` raises the friendly error message above
- [ ] `pytest` passes on all supported Python versions (immudb-marked tests skip when no server)
- [ ] `verify-logs cvdlink.log` runs and prints `result.summary`
- [ ] `python examples/basic_usage.py` runs and behaves identically to the current `python main.py`
- [ ] `python -m build` produces a wheel + sdist
- [ ] `ci.yml` runs green on a PR
- [ ] README install snippets work as written
