"""Mode A / B example — file + rotation + tamper-evident chain + (optional) immudb.

This script is the canonical demo for the package. It wires up three handlers
on one logger:

  1. ``ImmuDBHandler``                — best-effort write to an immudb
     container. If immudb is unreachable, the handler logs a warning and
     keeps the application running with file + integrity output only
     (graceful fallback). When immudb later becomes available, logging
     resumes automatically.

  2. ``IntegrityRotatingFileHandler`` — rotating file handler that *also*
     maintains a SHA-256 hash chain in a ``.integrity`` sidecar. Rotation
     moves both files in lockstep so each rotated pair
     (``cvdlink.log.1`` + ``cvdlink.log.1.integrity``) is independently
     verifiable.

  3. ``StreamHandler``                — stderr mirror for live observation.

All three handlers share one ``SingleLineFormatter`` so the .log file and
the hashed text agree exactly (a mismatch in formatters silently breaks
verification, see ``examples/minimal_usage.py`` for the explanation).

Mode A (no immudb container running)::

    python examples/basic_usage.py
    verify-logs cvdlink.log              # OK: N entries verified

Mode B (immudb running on localhost:3322 — see README)::

    docker run -d -p 3322:3322 -p 3080:8080 codenotary/immudb:latest
    python examples/basic_usage.py       # also pushes to immudb

The script is also runnable repeatedly: each invocation verifies the
existing chain at startup, then appends new entries to it.
"""

__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import sys
from datetime import datetime
import logging
from immutable_logging.immudb import ImmuDBHandler
from immutable_logging.integrity import (
    IntegrityRotatingFileHandler,
    SingleLineFormatter,
)
from immutable_logging.verify import verify_log_integrity

LOG_FILE = "cvdlink.log"


# ---- 1. Logger ------------------------------------------------------------
# The logger's level (DEBUG) is the *lowest* severity it will dispatch to
# its handlers. Each handler may add its own level filter, but we leave
# all of them at DEBUG so this demo emits every record we generate.
logger = logging.getLogger('CVDLINK test logger')
logger.setLevel(logging.DEBUG)


# ---- 2. Shared formatter --------------------------------------------------
# SingleLineFormatter escapes newlines (\n, \r) and backslashes in the
# formatted output, so multi-line records like exception tracebacks end up
# on one .log line. The verifier reads the .log file as one record per
# line, so this is mandatory whenever IntegrityHandler / IntegrityRotating-
# FileHandler is in the pipeline.
file_formatter = SingleLineFormatter(
    "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
)


# ---- 3. immudb handler (Mode B) -------------------------------------------
# Writes each log record to an immudb append-only database using SafeSet.
# If immudb is unreachable at construction, the handler prints a warning
# and falls back to "do nothing" — your application keeps logging to file
# and console without interruption. A background thread retries every 30s
# and resumes writing to immudb once it's back. This means you can promote
# Mode A -> Mode B without a code change, just by starting the container.
immu_handler = ImmuDBHandler()
logger.addHandler(immu_handler)


# ---- 4. Rotating file handler with integrated hash chain ------------------
# Single handler that writes BOTH cvdlink.log and cvdlink.log.integrity for
# each record. We use this instead of attaching a separate IntegrityHandler
# because rotation requires both files to move together — see the docstring
# on IntegrityRotatingFileHandler for the off-by-one bug that an external
# IntegrityHandler would otherwise hit at rollover boundaries.
#
#   maxBytes=10_000_000  — roll over when the active .log would exceed 10 MB.
#   backupCount=5        — keep up to five rotated pairs (cvdlink.log.1
#                          through cvdlink.log.5); anything older is deleted.
#                          See examples/rotation_usage.py for a stress demo
#                          that actually triggers rotation many times.
file_handler = IntegrityRotatingFileHandler(
    LOG_FILE,
    maxBytes=10_000_000,
    backupCount=5,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)


# ---- 5. Console handler ---------------------------------------------------
# Pure convenience — mirrors the formatted log lines to stderr so you see
# them while the script runs. Not involved in integrity at all.
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)


def print_log(entry):
    """Pretty-print one log entry as returned by ImmuDBHandler.scan_logs().

    Each entry is a dict like {"key": "...", "value": {...JSON record...}}.
    """
    key = entry["key"]
    value = entry["value"]
    ts = datetime.fromtimestamp(value["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(
        f"[{ts}] {value['level']:<8} "
        f"{value['message']}\n"
        f"    Logger: {value['logger']}\n"
        f"    File:   {value['filename']}:{value['lineno']}\n"
        f"    Func:   {value['func']}\n"
        f"    Key:    {key}\n"
    )


def main():
    # ---- 6. Startup integrity check ---------------------------------------
    # Verify whatever is already on disk before this run appends anything.
    # In production you'd alert on a non-passing result (other than
    # no_integrity_file, which is just the first-ever run).
    result = verify_log_integrity(LOG_FILE)
    if result.no_integrity_file:
        logger.info("No previous integrity file found. Starting fresh.")
    elif result.passed:
        logger.info("Log integrity check passed.")
    else:
        logger.warning(
            f"Log integrity check FAILED: {result.tampered} tampered, "
            f"{result.missing} missing entries."
        )

    # ---- 7. Emit records at every standard level --------------------------
    # Each call below fans out to all three handlers: hash chain entry +
    # .log line + console line + (best-effort) immudb write.
    logger.debug("Debug details for developers")
    logger.info("Service started")
    logger.warning("Memory usage near threshold")
    logger.error("Database connection timeout")
    logger.critical("System failure")

    # ---- 8. Exception with traceback --------------------------------------
    # The traceback is captured into the LogRecord and rendered by the
    # formatter. SingleLineFormatter escapes the embedded newlines so the
    # whole traceback lands on a single .log line (hash chain stays intact).
    try:
        1 / 0
    except Exception:
        logger.exception("Unhandled exception occurred")

    # ---- 9. Read back from immudb (only when actually connected) ---------
    # Mode B convenience: print the most recent entries straight from
    # immudb to prove the round-trip works. In Mode A (no container) we
    # just note that the file + sidecar still got written.
    if immu_handler.connected:
        print("\n--- Latest immudb logs ---")
        for log in immu_handler.scan_logs(limit=6):
            print_log(log)
    else:
        print("\n--- immudb not available, logs written to file and console ---")

if __name__ == "__main__":
    main()
