import hashlib
import os
import tempfile
import unittest

from verify_logs import verify_log_integrity

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


if __name__ == "__main__":
    unittest.main()
