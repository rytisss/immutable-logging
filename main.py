from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from immudb_handler import ImmuDBHandler

# Configure logger
logger = logging.getLogger('CVDLINK test logger')
logger.setLevel(logging.DEBUG)  # capture ALL levels

# -------------------------
# immudb handler (immutable logs)
# -------------------------
immu_handler = ImmuDBHandler()
logger.addHandler(immu_handler)

# -------------------------
# file handler (local logs)
# -------------------------
file_handler = RotatingFileHandler(
    "cvdlink.log",
    maxBytes=10_000_000,  # 10 MB per file
    backupCount=5         # keep last 5 logs
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)


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

# -------------------------
# application
# -------------------------
def main():
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

    # Fetch logs from immudb
    handler = logger.handlers[0]  # immudb handler
    print("\n--- Latest immudb logs ---")
    for log in handler.scan_logs(limit=6):
        print_log(log)

if __name__ == "__main__":
    main()