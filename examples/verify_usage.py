"""Demonstrate the verify_log_integrity API end-to-end.

Runs three checks against a temporary log:
  1. Clean      — newly written, hashes match.
  2. Tampered   — one line edited in place.
  3. Missing    — one line deleted.

Each check pretty-prints the VerifyResult so you can see what fields are
available for use in your own monitoring / CI / startup checks.

For one-shot use from the shell, the `verify-logs` CLI prints the same
information in one line per call.
"""

import logging
import os
import tempfile

from immutable_logging import (
    IntegrityHandler,
    SingleLineFormatter,
    verify_log_integrity,
)


def _write_log(log_path):
    """Write a small log + matching integrity sidecar."""
    logger = logging.getLogger("verify-demo")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    formatter = SingleLineFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    integrity = IntegrityHandler(log_path + ".integrity")
    integrity.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(integrity)
    logger.addHandler(file_handler)

    logger.info("Service started")
    logger.warning("Memory usage near threshold")
    logger.error("Database connection timeout")
    logger.info("Service stopped")

    integrity.close()
    file_handler.close()


def _report(label, result):
    print(f"\n=== {label} ===")
    print(f"summary:        {result.summary}")
    print(f"passed:         {result.passed}")
    print(f"tampered count: {result.tampered}")
    print(f"missing count:  {result.missing}")
    if result.tampered_lines:
        print(f"tampered lines: {result.tampered_lines}")
    if result.missing_lines:
        print(f"missing lines:  {result.missing_lines}")


def main():
    tmpdir = tempfile.mkdtemp(prefix="verify-demo-")
    log_path = os.path.join(tmpdir, "demo.log")

    try:
        _write_log(log_path)
        _report("1. Clean log", verify_log_integrity(log_path))

        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[1] = "tampered content\n"
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        _report("2. Tampered line 2", verify_log_integrity(log_path))

        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        del lines[-1]
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        _report("3. Tampered + deleted last line", verify_log_integrity(log_path))
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
