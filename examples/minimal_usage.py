"""Minimal Mode A example — file logging + tamper-evident hash chain.

This is the smallest useful setup. It wires together three handlers and one
formatter to get:

  * a human-readable log file (``minimal.log``)
  * a SHA-256 hash-chain sidecar (``minimal.log.integrity``)
  * console output for live observation

No rotation, no immudb, no extra dependencies — just stdlib ``logging`` plus
this package. Compare with:

  * ``basic_usage.py`` — adds rotation (IntegrityRotatingFileHandler) and an
    optional immudb backend.
  * ``rotation_usage.py`` — stress-tests rotation at 10K entries.
  * ``verify_usage.py`` — walks through what the verifier reports under
    clean / tampered / deleted conditions.

After running, verify the chain from the shell::

    verify-logs minimal.log
    # -> OK: 7 entries verified (the count grows on each re-run)

Re-running this script appends to the same files; the IntegrityHandler reads
the last entry from the sidecar on startup so the chain is continuous across
process restarts.
"""

__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import logging
import sys

from immutable_logging import (
    IntegrityHandler,
    SingleLineFormatter,
    verify_log_integrity,
)

LOG_FILE = "minimal.log"


def main():
    # ---- 1. Logger setup -------------------------------------------------
    # A logger is just a name and a level. The level (DEBUG here) is the
    # *lowest* severity that this logger will dispatch to its handlers;
    # each handler can additionally filter to a higher level if desired.
    logger = logging.getLogger("minimal")
    logger.setLevel(logging.DEBUG)

    # ---- 2. Formatter ----------------------------------------------------
    # SingleLineFormatter is a thin wrapper around logging.Formatter that
    # escapes "\n", "\r" and "\\" in the *formatted* output. We need this
    # because the integrity verifier reads the .log file one line per
    # entry; without escaping, an exception traceback (which would
    # otherwise span several lines) would split a single hash-chain entry
    # across multiple file lines and break verification.
    formatter = SingleLineFormatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )

    # ---- 3. Integrity handler -------------------------------------------
    # Writes one line to minimal.log.integrity per log record. Each line
    # has the form: "<seq>|sha256=<hex>|prev=<hex>", where the hash covers
    # the formatted record text *plus* the previous hash. That linkage is
    # what makes any single-line tamper / insertion / deletion detectable.
    #
    # On construction this handler reads the last line of the existing
    # sidecar (if any) and continues the chain from there, so two
    # consecutive process runs produce one continuous chain.
    integrity_handler = IntegrityHandler(LOG_FILE + ".integrity")
    integrity_handler.setFormatter(formatter)
    logger.addHandler(integrity_handler)

    # ---- 4. File handler -------------------------------------------------
    # Writes the human-readable log lines. Uses the *same* formatter as the
    # integrity handler so each .log file line matches exactly what was
    # hashed into the .integrity sidecar. If you pass a different formatter
    # here, every entry will fail verification.
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ---- 5. Console handler ---------------------------------------------
    # Pure convenience — mirrors the same formatted lines to stderr so you
    # see them in your terminal while running the script. Not involved in
    # integrity at all.
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ---- 6. Startup integrity check -------------------------------------
    # Best practice: verify any pre-existing log on startup. The check is
    # cheap (one streaming pass of two files) and surfaces tampering
    # before this run appends more entries. In a real service, route a
    # failure here to your alerting channel.
    result = verify_log_integrity(LOG_FILE)
    if result.no_integrity_file:
        # First-ever run: there's nothing to verify yet.
        logger.info("No previous integrity file found. Starting fresh.")
    elif result.passed:
        logger.info(f"Log integrity check passed ({result.summary}).")
    else:
        # result.tampered_lines / result.missing_lines tell you exactly
        # which entries are affected — see examples/verify_usage.py.
        logger.warning(f"Log integrity check FAILED: {result.summary}")

    # ---- 7. Emit log records at every level -----------------------------
    # Each call below goes through all three handlers and adds one entry
    # to the hash chain.
    logger.debug("Debug details for developers")
    logger.info("Service started")
    logger.warning("Memory usage near threshold")
    logger.error("Database connection timeout")
    logger.critical("System failure")

    # ---- 8. Exception logging -------------------------------------------
    # logger.exception() captures the active exception and includes the
    # full traceback in the record. Without SingleLineFormatter the
    # traceback would span ~6 lines in the .log file, but only one entry
    # in the .integrity sidecar — and verification would fail on the
    # *next* run. With it, the traceback is escaped to a single line.
    try:
        1 / 0
    except Exception:
        logger.exception("Unhandled exception occurred")


if __name__ == "__main__":
    main()
