__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import hashlib
import logging
import os
import tempfile
import unittest
from logging.handlers import RotatingFileHandler

from immutable_logging.integrity import IntegrityHandler, SingleLineFormatter
from immutable_logging.verify import verify_log_integrity

GENESIS_HASH = "0" * 64


def _create_log_pair(tmpdir, log_lines):
    """Create a valid log file and its integrity sidecar."""
    log_path = os.path.join(tmpdir, "test.log")
    integrity_path = log_path + ".integrity"

    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write("\n".join(log_lines) + "\n" if log_lines else "")

    prev_hash = GENESIS_HASH
    with open(integrity_path, "w", encoding="utf-8") as hf:
        for i, line in enumerate(log_lines, start=1):
            current_hash = hashlib.sha256(
                (line + prev_hash).encode()
            ).hexdigest()
            hf.write(f"{i}|sha256={current_hash}|prev={prev_hash}\n")
            prev_hash = current_hash

    return log_path


class TestVerifyLogIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_clean_log_passes(self):
        log_path = _create_log_pair(self.tmpdir, [
            "2026-04-09 10:00:00,000 [INFO] logger (main.py:1): Started",
            "2026-04-09 10:00:01,000 [DEBUG] logger (main.py:2): Details",
        ])
        result = verify_log_integrity(log_path)
        self.assertTrue(result.passed)
        self.assertEqual(result.tampered, 0)
        self.assertEqual(result.missing, 0)

    def test_tampered_entry_detected(self):
        log_path = _create_log_pair(self.tmpdir, [
            "2026-04-09 10:00:00,000 [INFO] logger (main.py:1): Started",
            "2026-04-09 10:00:01,000 [DEBUG] logger (main.py:2): Details",
        ])
        # Tamper with line 2
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[1] = "2026-04-09 10:00:01,000 [DEBUG] logger (main.py:2): HACKED\n"
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        result = verify_log_integrity(log_path)
        self.assertFalse(result.passed)
        self.assertEqual(result.tampered, 1)
        self.assertIn(2, result.tampered_lines)

    def test_deleted_entry_detected(self):
        log_path = _create_log_pair(self.tmpdir, [
            "2026-04-09 10:00:00,000 [INFO] logger (main.py:1): Line 1",
            "2026-04-09 10:00:01,000 [INFO] logger (main.py:2): Line 2",
            "2026-04-09 10:00:02,000 [INFO] logger (main.py:3): Line 3",
        ])
        # Delete line 2 from the log file
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(lines[0])
            f.write(lines[2])
        result = verify_log_integrity(log_path)
        self.assertFalse(result.passed)
        self.assertGreater(result.missing, 0)

    def test_missing_integrity_file(self):
        log_path = os.path.join(self.tmpdir, "no_integrity.log")
        with open(log_path, "w") as f:
            f.write("some log line\n")
        result = verify_log_integrity(log_path)
        self.assertFalse(result.passed)
        self.assertTrue(result.no_integrity_file)

    def test_empty_log_passes(self):
        log_path = _create_log_pair(self.tmpdir, [])
        result = verify_log_integrity(log_path)
        self.assertTrue(result.passed)

    def test_inserted_entry_detected(self):
        log_path = _create_log_pair(self.tmpdir, [
            "2026-04-09 10:00:00,000 [INFO] logger (main.py:1): Line 1",
            "2026-04-09 10:00:02,000 [INFO] logger (main.py:3): Line 3",
        ])
        # Insert a line between line 1 and line 3
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines.insert(1, "2026-04-09 10:00:01,000 [INFO] logger (main.py:2): INSERTED\n")
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        result = verify_log_integrity(log_path)
        self.assertFalse(result.passed)


def _run_session(log_path, messages, exception_at=None):
    """Mimic one process run of the basic example: file handler + integrity handler
    sharing a SingleLineFormatter, writing `messages` and optionally raising an exception."""
    logger = logging.getLogger(f"test.{log_path}.{id(messages)}")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    formatter = SingleLineFormatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )
    integrity = IntegrityHandler(log_path + ".integrity")
    integrity.setFormatter(formatter)
    file_handler = RotatingFileHandler(log_path, maxBytes=10_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(integrity)
    logger.addHandler(file_handler)

    for i, msg in enumerate(messages):
        if exception_at is not None and i == exception_at:
            try:
                1 / 0
            except ZeroDivisionError:
                logger.exception(msg)
        else:
            logger.info(msg)

    integrity.close()
    file_handler.close()


class TestEndToEnd(unittest.TestCase):
    """Regression tests for the two bugs that broke `python examples/basic_usage.py`
    on the second run: multi-line exception records and chain restart on process
    start. Both must verify cleanly without anyone tampering with the files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "session.log")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_single_run_with_exception_verifies(self):
        _run_session(self.log_path, ["start", "boom", "end"], exception_at=1)
        result = verify_log_integrity(self.log_path)
        self.assertTrue(result.passed, msg=result.summary)
        self.assertEqual(result.tampered, 0)
        self.assertEqual(result.missing, 0)

    def test_two_sequential_runs_verify(self):
        _run_session(self.log_path, ["run1 a", "run1 b"])
        _run_session(self.log_path, ["run2 a", "run2 b"])
        result = verify_log_integrity(self.log_path)
        self.assertTrue(result.passed, msg=result.summary)
        self.assertEqual(result.tampered, 0)
        self.assertEqual(result.missing, 0)

    def test_two_runs_with_exceptions_verify(self):
        """The exact failure mode the user reported: re-running basic_usage.py
        flagged the previous run's exception traceback as tampering."""
        _run_session(self.log_path, ["start", "boom", "end"], exception_at=1)
        _run_session(self.log_path, ["start", "boom", "end"], exception_at=1)
        result = verify_log_integrity(self.log_path)
        self.assertTrue(result.passed, msg=result.summary)

    def test_real_tamper_still_detected_after_fix(self):
        _run_session(self.log_path, ["start", "boom", "end"], exception_at=1)
        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace("start", "HACKED")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        result = verify_log_integrity(self.log_path)
        self.assertFalse(result.passed)
        self.assertGreaterEqual(result.tampered, 1)


if __name__ == "__main__":
    unittest.main()
