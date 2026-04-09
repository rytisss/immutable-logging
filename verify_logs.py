import argparse
import hashlib
import os
import sys
from dataclasses import dataclass, field

GENESIS_HASH = "0" * 64


@dataclass
class VerificationResult:
    passed: bool = True
    tampered: int = 0
    missing: int = 0
    tampered_lines: list = field(default_factory=list)
    missing_lines: list = field(default_factory=list)
    no_integrity_file: bool = False
    details: list = field(default_factory=list)


def verify_log_integrity(log_path):
    """
    Verify a log file against its .integrity sidecar.
    Returns a VerificationResult with details.
    """
    integrity_path = log_path + ".integrity"
    result = VerificationResult()

    if not os.path.exists(integrity_path):
        result.passed = False
        result.no_integrity_file = True
        result.details.append(
            f"No integrity file found for {log_path}. Cannot verify."
        )
        return result

    # Read log lines
    with open(log_path, "r", encoding="utf-8") as f:
        log_lines = f.read().splitlines()

    # Read integrity lines
    with open(integrity_path, "r", encoding="utf-8") as f:
        integrity_lines = f.read().splitlines()

    # Filter empty lines
    integrity_lines = [l for l in integrity_lines if l.strip()]

    # Check for missing entries (fewer log lines than integrity entries)
    if len(log_lines) < len(integrity_lines):
        result.passed = False
        for i in range(len(log_lines) + 1, len(integrity_lines) + 1):
            result.missing += 1
            result.missing_lines.append(i)
            result.details.append(f"Line {i}: MISSING")

    # Check for inserted entries (more log lines than integrity entries)
    if len(log_lines) > len(integrity_lines):
        result.passed = False
        for i in range(len(integrity_lines) + 1, len(log_lines) + 1):
            result.tampered += 1
            result.tampered_lines.append(i)
            result.details.append(f"Line {i}: TAMPERED")

    # Verify each integrity entry
    prev_hash = GENESIS_HASH
    check_count = min(len(log_lines), len(integrity_lines))

    for i in range(check_count):
        parts = integrity_lines[i].split("|")
        stored_hash = parts[1].split("=", 1)[1]
        stored_prev = parts[2].split("=", 1)[1]

        expected_hash = hashlib.sha256(
            (log_lines[i] + prev_hash).encode()
        ).hexdigest()

        if stored_prev != prev_hash:
            result.passed = False
            result.tampered += 1
            result.tampered_lines.append(i + 1)
            result.details.append(f"Line {i + 1}: TAMPERED")
        elif stored_hash != expected_hash:
            result.passed = False
            result.tampered += 1
            result.tampered_lines.append(i + 1)
            result.details.append(f"Line {i + 1}: TAMPERED")
        else:
            result.details.append(f"Line {i + 1}: OK")

        prev_hash = stored_hash

    return result


def main():
    parser = argparse.ArgumentParser(description="Verify log file integrity")
    parser.add_argument("log_file", help="Path to the log file to verify")
    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Log file not found: {args.log_file}")
        sys.exit(1)

    print(f"Verifying {args.log_file}...")
    result = verify_log_integrity(args.log_file)

    for detail in result.details:
        print(detail)

    print()
    if result.no_integrity_file:
        print(f"No integrity file found for {args.log_file}. Cannot verify.")
    elif result.passed:
        print("Result: PASSED — all entries verified")
    else:
        print(
            f"Result: FAILED — {result.tampered} tampered, "
            f"{result.missing} missing entries"
        )

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
