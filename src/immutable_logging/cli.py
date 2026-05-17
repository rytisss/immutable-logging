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
