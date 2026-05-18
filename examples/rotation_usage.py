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

# --- Demo parameters --------------------------------------------------------
# These are inherited from logging.handlers.RotatingFileHandler (which
# IntegrityRotatingFileHandler subclasses). The defaults below are tuned to
# trigger rotation many times in a small demo; production values are usually
# much larger.
#
#   ENTRIES       — how many log records this script writes.
#
#   MAX_BYTES     — maxBytes: rotate when the active log file would exceed
#                   this size in bytes after appending the next record. Set
#                   to 0 to disable size-based rotation. Bigger value = fewer
#                   rotations and longer chains per file; smaller value =
#                   more, smaller files.
#
#   BACKUP_COUNT  — backupCount: how many rotated files to keep around. On
#                   each rollover, app.log -> app.log.1, .1 -> .2, ..., and
#                   anything beyond app.log.{backupCount} is deleted. The
#                   same cascade applies to the .integrity sidecars. Set
#                   backupCount=0 to disable rotation entirely. Pick a
#                   value that bounds disk usage (peak = backupCount + 1
#                   files of up to maxBytes each, doubled when counting
#                   sidecars).
ENTRIES = 10_000
MAX_BYTES = 64 * 1024  # 64 KB — small so we rotate ~14 times in this demo
BACKUP_COUNT = 50      # keep all rotations for the demo; tune down in prod


def _section(title):
    print(f"\n{'=' * 72}\n {title}\n{'=' * 72}")


def main():
    tmpdir = tempfile.mkdtemp(prefix="rotation-demo-")
    log_path = os.path.join(tmpdir, "stress.log")

    try:
        _section("Parameters")
        print(f"  ENTRIES       = {ENTRIES:,}   (log records written)")
        print(f"  MAX_BYTES     = {MAX_BYTES:,} bytes "
              f"  (rotate when the active log would exceed this size)")
        print(f"  BACKUP_COUNT  = {BACKUP_COUNT}     "
              f"  (keep up to this many rotated .log + .integrity backups)")

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

        _section("Tampering with multiple log files")
        # Pick the active log and two rotated backups to tamper. Each file
        # has its own .integrity sidecar, so each must detect its own tamper
        # independently.
        rotated_backups = [n for n in log_files if n != "stress.log"]
        targets = [
            ("stress.log",            "active log, mid-file"),
            (rotated_backups[2],      "recent rotated backup"),
            (rotated_backups[-1],     "oldest rotated backup"),
        ]
        tampered_at = {}
        for name, description in targets:
            path = os.path.join(tmpdir, name)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            line_idx = len(lines) // 2
            tampered_at[name] = line_idx + 1
            lines[line_idx] = "MITM injected this line\n"
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"  edited {name:<24} line {line_idx + 1}  ({description})")

        _section("Re-verifying — each tampered file reports its own line, others stay clean")
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
        print("Takeaway: rotation moves the log and its .integrity sidecar")
        print("in lockstep, so each rotated pair is verifiable on its own.")
        print("Tampering in one file is pinpointed to its line number without")
        print("affecting verification of the other rotated backups.")
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
