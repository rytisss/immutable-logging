"""Rotation + integrity stress demo.

Writes 10,000 log entries through IntegrityRotatingFileHandler with a small
maxBytes so the log rolls over many times. Each rotated pair (.log.N and
.log.N.integrity) is verified independently to prove the chain holds across
rollover boundaries. Then a line in the active log is tampered and the
verifier pinpoints it by line number.

Run from the repo root:

    python examples/rotation_usage.py
"""

import os
import logging
import tempfile

from immutable_logging import (
    IntegrityRotatingFileHandler,
    SingleLineFormatter,
    verify_log_integrity,
)

ENTRIES = 10_000
MAX_BYTES = 64 * 1024  # 64 KB -> ~5-10 rollovers at this entry size
BACKUP_COUNT = 50      # keep enough backups to hold every rotation


def _section(title):
    print(f"\n{'=' * 72}\n {title}\n{'=' * 72}")


def main():
    tmpdir = tempfile.mkdtemp(prefix="rotation-demo-")
    log_path = os.path.join(tmpdir, "stress.log")

    try:
        _section(f"Writing {ENTRIES:,} entries with maxBytes={MAX_BYTES}")

        logger = logging.getLogger("rotation-demo")
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)

        formatter = SingleLineFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler = IntegrityRotatingFileHandler(
            log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        for i in range(ENTRIES):
            level = logging.INFO if i % 100 else logging.WARNING
            logger.log(level, f"event #{i:05d} user=alice action=request status=200")
        handler.close()

        def rotation_order(name):
            # Sort by rotation index, with the active log (no .N suffix) first.
            suffix = name[len("stress.log"):].lstrip(".")
            return (0,) if not suffix else (1, int(suffix))

        log_files = sorted(
            (f for f in os.listdir(tmpdir)
             if f.startswith("stress.log") and not f.endswith(".integrity")),
            key=rotation_order,
        )
        sidecars = sorted(
            (f for f in os.listdir(tmpdir) if f.endswith(".integrity")),
            key=lambda f: rotation_order(f[:-len(".integrity")].rstrip(".")),
        )
        print(f"  log files:      {len(log_files)} ({', '.join(log_files)})")
        print(f"  integrity files:{len(sidecars)} ({', '.join(sidecars)})")
        rollovers = len(log_files) - 1
        print(f"  rollovers:      {rollovers}")

        _section("Verifying every rotated pair (clean state)")
        all_passed = True
        for name in log_files:
            path = os.path.join(tmpdir, name)
            result = verify_log_integrity(path)
            entries = len(result.details)
            status = "OK   " if result.passed else "FAIL "
            print(f"  {status} {name:<24} {result.summary}")
            all_passed = all_passed and result.passed
        print(f"  -> overall: {'all pairs verified' if all_passed else 'verification BROKEN'}")

        _section("Tampering with the active log (mid-file edit)")
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        target = len(lines) // 2
        original = lines[target].rstrip()
        lines[target] = "MITM injected this line\n"
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"  replaced line {target + 1} of {os.path.basename(log_path)}")
        print(f"    before: {original[:90]}...")
        print(f"    after : MITM injected this line")

        _section("Re-verifying — tamper is pinpointed, rotated logs unaffected")
        for name in log_files:
            path = os.path.join(tmpdir, name)
            result = verify_log_integrity(path)
            status = "OK   " if result.passed else "FAIL "
            extra = ""
            if not result.passed and result.tampered_lines:
                shown = result.tampered_lines[:5]
                more = "" if len(result.tampered_lines) <= 5 else f", ... ({len(result.tampered_lines) - 5} more)"
                extra = f"  tampered={shown}{more}"
            print(f"  {status} {name:<24} {result.summary}{extra}")

        print()
        print("Takeaway: rotation moves both the log and its sidecar in lockstep,")
        print("so a tamper in the active log doesn't poison verification of")
        print("rotated backups — and the verifier reports the exact line.")
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
