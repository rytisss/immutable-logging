import importlib
import sys
import builtins

import pytest


def test_eager_exports_present():
    import immutable_logging

    assert hasattr(immutable_logging, "IntegrityHandler")
    assert hasattr(immutable_logging, "verify_log_integrity")
    assert hasattr(immutable_logging, "VerifyResult")
    assert hasattr(immutable_logging, "__version__")


def test_import_package_does_not_require_immudb(monkeypatch):
    """`import immutable_logging` must not import `immudb` even transitively."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "immudb" or name.startswith("immudb."):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]

    importlib.import_module("immutable_logging")  # must not raise


def test_top_level_immudb_handler_access_without_extra_raises_friendly_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "immudb" or name.startswith("immudb."):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]

    import immutable_logging

    with pytest.raises(ImportError) as exc_info:
        _ = immutable_logging.ImmuDBHandler

    msg = str(exc_info.value)
    assert "immudb" in msg
    assert "pip install immutable_logging[immudb]" in msg


def test_top_level_immudb_handler_access_with_extra_returns_class():
    """When immudb-py IS installed, the lazy attribute returns the real class."""
    pytest.importorskip("immudb")
    for mod_name in [m for m in list(sys.modules) if m == "immutable_logging" or m.startswith("immutable_logging.")]:
        del sys.modules[mod_name]
    import immutable_logging
    from immutable_logging.immudb import ImmuDBHandler as Direct
    assert immutable_logging.ImmuDBHandler is Direct
