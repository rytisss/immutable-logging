"""Rotation + integrity stress demo.

What this script does, step by step:

  1. Opens an IntegrityRotatingFileHandler against a temp directory with a
     deliberately small maxBytes (64 KB) so rotation triggers many times.
  2. Writes 10,000 log records. Behind the scenes the handler appends to
     ``stress.log`` and ``stress.log.integrity`` for every record, and on
     each rollover renames both files in lockstep
     (``stress.log -> stress.log.1`` and
     ``stress.log.integrity -> stress.log.1.integrity``), then starts a
     fresh hash chain for the new active log.
  3. Walks every resulting (.log, .integrity) pair through
     ``verify_log_integrity()`` and confirms each one passes independently.
     This is the key property: rotated backups don't depend on the active
     log to verify; each is a self-contained chain rooted at GENESIS.
  4. Tampers three files at once (active log + two backups) by overwriting
     one line in each. Sidecars are left untouched — the realistic attack
     model where the attacker can edit log content but not the chain.
  5. Re-runs verification on every file. The three tampered files report
     FAIL with the exact line number; every other file stays OK.

Run from the repo root:

    python examples/rotation_usage.py
"""

__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

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
    # Use a temp directory so the demo is self-cleaning and doesn't litter
    # the repo root with rotated files.
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

        # Build a fresh logger so re-running the demo doesn't accumulate
        # handlers on the module-level logging tree.
        logger = logging.getLogger("rotation-demo")
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)

        # SingleLineFormatter escapes newlines so multi-line records stay
        # on one .log line — required for hash verification (see comment
        # in minimal_usage.py for details).
        formatter = SingleLineFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        # ONE handler does both writes: each .info() below appends a line
        # to stress.log AND a hash entry to stress.log.integrity. When the
        # active .log would exceed MAX_BYTES, the handler renames both
        # files in lockstep (.log -> .log.1, .integrity -> .1.integrity)
        # and resets the chain to GENESIS for the new active log.
        handler = IntegrityRotatingFileHandler(
            log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Generate 10K records. Every 100th is WARNING so the file has
        # some level variety; the level doesn't affect rotation/integrity.
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
        # Each file in log_files has its own .integrity sidecar created at
        # the moment that file was the active log. verify_log_integrity(p)
        # finds {p}.integrity automatically and re-hashes p line by line
        # against it. Because rotation moved both files together, each
        # pair is self-contained and verifies independently.
        all_passed = True
        for name in log_files:
            path = os.path.join(tmpdir, name)
            result = verify_log_integrity(path)
            status = "OK   " if result.passed else "FAIL "
            print(f"  {status} {name:<24} {result.summary}")
            all_passed = all_passed and result.passed
        print(f"  -> overall: {'all pairs verified' if all_passed else 'verification BROKEN'}")

        _section("Tampering with multiple log files")
        # Pick three files: the active log, a recent rotated backup, and
        # the oldest rotated backup. Editing each in place (without
        # touching the .integrity sidecar) is the realistic attack — an
        # intruder who can rewrite log content but can't recompute the
        # whole chain. We expect verification to flag exactly these three
        # files and leave the others untouched.
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
            # Edit a line near the middle so the tamper isn't at the very
            # start or end of the file (verifier handles both, this is just
            # to make the demo realistic).
            line_idx = len(lines) // 2
            tampered_at[name] = line_idx + 1
            lines[line_idx] = "MITM injected this line\n"
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"  edited {name:<24} line {line_idx + 1}  ({description})")

        _section("Re-verifying — each tampered file reports its own line, others stay clean")
        # Re-run verification on the full set. Note how:
        #   - Tampered files report FAIL with the exact line number we edited.
        #   - Untouched files still report OK.
        #   - There's no cross-contamination: a tamper in stress.log.3 does
        #     not affect stress.log.4 because each pair has its own chain.
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
