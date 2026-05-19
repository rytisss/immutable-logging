"""Console-script entry point for `verify-logs`."""

__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import argparse
import os
import sys

from immutable_logging.verify import verify_log_integrity

# Cap per-category line lists so a fully-mangled log doesn't flood the terminal.
MAX_LINES_SHOWN = 20


def _format_lines(lines):
    """Render a list of 1-based line numbers, truncating with '...' past the cap."""
    if len(lines) <= MAX_LINES_SHOWN:
        return ", ".join(str(n) for n in lines)
    head = ", ".join(str(n) for n in lines[:MAX_LINES_SHOWN])
    return f"{head}, ... ({len(lines) - MAX_LINES_SHOWN} more)"


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
    if not result.passed:
        if result.tampered_lines:
            print(f"  Tampered lines: {_format_lines(result.tampered_lines)}")
        if result.missing_lines:
            print(f"  Missing lines:  {_format_lines(result.missing_lines)}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
