"""Immutable logging primitives: SHA-256 hash-chain integrity + optional immudb backend."""

from immutable_logging.integrity import IntegrityHandler, SingleLineFormatter
from immutable_logging.verify import VerifyResult, verify_log_integrity

__version__ = "0.1.0"

__all__ = [
    "IntegrityHandler",
    "ImmuDBHandler",
    "SingleLineFormatter",
    "VerifyResult",
    "verify_log_integrity",
    "__version__",
]


def __getattr__(name):
    """PEP 562 module-level __getattr__: lazy-load ImmuDBHandler.

    The immudb submodule does `from immudb.client import ImmudbClient` at the top,
    so it will raise ImportError if the [immudb] extra is not installed. We catch
    that and re-raise with a friendlier message pointing at the install command.
    """
    if name == "ImmuDBHandler":
        try:
            from immutable_logging.immudb import ImmuDBHandler
        except ImportError as exc:
            raise ImportError(
                "ImmuDBHandler requires the [immudb] extra. "
                "Install with: pip install immutable_logging[immudb]"
            ) from exc
        return ImmuDBHandler
    raise AttributeError(f"module 'immutable_logging' has no attribute {name!r}")
