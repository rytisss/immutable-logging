import sys
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from immutable_logging.immudb import ImmuDBHandler
from immutable_logging.integrity import IntegrityHandler
from immutable_logging.verify import verify_log_integrity

LOG_FILE = "cvdlink.log"


class IntegrityAwareRotatingHandler(RotatingFileHandler):
    """RotatingFileHandler that resets the integrity hash chain on rotation."""

    def __init__(self, *args, integrity_handler=None, **kwargs):
        self._integrity_handler = integrity_handler
        super().__init__(*args, **kwargs)

    def doRollover(self):
        super().doRollover()
        if self._integrity_handler:
            self._integrity_handler.reset_chain()


# Configure logger
logger = logging.getLogger('CVDLINK test logger')
logger.setLevel(logging.DEBUG)

# Shared formatter for file handler and integrity handler
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
)

# -------------------------
# immudb handler (immutable logs, best-effort)
# -------------------------
immu_handler = ImmuDBHandler()
logger.addHandler(immu_handler)

# -------------------------
# integrity handler (SHA-256 hash chain sidecar)
# -------------------------
integrity_handler = IntegrityHandler(LOG_FILE + ".integrity")
integrity_handler.setLevel(logging.DEBUG)
integrity_handler.setFormatter(file_formatter)
logger.addHandler(integrity_handler)

# -------------------------
# file handler (local logs, resets integrity chain on rotation)
# -------------------------
file_handler = IntegrityAwareRotatingHandler(
    LOG_FILE,
    maxBytes=10_000_000,
    backupCount=5,
    integrity_handler=integrity_handler,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# -------------------------
# console handler (stderr fallback)
# -------------------------
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)


def print_log(entry):
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
    # Optional: verify existing log integrity on startup
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

    # Write logs at all levels
    logger.debug("Debug details for developers")
    logger.info("Service started")
    logger.warning("Memory usage near threshold")
    logger.error("Database connection timeout")
    logger.critical("System failure")

    # Exception logging
    try:
        1 / 0
    except Exception:
        logger.exception("Unhandled exception occurred")

    # Fetch logs from immudb (only if connected)
    if immu_handler.connected:
        print("\n--- Latest immudb logs ---")
        for log in immu_handler.scan_logs(limit=6):
            print_log(log)
    else:
        print("\n--- immudb not available, logs written to file and console ---")

if __name__ == "__main__":
    main()
