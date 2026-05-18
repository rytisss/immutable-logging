"""Minimal Mode A example: IntegrityHandler + plain FileHandler, no rotation.

This is the simplest possible setup — useful when you don't need log rotation
and want to see the moving parts at a glance. Compare with basic_usage.py,
which adds rotation (and the IntegrityAwareRotatingHandler wrapper required
to reset the hash chain on rollover) plus an immudb handler.
"""

import logging
import sys

from immutable_logging import (
    IntegrityHandler,
    SingleLineFormatter,
    verify_log_integrity,
)

LOG_FILE = "minimal.log"


def main():
    logger = logging.getLogger("minimal")
    logger.setLevel(logging.DEBUG)

    # SingleLineFormatter escapes newlines so multi-line records (exceptions)
    # stay on one log line — required for hash-chain verification.
    formatter = SingleLineFormatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )

    integrity_handler = IntegrityHandler(LOG_FILE + ".integrity")
    integrity_handler.setFormatter(formatter)
    logger.addHandler(integrity_handler)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Verify any pre-existing log before adding new entries.
    result = verify_log_integrity(LOG_FILE)
    if result.no_integrity_file:
        logger.info("No previous integrity file found. Starting fresh.")
    elif result.passed:
        logger.info(f"Log integrity check passed ({result.summary}).")
    else:
        logger.warning(f"Log integrity check FAILED: {result.summary}")

    logger.debug("Debug details for developers")
    logger.info("Service started")
    logger.warning("Memory usage near threshold")
    logger.error("Database connection timeout")
    logger.critical("System failure")

    try:
        1 / 0
    except Exception:
        logger.exception("Unhandled exception occurred")


if __name__ == "__main__":
    main()
