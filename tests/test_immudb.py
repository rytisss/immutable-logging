import json
import logging
import os
import queue
import shutil
import tempfile
import time
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch, call
from datetime import datetime

import pytest

from immutable_logging.immudb import ImmuDBHandler

pytestmark = pytest.mark.immudb


def make_handler(**kwargs):
    """Create an ImmuDBHandler with a mocked immudb client."""
    with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
        mock_client = MockClient.return_value
        handler = ImmuDBHandler(**kwargs)
        handler.client = mock_client
        return handler, mock_client


class TestImmuDBHandlerInit(unittest.TestCase):
    def test_defaults(self):
        handler, _ = make_handler()
        self.assertEqual(handler.prefix, "log")
        self.assertTrue(handler.worker.is_alive())
        self.assertTrue(handler._running)

    def test_custom_prefix(self):
        handler, _ = make_handler(prefix="myapp")
        self.assertEqual(handler.prefix, "myapp")

    def test_login_called(self):
        with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
            mock_client = MockClient.return_value
            ImmuDBHandler(user="admin", password="secret")
            mock_client.login.assert_called_once_with("admin", "secret")

    def test_connected_true_on_success(self):
        handler, _ = make_handler()
        self.assertTrue(handler.connected)

    def test_connected_false_on_login_failure(self):
        with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.login.side_effect = Exception("Connection refused")
            handler = ImmuDBHandler()
            self.assertFalse(handler.connected)


class TestSerialize(unittest.TestCase):
    def setUp(self):
        self.handler, _ = make_handler()

    def _make_record(self, msg="hello", level=logging.INFO, exc_info=None):
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test_file.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )
        return record

    def test_key_format(self):
        record = self._make_record()
        key, value = self.handler._serialize(record)
        decoded_key = key.decode()
        parts = decoded_key.split(":")
        self.assertEqual(parts[0], "log")
        self.assertTrue(parts[1].isdigit())
        self.assertEqual(parts[2], "INFO")

    def test_value_fields(self):
        record = self._make_record(msg="test message", level=logging.WARNING)
        key, value = self.handler._serialize(record)
        entry = json.loads(value.decode())
        self.assertEqual(entry["message"], "test message")
        self.assertEqual(entry["level"], "WARNING")
        self.assertEqual(entry["logger"], "test.logger")
        self.assertEqual(entry["lineno"], 42)
        self.assertIn("timestamp", entry)
        self.assertIn("process", entry)
        self.assertIn("thread", entry)

    def test_timestamp_is_milliseconds(self):
        before = int(time.time() * 1000)
        record = self._make_record()
        key, value = self.handler._serialize(record)
        after = int(time.time() * 1000)
        entry = json.loads(value.decode())
        self.assertGreaterEqual(entry["timestamp"], before)
        self.assertLessEqual(entry["timestamp"], after)

    def test_no_exception_field_by_default(self):
        record = self._make_record()
        _, value = self.handler._serialize(record)
        entry = json.loads(value.decode())
        self.assertNotIn("exception", entry)

    def test_exception_field_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = self._make_record(exc_info=exc_info)
        _, value = self.handler._serialize(record)
        entry = json.loads(value.decode())
        self.assertIn("exception", entry)
        self.assertIn("ValueError", entry["exception"])
        self.assertIn("boom", entry["exception"])

    def test_key_is_bytes(self):
        record = self._make_record()
        key, value = self.handler._serialize(record)
        self.assertIsInstance(key, bytes)
        self.assertIsInstance(value, bytes)

    def test_custom_prefix_in_key(self):
        handler, _ = make_handler(prefix="svc")
        record = self._make_record()
        key, _ = handler._serialize(record)
        self.assertTrue(key.decode().startswith("svc:"))


class TestEmit(unittest.TestCase):
    def setUp(self):
        self.handler, self.mock_client = make_handler()

    def _make_record(self, msg="msg", level=logging.DEBUG):
        return logging.LogRecord(
            name="test", level=level, pathname="f.py",
            lineno=1, msg=msg, args=(), exc_info=None,
        )

    def test_emit_puts_entry_in_queue(self):
        record = self._make_record()
        self.handler.emit(record)
        self.assertFalse(self.handler.queue.empty())

    def test_emit_does_not_block_on_full_queue(self):
        handler, _ = make_handler(max_queue_size=1)
        # Pause background worker by replacing queue with a controlled one
        handler.queue = queue.Queue(maxsize=1)
        handler.queue.put(("k", "v"))  # fill it
        record = self._make_record()
        # Should not raise and should not block
        handler.emit(record)  # queue.Full is swallowed

    def test_emit_queued_entry_is_tuple(self):
        record = self._make_record(msg="hello")
        self.handler.emit(record)
        entry = self.handler.queue.get_nowait()
        self.assertIsInstance(entry, tuple)
        self.assertEqual(len(entry), 2)

    def test_emit_skips_queue_when_disconnected(self):
        handler, _ = make_handler()
        handler.connected = False
        record = self._make_record()
        handler.emit(record)
        self.assertTrue(handler.queue.empty())


class TestProcessQueue(unittest.TestCase):
    def test_worker_calls_client_set(self):
        handler, mock_client = make_handler()
        key = b"log:123:INFO"
        value = b'{"message": "hi"}'
        handler.queue.put((key, value))
        time.sleep(0.1)  # let worker consume
        mock_client.set.assert_called_once_with(key, value)

    def test_worker_reconnects_on_client_error(self):
        with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
            mock_client = MockClient.return_value
            # First set call raises, causing reconnect; second succeeds
            mock_client.set.side_effect = [Exception("conn lost"), None]
            handler = ImmuDBHandler()

            key = b"log:1:INFO"
            value = b"{}"
            handler.queue.put((key, value))
            handler.queue.put((key, value))
            time.sleep(0.3)

            # A new ImmudbClient should have been constructed (reconnect)
            self.assertGreaterEqual(MockClient.call_count, 2)


class TestScanLogs(unittest.TestCase):
    def setUp(self):
        self.handler, self.mock_client = make_handler()

    def _make_raw(self, entries):
        """Build the dict[bytes, bytes] that immudb.scan() returns."""
        result = {}
        for key_str, value_dict in entries:
            result[key_str.encode()] = json.dumps(value_dict).encode()
        return result

    def test_returns_list_of_dicts(self):
        self.mock_client.scan.return_value = self._make_raw([
            ("log:1000:INFO", {"message": "hello", "level": "INFO", "timestamp": 1000}),
        ])
        logs = self.handler.scan_logs(limit=1)
        self.assertEqual(len(logs), 1)
        self.assertIn("key", logs[0])
        self.assertIn("value", logs[0])

    def test_key_decoded_to_string(self):
        self.mock_client.scan.return_value = self._make_raw([
            ("log:999:DEBUG", {"message": "x", "timestamp": 999}),
        ])
        logs = self.handler.scan_logs()
        self.assertEqual(logs[0]["key"], "log:999:DEBUG")

    def test_value_parsed_from_json(self):
        payload = {"message": "test", "level": "ERROR", "timestamp": 5000}
        self.mock_client.scan.return_value = self._make_raw([
            ("log:5000:ERROR", payload),
        ])
        logs = self.handler.scan_logs()
        self.assertEqual(logs[0]["value"], payload)

    def test_scan_called_with_prefix(self):
        self.mock_client.scan.return_value = {}
        self.handler.scan_logs(limit=10, reverse=True)
        self.mock_client.scan.assert_called_once_with(
            key=b"",
            prefix=b"log:",
            desc=True,
            limit=10,
        )

    def test_scan_failure_raises_runtime_error(self):
        self.mock_client.scan.side_effect = Exception("network error")
        with self.assertRaises(RuntimeError) as ctx:
            self.handler.scan_logs()
        self.assertIn("immudb scan failed", str(ctx.exception))

    def test_invalid_json_value_returns_string(self):
        self.mock_client.scan.return_value = {
            b"log:1:INFO": b"not-json"
        }
        logs = self.handler.scan_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["value"], "not-json")

    def test_empty_scan_returns_empty_list(self):
        self.mock_client.scan.return_value = {}
        logs = self.handler.scan_logs()
        self.assertEqual(logs, [])


class TestReconnection(unittest.TestCase):
    def test_reconnects_after_interval(self):
        with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
            mock_client = MockClient.return_value
            # First login fails (init), second succeeds (reconnect)
            mock_client.login.side_effect = [Exception("refused"), None]
            handler = ImmuDBHandler(reconnect_interval=0.1)
            self.assertFalse(handler.connected)
            # Wait for reconnection attempt
            time.sleep(0.3)
            self.assertTrue(handler.connected)

    def test_no_reconnect_before_interval(self):
        with patch("immutable_logging.immudb.ImmudbClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.login.side_effect = [Exception("refused"), None]
            handler = ImmuDBHandler(reconnect_interval=10)
            self.assertFalse(handler.connected)
            time.sleep(0.2)
            # Should still be disconnected — interval hasn't elapsed
            self.assertFalse(handler.connected)


class TestClose(unittest.TestCase):
    def test_close_sets_running_false(self):
        handler, _ = make_handler()
        handler.close()
        self.assertFalse(handler._running)


class TestPrintLog(unittest.TestCase):
    """Tests for the print_log helper in main.py."""

    def _make_entry(self, ts_ms=1_700_000_000_000, level="INFO", message="hello",
                    logger="test", filename="app.py", lineno=10, func="run"):
        return {
            "key": f"log:{ts_ms}:{level}",
            "value": {
                "timestamp": ts_ms,
                "level": level,
                "message": message,
                "logger": logger,
                "filename": filename,
                "lineno": lineno,
                "func": func,
            }
        }

    def _capture_print_log(self, entry):
        import io, sys
        # Import here to avoid triggering ImmuDBHandler at module level
        with patch("immutable_logging.immudb.ImmudbClient"):
            import importlib
            import examples.basic_usage as m
        captured = io.StringIO()
        sys.stdout = captured
        try:
            m.print_log(entry)
        finally:
            sys.stdout = sys.__stdout__
        return captured.getvalue()

    def test_output_contains_message(self):
        entry = self._make_entry(message="Service started")
        output = self._capture_print_log(entry)
        self.assertIn("Service started", output)

    def test_output_contains_level(self):
        entry = self._make_entry(level="WARNING")
        output = self._capture_print_log(entry)
        self.assertIn("WARNING", output)

    def test_output_contains_filename_and_lineno(self):
        entry = self._make_entry(filename="worker.py", lineno=99)
        output = self._capture_print_log(entry)
        self.assertIn("worker.py:99", output)

    def test_output_contains_func(self):
        entry = self._make_entry(func="process_event")
        output = self._capture_print_log(entry)
        self.assertIn("process_event", output)

    def test_output_contains_key(self):
        entry = self._make_entry()
        output = self._capture_print_log(entry)
        self.assertIn(entry["key"], output)

    def test_timestamp_format(self):
        # Use a known timestamp: 2023-11-14 22:13:20.000 UTC (approx, local TZ may vary)
        ts_ms = 1_700_000_000_000
        entry = self._make_entry(ts_ms=ts_ms)
        output = self._capture_print_log(entry)
        expected_ts = datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
        self.assertIn(expected_ts, output)


class TestStartupVerification(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_startup_check_logs_info_on_clean(self):
        from immutable_logging.verify import verify_log_integrity
        # Create an empty log — should pass
        log_path = os.path.join(self.tmpdir, "test.log")
        integrity_path = log_path + ".integrity"
        open(log_path, "w").close()
        open(integrity_path, "w").close()
        result = verify_log_integrity(log_path)
        self.assertTrue(result.passed)

    def test_startup_check_detects_tampered(self):
        from immutable_logging.verify import verify_log_integrity
        import hashlib

        log_path = os.path.join(self.tmpdir, "test.log")
        integrity_path = log_path + ".integrity"

        with open(log_path, "w") as f:
            f.write("tampered line\n")

        genesis = "0" * 64
        original_hash = hashlib.sha256(
            ("original line" + genesis).encode()
        ).hexdigest()
        with open(integrity_path, "w") as f:
            f.write(f"1|sha256={original_hash}|prev={genesis}\n")

        result = verify_log_integrity(log_path)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
