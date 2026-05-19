__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import hashlib
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

GENESIS_HASH = "0" * 64


class SingleLineFormatter(logging.Formatter):
    """Formatter that escapes newlines so each log record occupies a single file line.

    Pair this with IntegrityHandler: the verifier reads the log file line-by-line
    and expects one line per integrity entry. Without escaping, an exception's
    traceback would split one record across many lines and break verification.

    Apply the same instance (or two with identical patterns) to both the file
    handler and the IntegrityHandler so they produce identical text for the
    same record.
    """

    def format(self, record):
        text = super().format(record)
        return (
            text.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )


class IntegrityHandler(logging.Handler):
    """
    Logging handler that writes a SHA-256 hash chain sidecar file.
    Each entry links to the previous via its hash, forming a tamper-evident chain.

    On construction, the chain state is seeded from the last entry of an existing
    integrity file (if any) so the chain survives process restarts. Use
    reset_chain() to start a fresh chain (e.g. after log rotation).

    Thread safety: emit() is called by Handler.handle() which acquires self.lock
    before calling emit(), so concurrent access to _prev_hash and _line_num is safe
    under normal logging usage.
    """

    def __init__(self, integrity_path):
        super().__init__()
        self.integrity_path = integrity_path
        self._prev_hash, self._line_num = self._load_chain_state()

    def _load_chain_state(self):
        """Return (prev_hash, line_num) seeded from the last entry of the existing
        integrity file, or (GENESIS, 0) if the file is absent, empty, or malformed."""
        if not os.path.exists(self.integrity_path):
            return GENESIS_HASH, 0
        last_line = ""
        with open(self.integrity_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if not last_line:
            return GENESIS_HASH, 0
        try:
            parts = last_line.split("|")
            line_num = int(parts[0])
            prev_hash = parts[1].split("=", 1)[1]
            if len(prev_hash) != 64:
                raise ValueError("hash length")
            return prev_hash, line_num
        except (IndexError, ValueError):
            return GENESIS_HASH, 0

    def emit(self, record):
        """Format the record, compute its chained hash, and write to the integrity file."""
        try:
            formatted = self.format(record)
            current_hash = hashlib.sha256(
                (formatted + self._prev_hash).encode()
            ).hexdigest()
            self._line_num += 1
            line = f"{self._line_num}|sha256={current_hash}|prev={self._prev_hash}\n"
            with open(self.integrity_path, "a", encoding="utf-8") as f:
                f.write(line)
            self._prev_hash = current_hash
        except Exception:
            self.handleError(record)

    def reset_chain(self):
        """Reset the hash chain to genesis. Called on log rotation."""
        self._prev_hash = GENESIS_HASH
        self._line_num = 0

    def close(self):
        super().close()


class IntegrityRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that also writes a SHA-256 hash-chain sidecar
    next to the log file. The sidecar lives at ``{log_path}.integrity`` and
    rotates in lockstep with the log, so each rotated pair (e.g. ``app.log.1``
    and ``app.log.1.integrity``) verifies independently via
    ``verify_log_integrity()`` or ``verify-logs``.

    Use this instead of attaching a separate IntegrityHandler to the logger
    when rotation is involved: one handler writes both files for the same
    record, which keeps the chain aligned across rollover boundaries.

    Constructor arguments are inherited from
    :class:`logging.handlers.RotatingFileHandler`. The two that matter most:

    - ``maxBytes`` — rotate when the active log would exceed this size in
      bytes. Set to 0 to disable size-based rotation.
    - ``backupCount`` — how many rotated files to retain. On each rollover
      ``app.log -> app.log.1``, ``.1 -> .2``, ..., and anything beyond
      ``app.log.{backupCount}`` is deleted. The same cascade is applied to
      the ``.integrity`` sidecars. Peak disk usage is roughly
      ``(backupCount + 1) * maxBytes`` doubled for the sidecars.

    Extra argument:

    - ``keep_all_backups`` — when True, ignore ``backupCount`` and rename
      each rolled-over file to a unique timestamped name
      (``app.log.YYYYMMDDTHHMMSS-uuuuuu``) so no rotated log or sidecar is
      ever deleted. Use this for audit/compliance workloads where the full
      history must remain on disk (and you handle off-box archival
      separately). Disk usage grows unbounded.
    """

    def __init__(self, *args, keep_all_backups=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.keep_all_backups = keep_all_backups
        self._integrity_handler = IntegrityHandler(self.baseFilename + ".integrity")

    def setFormatter(self, formatter):
        super().setFormatter(formatter)
        self._integrity_handler.setFormatter(formatter)

    def emit(self, record):
        try:
            if self.shouldRollover(record):
                self.doRollover()
            logging.FileHandler.emit(self, record)
            self._integrity_handler.emit(record)
        except Exception:
            self.handleError(record)

    def doRollover(self):
        if self.keep_all_backups:
            self._do_timestamped_rollover()
        else:
            super().doRollover()
            if self.backupCount > 0:
                self._rotate_integrity_sidecar()
        self._integrity_handler.reset_chain()

    def _do_timestamped_rollover(self):
        """Rename the current .log and .integrity to unique timestamped names
        so nothing is overwritten or deleted, then reopen a fresh active log.
        The sidecar name mirrors {log_dest}.integrity so verify-logs can find it."""
        if self.stream:
            self.stream.close()
            self.stream = None
        suffix = self._unique_timestamp_suffix()
        log_dest = f"{self.baseFilename}.{suffix}"
        integrity_dest = f"{log_dest}.integrity"
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, log_dest)
        current_integrity = self._integrity_handler.integrity_path
        if os.path.exists(current_integrity):
            os.rename(current_integrity, integrity_dest)
        if not self.delay:
            self.stream = self._open()

    def _unique_timestamp_suffix(self):
        """ISO-like timestamp with microsecond precision; appends -N on collision
        (clock jitter, sub-microsecond rollover, or wall-clock going backward)."""
        base = datetime.now().strftime("%Y%m%dT%H%M%S-%f")
        candidate = base
        counter = 0
        while (os.path.exists(f"{self.baseFilename}.{candidate}")
               or os.path.exists(f"{self.baseFilename}.{candidate}.integrity")):
            counter += 1
            candidate = f"{base}-{counter}"
        return candidate

    def _rotate_integrity_sidecar(self):
        """Cascade {base}.N.integrity → {base}.N+1.integrity and
        {base}.integrity → {base}.1.integrity, mirroring the parent's .log cascade."""
        base = self.baseFilename
        for i in range(self.backupCount - 1, 0, -1):
            sfn = f"{base}.{i}.integrity"
            dfn = f"{base}.{i + 1}.integrity"
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        dfn = f"{base}.1.integrity"
        if os.path.exists(dfn):
            os.remove(dfn)
        current = self._integrity_handler.integrity_path
        if os.path.exists(current):
            os.rename(current, dfn)

    def close(self):
        self._integrity_handler.close()
        super().close()
