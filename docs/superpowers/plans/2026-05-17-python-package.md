# `immutable_logging` Python Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the existing flat repo into an installable Python package `immutable_logging`, with src/ layout, optional `[immudb]` extra, `verify-logs` CLI, and GitHub Actions CI + (deferred-but-ready) PyPI release workflow.

**Architecture:** Modules move from repo root into `src/immutable_logging/`. The package is installed editable for development (`pip install -e .[immudb,dev]`). The public API in `__init__.py` re-exports building-block handlers and uses PEP 562 `__getattr__` to lazy-import `ImmuDBHandler` so users without the optional `immudb-py` dependency can still import the package. The `verify-logs` console script wraps `verify_log_integrity` and prints `result.summary` (a new one-line property on `VerifyResult`).

**Tech Stack:** Python 3.10+, setuptools (PEP 621 `pyproject.toml`), pytest, immudb-py (optional), GitHub Actions, PyPI trusted publishing.

**Commit conventions for this plan:**
- No Conventional Commits prefixes (no `feat:`, `fix:`, `docs:`, etc.) — write plain sentences.
- Do **not** add a `Co-Authored-By: Claude ...` trailer.
- Each task ends with a single commit (or a brief sequence of commits if a task naturally splits).

---

## File Structure

**Created:**
- `pyproject.toml`
- `src/immutable_logging/__init__.py`
- `src/immutable_logging/integrity.py` (from `integrity_handler.py`)
- `src/immutable_logging/immudb.py` (from `immudb_handler.py`)
- `src/immutable_logging/verify.py` (from `verify_logs.py`)
- `src/immutable_logging/cli.py`
- `tests/__init__.py`
- `tests/test_integrity.py` (from `test_integrity_handler.py`)
- `tests/test_immudb.py` (from `test_immudb_handler.py`)
- `tests/test_verify.py` (from `test_verify_logs.py`)
- `tests/test_summary.py`
- `tests/test_cli.py`
- `tests/test_public_api.py`
- `examples/basic_usage.py` (from `main.py`)
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

**Modified:**
- `README.md` (add Installation section, update import paths in examples)

**Deleted:**
- `integrity_handler.py`, `immudb_handler.py`, `verify_logs.py`, `main.py` (moved)
- `test_integrity_handler.py`, `test_immudb_handler.py`, `test_verify_logs.py` (moved)
- `requirements.txt` (superseded by `pyproject.toml`)
- `__pycache__/`, `cvdlink.log`, `cvdlink.log.integrity` (gitignore artifacts; should already be ignored)

---

## Task 1: Package Skeleton + Editable Install

Set up the minimum `pyproject.toml` and an empty `src/immutable_logging/` so that `pip install -e .[dev]` succeeds and `import immutable_logging` works. No code moved yet.

**Files:**
- Create: `pyproject.toml`
- Create: `src/immutable_logging/__init__.py`

- [ ] **Step 1: Create the package directory and an empty `__init__.py` with a version constant**

```python
# src/immutable_logging/__init__.py
"""Immutable logging primitives: SHA-256 hash-chain integrity + optional immudb backend."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "immutable_logging"
description = "Immutable logging for Python: SHA-256 hash-chain integrity, with optional immudb backend."
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
authors = [{ name = "Rytis" }]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: System :: Logging",
]
dependencies = []
dynamic = ["version"]

[project.optional-dependencies]
immudb = ["immudb-py>=1.5,<2"]
dev = ["pytest>=7", "build"]

[project.scripts]
verify-logs = "immutable_logging.cli:main"

[project.urls]
Homepage = "https://github.com/rytisss/immutable-log"

[tool.setuptools.dynamic]
version = { attr = "immutable_logging.__version__" }

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "immudb: marks tests that require a running immudb server (deselect with '-m \"not immudb\"')",
]
```

> **Note:** Adjust `authors` and `Homepage` URL during execution if the repo's git remote points somewhere different. Run `git remote get-url origin` to confirm.

- [ ] **Step 3: Verify the package installs editable and imports**

Run:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import immutable_logging; print(immutable_logging.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 4: Add `.venv/` and build artifacts to `.gitignore` if not already present**

Append these patterns to `.gitignore` if missing:
```
.venv/
build/
dist/
*.egg-info/
```

Check first with `grep -E '^\.venv/|^build/|^dist/|egg-info' .gitignore` — only add what's missing.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/immutable_logging/__init__.py .gitignore
git commit -m "Add pyproject.toml and empty immutable_logging package skeleton"
```

---

## Task 2: Move IntegrityHandler into the package

Move `integrity_handler.py` to `src/immutable_logging/integrity.py` and the corresponding test to `tests/test_integrity.py`, updating imports. Verify behavior is unchanged.

**Files:**
- Create: `src/immutable_logging/integrity.py` (contents copied verbatim from `integrity_handler.py`)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_integrity.py` (contents from `test_integrity_handler.py`, with import line updated)
- Delete: `integrity_handler.py`, `test_integrity_handler.py`

- [ ] **Step 1: Copy `integrity_handler.py` to `src/immutable_logging/integrity.py` unchanged**

Run:
```bash
cp integrity_handler.py src/immutable_logging/integrity.py
```

Verify identical contents (sanity check):
```bash
diff integrity_handler.py src/immutable_logging/integrity.py
```
Expected: no output (files are identical).

- [ ] **Step 2: Create empty `tests/__init__.py`**

```python
# tests/__init__.py
```

- [ ] **Step 3: Copy the test file and update its import**

Run:
```bash
cp test_integrity_handler.py tests/test_integrity.py
```

Then edit `tests/test_integrity.py` and change:
```python
from integrity_handler import IntegrityHandler
```
to:
```python
from immutable_logging.integrity import IntegrityHandler
```

- [ ] **Step 4: Run the moved tests and verify they pass**

Run:
```bash
pytest tests/test_integrity.py -v
```

Expected: all tests pass (same set as `test_integrity_handler.py` previously). If any fail, investigate before moving on — they were passing before the move so any failure indicates a path or import problem.

- [ ] **Step 5: Delete the old files**

```bash
git rm integrity_handler.py test_integrity_handler.py
```

- [ ] **Step 6: Commit**

```bash
git add src/immutable_logging/integrity.py tests/__init__.py tests/test_integrity.py
git commit -m "Move IntegrityHandler into immutable_logging.integrity"
```

---

## Task 3: Move verify module + rename `VerificationResult` → `VerifyResult`

Move `verify_logs.py` to `src/immutable_logging/verify.py` and rename the dataclass `VerificationResult` to `VerifyResult` (the public name agreed in the spec). Move tests and update imports.

**Files:**
- Create: `src/immutable_logging/verify.py`
- Create: `tests/test_verify.py`
- Delete: `verify_logs.py`, `test_verify_logs.py`

- [ ] **Step 1: Copy `verify_logs.py` to `src/immutable_logging/verify.py`**

Run:
```bash
cp verify_logs.py src/immutable_logging/verify.py
```

- [ ] **Step 2: Rename the dataclass `VerificationResult` to `VerifyResult` in the new file**

In `src/immutable_logging/verify.py`, change:
```python
@dataclass
class VerificationResult:
```
to:
```python
@dataclass
class VerifyResult:
```

And update the one internal reference inside `verify_log_integrity`:
```python
result = VerificationResult()
```
to:
```python
result = VerifyResult()
```

Also remove the CLI `main()` function and its `if __name__ == "__main__":` block from this file — the CLI will live in its own `cli.py` module (Task 6). After removal, also remove the now-unused imports at the top: `argparse` and `sys`. Keep `hashlib`, `os`, and the `dataclass`/`field` imports.

The resulting top of the file should be:
```python
import hashlib
import os
from dataclasses import dataclass, field

GENESIS_HASH = "0" * 64


@dataclass
class VerifyResult:
    passed: bool = True
    tampered: int = 0
    missing: int = 0
    tampered_lines: list = field(default_factory=list)
    missing_lines: list = field(default_factory=list)
    no_integrity_file: bool = False
    details: list = field(default_factory=list)


def verify_log_integrity(log_path):
    ...  # unchanged body, but uses VerifyResult() instead of VerificationResult()
```

- [ ] **Step 3: Copy `test_verify_logs.py` to `tests/test_verify.py` and update its import**

```bash
cp test_verify_logs.py tests/test_verify.py
```

Edit `tests/test_verify.py` and change:
```python
from verify_logs import verify_log_integrity
```
to:
```python
from immutable_logging.verify import verify_log_integrity
```

The existing tests don't reference `VerificationResult` by name (they only use `.passed`, `.tampered`, `.missing` attributes), so no other test changes are needed.

- [ ] **Step 4: Run the moved tests**

```bash
pytest tests/test_verify.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Delete the old files**

```bash
git rm verify_logs.py test_verify_logs.py
```

- [ ] **Step 6: Commit**

```bash
git add src/immutable_logging/verify.py tests/test_verify.py
git commit -m "Move verify_log_integrity into immutable_logging.verify and rename result class to VerifyResult"
```

---

## Task 4: Add `VerifyResult.summary` property (TDD)

Add a `.summary` property that returns a single human-readable line describing the verification outcome. This is the property the spec promised, used by both programmatic callers and the CLI.

**Files:**
- Modify: `src/immutable_logging/verify.py`
- Create: `tests/test_summary.py`

- [ ] **Step 1: Write failing tests for `VerifyResult.summary`**

Create `tests/test_summary.py`:
```python
from immutable_logging.verify import VerifyResult


def test_summary_when_passed():
    r = VerifyResult(passed=True, tampered=0, missing=0)
    # Track entry count via the details list (one detail per verified line).
    r.details = ["Line 1: OK", "Line 2: OK", "Line 3: OK"]
    assert r.summary == "OK: 3 entries verified"


def test_summary_when_no_integrity_file():
    r = VerifyResult(passed=False, no_integrity_file=True)
    assert r.summary == "No previous integrity file found"


def test_summary_when_tampered_only():
    r = VerifyResult(passed=False, tampered=3, missing=0)
    assert r.summary == "FAILED: 3 tampered, 0 missing"


def test_summary_when_missing_only():
    r = VerifyResult(passed=False, tampered=0, missing=2)
    assert r.summary == "FAILED: 0 tampered, 2 missing"


def test_summary_when_both_tampered_and_missing():
    r = VerifyResult(passed=False, tampered=4, missing=1)
    assert r.summary == "FAILED: 4 tampered, 1 missing"


def test_summary_thousand_separator():
    r = VerifyResult(passed=True)
    r.details = ["Line {}: OK".format(i) for i in range(1, 1248)]
    assert r.summary == "OK: 1,247 entries verified"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_summary.py -v
```

Expected: all six tests fail with `AttributeError: 'VerifyResult' object has no attribute 'summary'`.

- [ ] **Step 3: Add the `summary` property to `VerifyResult`**

In `src/immutable_logging/verify.py`, add the property at the end of the `VerifyResult` class:

```python
@dataclass
class VerifyResult:
    passed: bool = True
    tampered: int = 0
    missing: int = 0
    tampered_lines: list = field(default_factory=list)
    missing_lines: list = field(default_factory=list)
    no_integrity_file: bool = False
    details: list = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.no_integrity_file:
            return "No previous integrity file found"
        if self.passed:
            count = len(self.details)
            return f"OK: {count:,} entries verified"
        return f"FAILED: {self.tampered:,} tampered, {self.missing:,} missing"
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_summary.py -v
```

Expected: all six tests pass. Also re-run the verify tests to make sure nothing regressed:

```bash
pytest tests/test_verify.py tests/test_summary.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/immutable_logging/verify.py tests/test_summary.py
git commit -m "Add VerifyResult.summary one-line human-readable property"
```

---

## Task 5: Move ImmuDBHandler + mark immudb tests

Move `immudb_handler.py` to `src/immutable_logging/immudb.py` and the test to `tests/test_immudb.py`, updating imports. Mark the entire `test_immudb.py` module with `pytest.mark.immudb` so CI without an immudb server can skip it cleanly.

**Files:**
- Create: `src/immutable_logging/immudb.py`
- Create: `tests/test_immudb.py`
- Delete: `immudb_handler.py`, `test_immudb_handler.py`

- [ ] **Step 1: Copy `immudb_handler.py` to `src/immutable_logging/immudb.py`**

```bash
cp immudb_handler.py src/immutable_logging/immudb.py
```

No code changes inside the file. The top-level `from immudb.client import ImmudbClient` import stays — it's what raises a clean `ImportError` if the `[immudb]` extra is not installed.

- [ ] **Step 2: Copy `test_immudb_handler.py` to `tests/test_immudb.py` and update imports**

```bash
cp test_immudb_handler.py tests/test_immudb.py
```

In `tests/test_immudb.py`:
- Change `from immudb_handler import ImmuDBHandler` → `from immutable_logging.immudb import ImmuDBHandler`
- Change the two occurrences of `from verify_logs import verify_log_integrity` (lines 366 and 376 of the original) → `from immutable_logging.verify import verify_log_integrity`

- [ ] **Step 3: Add the `pytest.mark.immudb` marker at module level**

At the top of `tests/test_immudb.py`, after the existing imports, add:
```python
import pytest

pytestmark = pytest.mark.immudb
```

This applies the `immudb` marker to every test in the module. The marker was already registered in `pyproject.toml` in Task 1.

> **Note:** These tests use `unittest.mock.patch` to stub the immudb client, so they don't actually require a running immudb server. The marker exists for users/CI that want to opt out of any immudb-related code paths, not because the tests will fail without a server. This is intentional: the marker is a label, not a skip.

- [ ] **Step 4: Run the moved tests**

```bash
pytest tests/test_immudb.py -v
```

Expected: all tests pass (same as before the move).

Also try the skip behavior:
```bash
pytest tests/test_immudb.py -v -m "not immudb"
```

Expected: all tests deselected, exit 0.

- [ ] **Step 5: Delete the old files**

```bash
git rm immudb_handler.py test_immudb_handler.py
```

- [ ] **Step 6: Commit**

```bash
git add src/immutable_logging/immudb.py tests/test_immudb.py
git commit -m "Move ImmuDBHandler into immutable_logging.immudb and mark its tests with the immudb pytest marker"
```

---

## Task 6: Wire public re-exports + PEP 562 lazy ImmuDBHandler

Expose the public API from `immutable_logging` and use PEP 562 `__getattr__` so importing `ImmuDBHandler` from the top-level namespace raises a helpful error when the `[immudb]` extra is missing, without affecting `import immutable_logging` itself.

**Files:**
- Modify: `src/immutable_logging/__init__.py`
- Create: `tests/test_public_api.py`

- [ ] **Step 1: Write failing tests for the public API**

Create `tests/test_public_api.py`:
```python
import importlib
import sys
import builtins

import pytest


def test_eager_exports_present():
    import immutable_logging

    assert hasattr(immutable_logging, "IntegrityHandler")
    assert hasattr(immutable_logging, "verify_log_integrity")
    assert hasattr(immutable_logging, "VerifyResult")
    assert hasattr(immutable_logging, "__version__")


def test_import_package_does_not_require_immudb(monkeypatch):
    """`import immutable_logging` must not import `immudb` even transitively."""
    # Force a re-import in an environment where 'immudb' is unimportable.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "immudb" or name.startswith("immudb."):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Drop cached package + submodules so it re-imports under our patched __import__.
    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]

    importlib.import_module("immutable_logging")  # must not raise


def test_top_level_immudb_handler_access_without_extra_raises_friendly_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "immudb" or name.startswith("immudb."):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]

    import immutable_logging

    with pytest.raises(ImportError) as exc_info:
        _ = immutable_logging.ImmuDBHandler

    msg = str(exc_info.value)
    assert "immudb" in msg
    assert "pip install immutable_logging[immudb]" in msg


def test_top_level_immudb_handler_access_with_extra_returns_class():
    """When immudb-py IS installed, the lazy attribute returns the real class."""
    pytest.importorskip("immudb")
    # Ensure a clean import
    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]
    import immutable_logging
    from immutable_logging.immudb import ImmuDBHandler as Direct
    assert immutable_logging.ImmuDBHandler is Direct
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_public_api.py -v
```

Expected: `test_eager_exports_present` and both top-level access tests fail because `__init__.py` only defines `__version__`. The "does not require immudb" test should pass already (current `__init__.py` doesn't import anything).

- [ ] **Step 3: Implement the public API in `__init__.py`**

Replace `src/immutable_logging/__init__.py` with:

```python
"""Immutable logging primitives: SHA-256 hash-chain integrity + optional immudb backend."""

from immutable_logging.integrity import IntegrityHandler
from immutable_logging.verify import VerifyResult, verify_log_integrity

__version__ = "0.1.0"

__all__ = [
    "IntegrityHandler",
    "ImmuDBHandler",
    "VerifyResult",
    "verify_log_integrity",
    "__version__",
]


def __getattr__(name):
    """PEP 562 module-level __getattr__: lazy-load ImmuDBHandler.

    The immudb submodule does `from immudb.client import ImmudbClient` at the top,
    so it will raise ImportError if the [immudb] extra is not installed. We catch
    that and re-raise with a friendlier message pointing at the install command.
    """
    if name == "ImmuDBHandler":
        try:
            from immutable_logging.immudb import ImmuDBHandler
        except ImportError as exc:
            raise ImportError(
                "ImmuDBHandler requires the [immudb] extra. "
                "Install with: pip install immutable_logging[immudb]"
            ) from exc
        return ImmuDBHandler
    raise AttributeError(f"module 'immutable_logging' has no attribute {name!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_public_api.py -v
```

Expected: all four tests pass. Also run the full test suite to confirm no regressions:

```bash
pytest -v
```

Expected: everything passes (or `test_immudb.py` is skipped if you ran with `-m "not immudb"`).

- [ ] **Step 5: Commit**

```bash
git add src/immutable_logging/__init__.py tests/test_public_api.py
git commit -m "Expose IntegrityHandler, VerifyResult, verify_log_integrity, and lazy ImmuDBHandler from package root"
```

---

## Task 7: `verify-logs` CLI + tests

Add the `cli.py` module that backs the `verify-logs` console_script. The script prints `result.summary` and exits with code 0 if `result.passed`, non-zero otherwise.

**Files:**
- Create: `src/immutable_logging/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for the CLI**

Create `tests/test_cli.py`:
```python
import subprocess
import sys
import tempfile
import logging
from pathlib import Path

import pytest

from immutable_logging.integrity import IntegrityHandler


def _write_intact_log(tmp_path: Path) -> Path:
    """Create a small log + matching .integrity sidecar."""
    log_path = tmp_path / "app.log"
    integrity_path = Path(str(log_path) + ".integrity")

    handler = IntegrityHandler(str(integrity_path))
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("cli-test-intact")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    with open(log_path, "w") as f:
        for msg in ["one", "two", "three"]:
            f.write(msg + "\n")
            handler.emit(logging.LogRecord("cli-test-intact", logging.INFO, __file__, 0, msg, None, None))
    handler.close()
    return log_path


def test_cli_passes_on_intact_log(tmp_path):
    log_path = _write_intact_log(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK:" in proc.stdout


def test_cli_fails_on_missing_integrity_file(tmp_path):
    log_path = tmp_path / "no-integrity.log"
    log_path.write_text("hello\n")
    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "No previous integrity file found" in proc.stdout


def test_cli_fails_on_missing_log_file(tmp_path):
    log_path = tmp_path / "does-not-exist.log"
    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    # Some message about the file being missing
    combined = proc.stdout + proc.stderr
    assert str(log_path) in combined


def test_installed_console_script_is_on_path(tmp_path):
    """The `verify-logs` entry point declared in pyproject.toml is installed."""
    log_path = _write_intact_log(tmp_path)
    proc = subprocess.run(
        ["verify-logs", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK:" in proc.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py -v
```

Expected: all four tests fail — `python -m immutable_logging.cli` and `verify-logs` don't exist yet.

- [ ] **Step 3: Implement `src/immutable_logging/cli.py`**

```python
"""Console-script entry point for `verify-logs`."""

import argparse
import os
import sys

from immutable_logging.verify import verify_log_integrity


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="verify-logs",
        description="Verify a log file against its .integrity sidecar.",
    )
    parser.add_argument("log_file", help="Path to the log file to verify")
    args = parser.parse_args(argv)

    if not os.path.exists(args.log_file):
        print(f"Log file not found: {args.log_file}", file=sys.stderr)
        return 2

    result = verify_log_integrity(args.log_file)
    print(result.summary)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Re-install editable so the console_script is registered**

The `[project.scripts]` entry was added in Task 1's `pyproject.toml`, but the `verify-logs` script is only created on (re)install. Run:

```bash
pip install -e ".[dev]"
```

Verify the entry point exists:
```bash
which verify-logs
```
Expected: a path inside `.venv/bin/`.

- [ ] **Step 5: Run the CLI tests to verify they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: all four tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/immutable_logging/cli.py tests/test_cli.py
git commit -m "Add verify-logs CLI wrapping verify_log_integrity"
```

---

## Task 8: Move `main.py` to `examples/basic_usage.py`

Move the demo script to `examples/` and update its imports to use the installed package. Behavior must be identical when run.

**Files:**
- Create: `examples/basic_usage.py`
- Delete: `main.py`

- [ ] **Step 1: Copy `main.py` to `examples/basic_usage.py`**

```bash
mkdir -p examples
cp main.py examples/basic_usage.py
```

- [ ] **Step 2: Update imports in `examples/basic_usage.py`**

Change the import block from:
```python
from immudb_handler import ImmuDBHandler
from integrity_handler import IntegrityHandler
from verify_logs import verify_log_integrity
```
to:
```python
from immutable_logging.immudb import ImmuDBHandler
from immutable_logging.integrity import IntegrityHandler
from immutable_logging.verify import verify_log_integrity
```

The `IntegrityAwareRotatingHandler` class stays defined locally in this example file — it was never part of the package's public surface; it's demo-level glue.

- [ ] **Step 3: Run the example end-to-end**

From the repo root:
```bash
python examples/basic_usage.py
```

Expected:
- It writes log entries at all levels (matches the original `main.py` behavior).
- If immudb is not running, prints `--- immudb not available, logs written to file and console ---`.
- A `cvdlink.log` and `cvdlink.log.integrity` file are written in the current directory (matching original behavior).

Clean up after testing:
```bash
rm -f cvdlink.log cvdlink.log.integrity cvdlink.log.1 cvdlink.log.2 cvdlink.log.3 cvdlink.log.4 cvdlink.log.5
```

- [ ] **Step 4: Delete `main.py`**

```bash
git rm main.py
```

- [ ] **Step 5: Commit**

```bash
git add examples/basic_usage.py
git commit -m "Move demo from main.py to examples/basic_usage.py with package imports"
```

---

## Task 9: Update README

Add an Installation section and update code examples to use the new import paths.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Determine the GitHub owner**

Run:
```bash
git remote get-url origin
```

Note the owner (the segment between `github.com[:/]` and `/immutable-log`). The examples below assume `rytisss` — replace with the actual owner.

- [ ] **Step 2: Add an Installation section right after the project description**

Open `README.md` and find the line `## Two ways to use it`. Insert a new section directly *before* it:

```markdown
## Installation

Install the base package (hash-chain integrity, stdlib only):

```bash
pip install git+https://github.com/<owner>/immutable-log
```

To also use the immudb handler, install with the `immudb` extra:

```bash
pip install 'immutable_logging[immudb] @ git+https://github.com/<owner>/immutable-log'
```

After install, the public API is:

```python
from immutable_logging import (
    IntegrityHandler,        # SHA-256 hash chain to a .integrity sidecar
    ImmuDBHandler,           # immudb backend (needs [immudb] extra)
    verify_log_integrity,    # programmatic verification
    VerifyResult,            # result dataclass with .passed and .summary
)
```

A CLI is also installed:

```bash
verify-logs path/to/app.log
```
```

(Substitute the actual `<owner>` from Step 1.)

- [ ] **Step 3: Update existing code snippets in README to use package imports**

Scan the README for any `from immudb_handler import`, `from integrity_handler import`, or `from verify_logs import` references and update them to the corresponding `immutable_logging.*` paths. Also update any references that say "run `python main.py`" to "run `python examples/basic_usage.py`".

Run to find candidates:
```bash
grep -n "main\.py\|immudb_handler\|integrity_handler\|verify_logs\.py" README.md
```

Update each hit accordingly.

- [ ] **Step 4: Sanity-check the install snippet works**

In a fresh venv (different from `.venv` so the local editable install doesn't mask anything), run:
```bash
python -m venv /tmp/imlog-install-test
/tmp/imlog-install-test/bin/pip install git+file://$(pwd)
/tmp/imlog-install-test/bin/python -c "from immutable_logging import IntegrityHandler, verify_log_integrity, VerifyResult; print('ok')"
```

Expected: prints `ok`. Then clean up:
```bash
rm -rf /tmp/imlog-install-test
```

> **Note:** This validates the wheel built from the current branch installs and exposes the public API. The README snippet uses `git+https://...` which requires the commit to be pushed; `git+file://` is the local equivalent for pre-push verification.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Document pip install and immutable_logging import paths in README"
```

---

## Task 10: GitHub Actions CI workflow

Add `.github/workflows/ci.yml` that runs tests on Python 3.10–3.13 and builds the wheel + sdist as an artifact.

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install package with dev + immudb extras
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[immudb,dev]"

      - name: Run tests
        run: pytest -v

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build wheel + sdist
        run: |
          python -m pip install --upgrade pip build
          python -m build

      - name: Upload distribution artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/*
```

- [ ] **Step 2: Sanity-check the workflow locally**

You can't run GitHub Actions locally without extra tools, but you can validate the YAML parses and approximate the steps:

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "ok"
```
Expected: `ok`

And do a dry equivalent of the build job:
```bash
pip install --upgrade build
python -m build
ls dist/
```
Expected: two files — `immutable_logging-0.1.0-py3-none-any.whl` and `immutable_logging-0.1.0.tar.gz`. Then clean up:
```bash
rm -rf dist/ build/ src/*.egg-info
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Add GitHub Actions CI matrix for Python 3.10-3.13 and wheel build artifact"
```

---

## Task 11: PyPI release workflow (trusted publishing, inert until first tag)

Add `.github/workflows/release.yml` configured for PyPI trusted publishing. The workflow only fires on `v*` tag pushes and does nothing otherwise.

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the release workflow**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/immutable-logging
    permissions:
      id-token: write   # required for PyPI trusted publishing (OIDC)

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build wheel + sdist
        run: |
          python -m pip install --upgrade pip build
          python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Trusted publishing — no API token in repo secrets.
        # Requires the project on PyPI to be configured to trust this repo + workflow.
```

> **Note:** This workflow will fail at the publish step until the PyPI project `immutable-logging` exists AND has this repo configured as a trusted publisher. That's expected and deliberate — the workflow is dormant until the user is ready to publish, at which point they reserve the name on PyPI, register the trusted publisher, and push their first `v0.1.0` tag.

- [ ] **Step 2: Validate the YAML parses**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo "ok"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "Add PyPI release workflow using trusted publishing, triggered by v* tags"
```

---

## Task 12: Remove `requirements.txt` + final cleanup

`pyproject.toml` is now the source of truth for dependencies, so `requirements.txt` is redundant and risks drifting out of sync.

**Files:**
- Delete: `requirements.txt`

- [ ] **Step 1: Delete the file**

```bash
git rm requirements.txt
```

- [ ] **Step 2: Verify no in-tree script or doc still references it**

```bash
grep -rn "requirements\.txt" . --include="*.md" --include="*.py" --include="*.yml" --include="*.yaml" --include="Dockerfile*" 2>/dev/null
```

Expected: no hits, OR only hits that legitimately discuss the historical file (in which case update them to point at `pyproject.toml`). Pay special attention to any `Dockerfile` and the README — fix any references to install via `requirements.txt`.

- [ ] **Step 3: Final full-suite test run**

```bash
pip install -e ".[immudb,dev]"
pytest -v
```

Expected: every test passes (`tests/test_integrity.py`, `tests/test_verify.py`, `tests/test_summary.py`, `tests/test_immudb.py`, `tests/test_public_api.py`, `tests/test_cli.py`).

- [ ] **Step 4: Verify the example still runs and the CLI works**

```bash
python examples/basic_usage.py
verify-logs cvdlink.log
```

Expected: the example produces a log + integrity sidecar; `verify-logs` prints `OK: N entries verified` and exits 0.

Clean up:
```bash
rm -f cvdlink.log cvdlink.log.integrity cvdlink.log.[1-5]
```

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "Remove requirements.txt now that pyproject.toml is the source of truth"
```

---

## Acceptance Criteria (re-checked against spec)

- [x] `pip install -e .` succeeds on Python 3.10–3.13 → covered by Tasks 1, 10
- [x] `pip install -e .[immudb]` works and `from immutable_logging import ImmuDBHandler` succeeds → covered by Tasks 5, 6
- [x] Without `[immudb]`, top-level access raises the friendly error message → covered by Task 6
- [x] `pytest` passes on all supported versions → covered by Task 10 matrix
- [x] `verify-logs cvdlink.log` runs and prints `result.summary` → covered by Tasks 4, 7
- [x] `python examples/basic_usage.py` behaves identically to old `python main.py` → covered by Task 8
- [x] `python -m build` produces wheel + sdist → covered by Tasks 1, 10
- [x] `ci.yml` runs green on a PR → covered by Task 10
- [x] README install snippets work as written → covered by Task 9
