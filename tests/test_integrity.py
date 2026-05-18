import hashlib
import logging
import os
import sys
import tempfile
import unittest

from immutable_logging.integrity import IntegrityHandler, SingleLineFormatter

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


if __name__ == "__main__":
    unittest.main()
