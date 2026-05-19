"""Demonstrate the verify_log_integrity API end-to-end.

Walks through three scenarios against a temporary log, printing the
VerifyResult after each so you can see exactly what the verifier reports.
Useful as a template for monitoring / CI / startup checks in your own code.

For one-shot use from the shell, see the `verify-logs` CLI.
"""

__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import logging
import os
import tempfile

from immutable_logging import (
    IntegrityHandler,
    SingleLineFormatter,
    verify_log_integrity,
)


def _write_log(log_path):
    """Write a realistic-looking log + matching integrity sidecar."""
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
    logger.debug("Loaded configuration from /etc/app/config.yaml")
    logger.info("Listening on 0.0.0.0:8080")
    logger.debug("Accepted connection from 10.0.0.42")
    logger.info("User alice authenticated successfully")
    logger.warning("Memory usage near threshold (87%)")
    logger.error("Database connection timeout after 30s")
    logger.info("Retrying database connection (attempt 2/3)")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Unhandled exception while processing request")
    logger.critical("System failure: shutting down")
    logger.info("Service stopped")

    integrity.close()
    file_handler.close()


def _section(title, description):
    bar = "=" * 72
    print(f"\n{bar}\n {title}\n{bar}")
    print(description.strip())


def _report(result, show_details=False):
    print()
    print(f"  result.summary        = {result.summary!r}")
    print(f"  result.passed         = {result.passed}")
    print(f"  result.tampered       = {result.tampered}")
    print(f"  result.missing        = {result.missing}")
    print(f"  result.tampered_lines = {result.tampered_lines}")
    print(f"  result.missing_lines  = {result.missing_lines}")
    if show_details and result.details:
        print("  result.details:")
        for line in result.details:
            print(f"    - {line}")


def _show_log(log_path, highlight=None):
    """Print the log file with line numbers; highlight any 1-based indices given."""
    highlight = set(highlight or ())
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    print()
    print("  current log file contents:")
    for i, line in enumerate(lines, 1):
        marker = "  >>" if i in highlight else "    "
        snippet = (line[:90] + "...") if len(line) > 90 else line
        print(f"  {marker}{i:>3}: {snippet}")


def main():
    tmpdir = tempfile.mkdtemp(prefix="verify-demo-")
    log_path = os.path.join(tmpdir, "demo.log")

    try:
        # --- Scenario 1 -------------------------------------------------
        _section(
            "Scenario 1 — Clean log",
            """
The log and its .integrity sidecar were just written together, so every
hash in the chain matches. verify_log_integrity() should report passed=True
and zero tampered / missing entries.
            """,
        )
        _write_log(log_path)
        _show_log(log_path)
        _report(verify_log_integrity(log_path))

        # --- Scenario 2 -------------------------------------------------
        _section(
            "Scenario 2 — In-place edits",
            """
Below we overwrite lines 2, 5, 7, and 9 in the .log file (the .integrity
sidecar is untouched, which is the realistic attack model — an intruder
who can edit logs but not the chain). The verifier recomputes each line's
hash and compares against the sidecar; mismatches are flagged as tampered.
The exact line numbers come back in result.tampered_lines.
            """,
        )
        tampered_targets = (2, 5, 7, 9)
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line_no in tampered_targets:
            lines[line_no - 1] = f"tampered content #{line_no}\n"
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        _show_log(log_path, highlight=tampered_targets)
        _report(verify_log_integrity(log_path))

        # --- Scenario 3 -------------------------------------------------
        _section(
            "Scenario 3 — Deletions cause a positional cascade",
            """
Now we also delete three lines (originally 3, 6, and 11). The verifier
compares positionally: log line N is checked against integrity entry N.
Once a line is removed, every subsequent log line shifts up by one, so
the lines that used to be 'clean' now hash against the wrong integrity
entry and get flagged as tampered too. Entries past the new end of the
log are reported as missing. Watch how tampered_lines now spans a
contiguous range and missing_lines points at the tail.
            """,
        )
        deletion_targets = (3, 6, 11)
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line_no in sorted(deletion_targets, reverse=True):
            del lines[line_no - 1]
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        _show_log(log_path)
        _report(verify_log_integrity(log_path), show_details=True)

        print()
        print("Done. In production, branch on result.passed and route the")
        print("tampered/missing line lists to your alerting / on-call channel.")
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
