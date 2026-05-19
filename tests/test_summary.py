__author__ = "Rytis Augustauskas"
__email__ = "rytis.here@gmail.com"

from immutable_logging.verify import VerifyResult


def test_summary_when_passed():
    r = VerifyResult(passed=True, tampered=0, missing=0)
    # Track entry count via the details list (one detail per verified line).
    r.details = ["Line 1: OK", "Line 2: OK", "Line 3: OK"]
    assert r.summary == "OK: 3 entries verified"


def test_summary_when_no_integrity_file():
    r = VerifyResult(passed=False, no_integrity_file=True)
    assert r.summary == "No previous integrity file found"


def test_summary_when_tampered_only():
    r = VerifyResult(passed=False, tampered=3, missing=0)
    assert r.summary == "FAILED: 3 tampered, 0 missing"


def test_summary_when_missing_only():
    r = VerifyResult(passed=False, tampered=0, missing=2)
    assert r.summary == "FAILED: 0 tampered, 2 missing"


def test_summary_when_both_tampered_and_missing():
    r = VerifyResult(passed=False, tampered=4, missing=1)
    assert r.summary == "FAILED: 4 tampered, 1 missing"


def test_summary_thousand_separator():
    r = VerifyResult(passed=True)
    r.details = ["Line {}: OK".format(i) for i in range(1, 1248)]
    assert r.summary == "OK: 1,247 entries verified"
