__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

import hashlib
import logging
import os
import sys
import tempfile
import unittest

from immutable_logging.integrity import (
    IntegrityHandler,
    IntegrityRotatingFileHandler,
    SingleLineFormatter,
)
from immutable_logging.verify import verify_log_integrity

GENESIS_HASH = "0" * 64


class TestIntegrityHandler(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "test.log.integrity")
        self.handler = IntegrityHandler(self.log_path)
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
        )
        self.handler.setFormatter(self.formatter)

    def tearDown(self):
        self.handler.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _make_record(self, msg="hello", level=logging.INFO):
        return logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test_file.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_first_entry_uses_genesis_hash(self):
        record = self._make_record()
        self.handler.emit(record)
        with open(self.log_path) as f:
            line = f.readline().strip()
        parts = line.split("|")
        self.assertEqual(parts[0], "1")
        self.assertTrue(parts[2].startswith("prev="))
        prev_hash = parts[2].split("=", 1)[1]
        self.assertEqual(prev_hash, GENESIS_HASH)

    def test_hash_chain_links_correctly(self):
        record1 = self._make_record(msg="first")
        record2 = self._make_record(msg="second")
        self.handler.emit(record1)
        self.handler.emit(record2)
        with open(self.log_path) as f:
            lines = f.readlines()
        line1_parts = lines[0].strip().split("|")
        line2_parts = lines[1].strip().split("|")
        hash1 = line1_parts[1].split("=", 1)[1]
        prev2 = line2_parts[2].split("=", 1)[1]
        self.assertEqual(hash1, prev2)

    def test_hash_computation(self):
        record = self._make_record(msg="test message")
        self.handler.emit(record)
        formatted_line = self.formatter.format(record)
        expected_hash = hashlib.sha256(
            (formatted_line + GENESIS_HASH).encode()
        ).hexdigest()
        with open(self.log_path) as f:
            line = f.readline().strip()
        stored_hash = line.split("|")[1].split("=", 1)[1]
        self.assertEqual(stored_hash, expected_hash)

    def test_line_numbers_increment(self):
        for i in range(5):
            self.handler.emit(self._make_record(msg=f"msg {i}"))
        with open(self.log_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines, start=1):
            line_num = int(line.strip().split("|")[0])
            self.assertEqual(line_num, i)

    def test_reset_chain(self):
        self.handler.emit(self._make_record(msg="before reset"))
        self.handler.reset_chain()
        self.handler.emit(self._make_record(msg="after reset"))
        with open(self.log_path) as f:
            lines = f.readlines()
        last_line_parts = lines[-1].strip().split("|")
        prev_hash = last_line_parts[2].split("=", 1)[1]
        self.assertEqual(prev_hash, GENESIS_HASH)
        line_num = int(last_line_parts[0])
        self.assertEqual(line_num, 1)

    def test_init_resumes_chain_from_existing_file(self):
        """A new handler instance on an existing integrity file continues the chain
        instead of restarting at GENESIS — required to survive process restarts."""
        self.handler.emit(self._make_record(msg="first"))
        self.handler.emit(self._make_record(msg="second"))
        self.handler.close()

        resumed = IntegrityHandler(self.log_path)
        resumed.setFormatter(self.formatter)
        resumed.emit(self._make_record(msg="third"))
        resumed.close()

        with open(self.log_path) as f:
            lines = [l.strip() for l in f.readlines()]
        self.assertEqual(len(lines), 3)

        line2_hash = lines[1].split("|")[1].split("=", 1)[1]
        line3_parts = lines[2].split("|")
        line3_num = int(line3_parts[0])
        line3_prev = line3_parts[2].split("=", 1)[1]

        self.assertEqual(line3_num, 3, "line numbers should continue across restart")
        self.assertEqual(line3_prev, line2_hash, "chain should link to previous run's last hash")

    def test_init_handles_empty_integrity_file(self):
        """An empty integrity file (created but never written) should start at GENESIS."""
        open(self.log_path, "w").close()
        handler = IntegrityHandler(self.log_path)
        handler.setFormatter(self.formatter)
        handler.emit(self._make_record(msg="first"))
        handler.close()

        with open(self.log_path) as f:
            line = f.readline().strip()
        parts = line.split("|")
        self.assertEqual(int(parts[0]), 1)
        self.assertEqual(parts[2].split("=", 1)[1], GENESIS_HASH)


class TestSingleLineFormatter(unittest.TestCase):
    def _make_record(self, msg="hello", exc_info=None):
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )

    def test_escapes_newlines_in_message(self):
        fmt = SingleLineFormatter("%(message)s")
        out = fmt.format(self._make_record(msg="line1\nline2\nline3"))
        self.assertNotIn("\n", out)
        self.assertEqual(out, "line1\\nline2\\nline3")

    def test_escapes_carriage_returns(self):
        fmt = SingleLineFormatter("%(message)s")
        out = fmt.format(self._make_record(msg="a\r\nb"))
        self.assertNotIn("\n", out)
        self.assertNotIn("\r", out)

    def test_escapes_backslashes_first(self):
        """Backslashes must be escaped before \\n so the result is reversible
        and a literal '\\n' in the message doesn't collide with an escaped newline."""
        fmt = SingleLineFormatter("%(message)s")
        out = fmt.format(self._make_record(msg="path\\to\\file"))
        self.assertEqual(out, "path\\\\to\\\\file")

    def test_escapes_exception_traceback(self):
        fmt = SingleLineFormatter("%(message)s")
        try:
            1 / 0
        except ZeroDivisionError:
            rec = self._make_record(msg="boom", exc_info=sys.exc_info())
        out = fmt.format(rec)
        self.assertNotIn("\n", out)
        self.assertIn("ZeroDivisionError", out)


class TestIntegrityRotatingFileHandler(unittest.TestCase):
    """The rotating handler must rotate the .integrity sidecar in lockstep with
    the .log file, and rotated pairs must verify independently."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "app.log")
        self.integrity_path = self.log_path + ".integrity"

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _build_logger(self, max_bytes, backup_count):
        formatter = SingleLineFormatter("%(message)s")
        rot = IntegrityRotatingFileHandler(
            self.log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        rot.setFormatter(formatter)
        logger = logging.getLogger(f"rot.{id(self)}.{max_bytes}.{backup_count}")
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(rot)
        return logger, rot

    def test_writes_both_log_and_integrity_for_each_record(self):
        logger, rot = self._build_logger(max_bytes=10_000_000, backup_count=3)
        for i in range(5):
            logger.info(f"msg {i}")
        rot.close()

        with open(self.log_path) as f:
            log_lines = f.read().splitlines()
        with open(self.integrity_path) as f:
            int_lines = f.read().splitlines()
        self.assertEqual(len(log_lines), 5)
        self.assertEqual(len(int_lines), 5)

    def test_doRollover_renames_integrity_sidecar(self):
        logger, rot = self._build_logger(max_bytes=200, backup_count=3)
        for i in range(50):
            logger.info("x" * 60)
        rot.close()

        files = set(os.listdir(self.tmpdir))
        self.assertIn("app.log", files)
        self.assertIn("app.log.integrity", files)
        self.assertIn("app.log.1.integrity", files,
                      msg=f"expected rotated sidecar; got {files}")

    def test_chain_resets_on_rollover(self):
        logger, rot = self._build_logger(max_bytes=200, backup_count=3)
        for i in range(50):
            logger.info("x" * 60)
        rot.close()

        with open(self.integrity_path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        parts = first.split("|")
        self.assertEqual(int(parts[0]), 1)
        self.assertEqual(parts[2].split("=", 1)[1], GENESIS_HASH)

    def test_each_rotated_pair_verifies_independently(self):
        logger, rot = self._build_logger(max_bytes=300, backup_count=5)
        for i in range(200):
            logger.info(f"entry {i:04d} " + "x" * 30)
        rot.close()

        result = verify_log_integrity(self.log_path)
        self.assertTrue(result.passed, msg=f"current: {result.summary}")

        rotated = [f for f in os.listdir(self.tmpdir)
                   if f.startswith("app.log.") and f.count(".") == 2 and not f.endswith(".integrity")]
        self.assertGreater(len(rotated), 0, "expected at least one rotation")
        for name in rotated:
            path = os.path.join(self.tmpdir, name)
            result = verify_log_integrity(path)
            self.assertTrue(result.passed, msg=f"{name}: {result.summary}")

    def test_backup_count_limit_enforced_for_sidecars(self):
        logger, rot = self._build_logger(max_bytes=200, backup_count=2)
        for i in range(200):
            logger.info("x" * 60)
        rot.close()

        sidecars = [f for f in os.listdir(self.tmpdir)
                    if f.endswith(".integrity") and f != "app.log.integrity"]
        self.assertLessEqual(len(sidecars), 2,
                             msg=f"too many sidecars retained: {sidecars}")

    def test_keep_all_backups_uses_timestamped_filenames(self):
        """keep_all_backups=True must rename each rolled-over file to a unique
        timestamped name so nothing is ever overwritten or deleted."""
        formatter = SingleLineFormatter("%(message)s")
        rot = IntegrityRotatingFileHandler(
            self.log_path, maxBytes=200, backupCount=0, keep_all_backups=True,
        )
        rot.setFormatter(formatter)
        logger = logging.getLogger(f"rot.keepall.{id(self)}")
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(rot)

        for i in range(200):
            logger.info("x" * 60)
        rot.close()

        files = os.listdir(self.tmpdir)
        # Active log + sidecar.
        self.assertIn("app.log", files)
        self.assertIn("app.log.integrity", files)

        # Rotated logs use timestamp suffix (not numeric), and every rotated
        # log has a matching sidecar with the same suffix.
        rotated_logs = sorted(
            f for f in files
            if f.startswith("app.log.") and not f.endswith(".integrity") and f != "app.log"
        )
        rotated_sidecars = sorted(
            f for f in files
            if f.endswith(".integrity") and f != "app.log.integrity"
        )
        self.assertGreater(len(rotated_logs), 1,
                           msg=f"expected multiple rotations; got {rotated_logs}")
        self.assertEqual(len(rotated_logs), len(rotated_sidecars))
        for log_name in rotated_logs:
            suffix = log_name[len("app.log."):]
            # ISO-style timestamp suffix should contain a 'T' separator.
            self.assertIn("T", suffix, msg=f"non-timestamped name: {log_name}")
            self.assertIn(log_name + ".integrity", rotated_sidecars)

    def test_keep_all_backups_verifies_each_rotated_pair(self):
        formatter = SingleLineFormatter("%(message)s")
        rot = IntegrityRotatingFileHandler(
            self.log_path, maxBytes=300, backupCount=0, keep_all_backups=True,
        )
        rot.setFormatter(formatter)
        logger = logging.getLogger(f"rot.keepall2.{id(self)}")
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(rot)

        for i in range(100):
            logger.info(f"entry {i:04d} " + "x" * 30)
        rot.close()

        log_files = [
            os.path.join(self.tmpdir, f) for f in os.listdir(self.tmpdir)
            if f.startswith("app.log") and not f.endswith(".integrity")
        ]
        self.assertGreater(len(log_files), 1)
        for path in log_files:
            result = verify_log_integrity(path)
            self.assertTrue(result.passed, msg=f"{path}: {result.summary}")


if __name__ == "__main__":
    unittest.main()
