import hashlib
import logging

GENESIS_HASH = "0" * 64


class IntegrityHandler(logging.Handler):
    """
    Logging handler that writes a SHA-256 hash chain sidecar file.
    Each entry links to the previous via its hash, forming a tamper-evident chain.

    Thread safety: emit() is called by Handler.handle() which acquires self.lock
    before calling emit(), so concurrent access to _prev_hash and _line_num is safe
    under normal logging usage.
    """

    def __init__(self, integrity_path):
        super().__init__()
        self.integrity_path = integrity_path
        self._prev_hash = GENESIS_HASH
        self._line_num = 0

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
