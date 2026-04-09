import json
import time
import logging
import queue
import threading
from immudb.client import ImmudbClient


class ImmuDBHandler(logging.Handler):
    """
    Production-grade logging handler for immudb.
    - Fully async using an internal queue (non-blocking)
    - Supports all Python logging levels
    - Captures exception info (tracebacks)
    - Thread-safe
    - Automatically reconnects if immudb becomes unavailable
    """

    def __init__(
        self,
        host="0.0.0.0",
        port=3322,
        user="immudb",
        password="immudb",
        prefix="log",
        max_queue_size=10000,
        reconnect_interval=30,
    ):
        super().__init__()
        self.prefix = prefix
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.reconnect_interval = reconnect_interval

        # internal queue to avoid blocking application code
        self.queue = queue.Queue(maxsize=max_queue_size)

        # immudb connection
        self.connected = False
        self.client = None
        self._try_connect()

        # background worker thread
        self._running = True
        self._last_reconnect_attempt = time.time()
        self.worker = threading.Thread(target=self._process_queue, daemon=True)
        self.worker.start()

    def _try_connect(self):
        """Attempt to connect to immudb. Sets self.connected on result."""
        try:
            self.client = ImmudbClient(f"{self.host}:{self.port}")
            self.client.login(self.user, self.password)
            self.connected = True
        except Exception as e:
            self.connected = False
            self.client = None
            import sys
            print(
                f"immudb connection failed: {e}. Falling back to file-only logging.",
                file=sys.stderr,
            )

    def emit(self, record):
        """
        Serialize and queue log record.
        Never blocks application threads.
        Skips silently if not connected to immudb.
        """
        if not self.connected:
            return
        try:
            log_entry = self._serialize(record)
            self.queue.put_nowait(log_entry)
        except queue.Full:
            # Drop log if queue is full — fail-safe behavior
            pass
        except Exception:
            self.handleError(record)

    def _serialize(self, record):
        """
        Convert log record → JSON-serializable dict.
        """
        timestamp = int(time.time() * 1000)

        entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
            "func": record.funcName,
            "process": record.process,
            "thread": record.thread,
        }

        # Include exception/traceback if present
        if record.exc_info:
            formatter = self.formatter or logging.Formatter()
            entry["exception"] = formatter.formatException(record.exc_info)

        key = f"{self.prefix}:{timestamp}:{record.levelname}".encode()
        value = json.dumps(entry).encode()

        return key, value

    def _process_queue(self):
        """
        Background worker that writes logs to immudb.
        Periodically attempts to reconnect if disconnected.
        """
        while self._running:
            # If disconnected, try to reconnect at the configured interval
            if not self.connected:
                now = time.time()
                if now - self._last_reconnect_attempt >= self.reconnect_interval:
                    self._last_reconnect_attempt = now
                    self._try_connect()
                    if self.connected:
                        import sys
                        print("immudb connection re-established.", file=sys.stderr)
                time.sleep(0.1)
                continue

            try:
                key, value = self.queue.get(timeout=0.1)
                self.client.set(key, value)
            except queue.Empty:
                continue
            except Exception:
                self.connected = False
                # Set last attempt to 0 so reconnect is tried immediately
                self._last_reconnect_attempt = 0

    def close(self):
        """
        Flush queue and stop thread.
        """
        self._running = False
        self.worker.join(timeout=2)
        super().close()

    def scan_logs(self, limit=100, reverse=False):
        """
        Works with immudb-py versions where scan() returns Dict[bytes, bytes].
        reverse=False -> ascending order
        reverse=True -> descending order
        """

        prefix = f"{self.prefix}:".encode()

        # key: b'' means "start from beginning"
        seek_key = b""

        try:
            raw = self.client.scan(
                key=seek_key,
                prefix=prefix,
                desc=reverse,
                limit=limit
            )
        except Exception as e:
            raise RuntimeError(f"immudb scan failed: {e}")

        logs = []
        for key_bytes, val_bytes in raw.items():
            try:
                key_str = key_bytes.decode()
            except Exception:
                key_str = repr(key_bytes)

            try:
                # values are JSON strings
                value = json.loads(val_bytes.decode())
            except Exception:
                value = val_bytes.decode(errors="replace")

            logs.append({
                "key": key_str,
                "value": value
            })

        return logs
