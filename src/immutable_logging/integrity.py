import hashlib
import logging
import os

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
