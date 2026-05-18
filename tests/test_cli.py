import subprocess
import sys
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
    combined = proc.stdout + proc.stderr
    assert str(log_path) in combined


def test_cli_lists_tampered_line_numbers_on_failure(tmp_path):
    log_path = _write_intact_log(tmp_path)
    # Tamper with line 2.
    with open(log_path, "r") as f:
        lines = f.readlines()
    lines[1] = "HACKED\n"
    with open(log_path, "w") as f:
        f.writelines(lines)

    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "FAILED" in proc.stdout
    assert "Tampered lines" in proc.stdout
    assert "2" in proc.stdout


def test_cli_lists_missing_line_numbers_on_failure(tmp_path):
    log_path = _write_intact_log(tmp_path)
    # Delete line 3 from the log file so integrity has more entries than log.
    with open(log_path, "r") as f:
        lines = f.readlines()
    with open(log_path, "w") as f:
        f.writelines(lines[:-1])

    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "Missing lines" in proc.stdout
    assert "3" in proc.stdout


def test_cli_caps_long_lists_with_ellipsis(tmp_path):
    """A massively tampered log shouldn't flood the terminal — list is truncated."""
    log_path = tmp_path / "many.log"
    integrity_path = Path(str(log_path) + ".integrity")

    handler = IntegrityHandler(str(integrity_path))
    handler.setFormatter(logging.Formatter("%(message)s"))
    with open(log_path, "w") as f:
        for i in range(30):
            msg = f"line {i}"
            f.write(msg + "\n")
            handler.emit(logging.LogRecord("many", logging.INFO, __file__, 0, msg, None, None))
    handler.close()

    # Tamper with every line.
    with open(log_path, "w") as f:
        for i in range(30):
            f.write(f"HACKED {i}\n")

    proc = subprocess.run(
        [sys.executable, "-m", "immutable_logging.cli", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "..." in proc.stdout


def test_installed_console_script_is_on_path(tmp_path):
    """The `verify-logs` entry point declared in pyproject.toml is installed."""
    log_path = _write_intact_log(tmp_path)
    proc = subprocess.run(
        ["verify-logs", str(log_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK:" in proc.stdout
