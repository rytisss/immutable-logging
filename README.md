# immutable-logging for Python

This project demonstrates a **production-ready, immutable logging system** using [immudb](https://immudb.io/), an open-source cryptographically verifiable database. Logs are stored in an append-only, tamper-evident database while optionally also being written to local files. This ensures **full auditability, traceability, and integrity** of all application events.

<p align="center">
  <img width="585" height="215" alt="image" src="https://github.com/user-attachments/assets/a43ce8e2-28fd-4aa9-ae6c-f6972e4cb767" />
</p>


---

## Features

- **Immutable Logging**: All log entries are stored in immudb with cryptographic verification.
- **Native Python Logging Levels**: Supports `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
- **Exception Logging**: Automatically captures exceptions and tracebacks.
- **Dual Output**: Logs can be stored in immudb **and** written to a rotating file for easy inspection.
- **Thread-Safe & Non-blocking**: Uses a queue and background worker to prevent application slowdowns.
- **Docker-Ready**: Includes a Docker Compose setup for running immudb and your application together.
- **Pretty-Printed Output**: Human-readable display of immudb log entries.
- **Tamper-Proof File Logs**: SHA-256 hash chain written to a `.integrity` sidecar file detects modifications, deletions, and insertions.
- **Graceful immudb Fallback**: Works without immudb — falls back to file + console logging, retries connection every 30 seconds.
- **Log Integrity Verification**: CLI tool and startup check to verify log file integrity.

---

## How It Works

1. Log messages are generated using Python’s standard logging module.
2. Each log record is serialized with metadata, including:
   - Timestamp
   - Logger name
   - File and line number
   - Function name
   - Log level
3. Records are sent to immudb, where:
   - Each write is **append-only**.
   - Updates create new versions while preserving the full historical record.
   - Cryptographic proofs ensure tamper-evidence.
4. Optionally, logs are also written to a local file using a rotating file handler.
5. A SHA-256 hash chain is written to a `.integrity` sidecar file. Each entry's hash covers its full content plus the previous hash, forming a tamper-evident chain that can be independently verified.

---

## Benefits

- **Auditability**: Every event can be independently verified.
- **Traceability**: Complete history of changes is preserved.
- **Compliance**: Suitable for systems requiring strict data integrity standards.
- **Flexible**: Language-agnostic logging pattern; applications only need to append events.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- pip

### Run immudb with Docker and expose a few ports for the communication:  

```bash
docker run -d -p 3322:3322 -p 8080:8080 -it --rm --name immudb codenotary/immudb:latest
```

### Install requirements  

```bash
pip install -r requirements.txt
```

### Run the application
```bash
python main.py
```

## Log sinks
- Logs are stored in immudb:
```bash
--- Latest immudb logs ---
[2026-03-31 11:05:55.026] DEBUG    Debug details for developers
    Logger: CVDLINK test logger
    File:   main.py:50
    Func:   main
    Key:    log:1774944355026:DEBUG

[2026-03-31 11:05:55.027] CRITICAL System failure
    Logger: CVDLINK test logger
    File:   main.py:54
    Func:   main
    Key:    log:1774944355027:CRITICAL

[2026-03-31 11:05:55.027] ERROR    Database connection timeout
    Logger: CVDLINK test logger
    File:   main.py:53
    Func:   main
    Key:    log:1774944355027:ERROR

[2026-03-31 11:05:55.027] INFO     Service started
    Logger: CVDLINK test logger
    File:   main.py:51
    Func:   main
    Key:    log:1774944355027:INFO

[2026-03-31 11:05:55.027] WARNING  Memory usage near threshold
    Logger: CVDLINK test logger
    File:   main.py:52
    Func:   main
    Key:    log:1774944355027:WARNING

[2026-03-31 11:05:55.028] ERROR    Unhandled exception occurred
    Logger: CVDLINK test logger
    File:   main.py:60
    Func:   main
    Key:    log:1774944355028:ERROR

```
- Rotating file logs are saved to **cvdlink.log**:
```bash
2026-03-31 11:11:08,615 [DEBUG] CVDLINK test logger (main.py:50): Debug details for developers
2026-03-31 11:11:08,616 [INFO] CVDLINK test logger (main.py:51): Service started
2026-03-31 11:11:08,616 [WARNING] CVDLINK test logger (main.py:52): Memory usage near threshold
2026-03-31 11:11:08,616 [ERROR] CVDLINK test logger (main.py:53): Database connection timeout
2026-03-31 11:11:08,616 [CRITICAL] CVDLINK test logger (main.py:54): System failure
2026-03-31 11:11:08,616 [ERROR] CVDLINK test logger (main.py:60): Unhandled exception occurred
Traceback (most recent call last):
  File "c:\src\Projects\immutable_logging\main.py", line 58, in main
    1 / 0
    ~~^~~
ZeroDivisionError: division by zero
```

## Running Tests

The test suite uses only the standard library (`unittest`) and mocks the immudb client, so **no running immudb instance is required**.

```bash
python -m pytest test_immudb_handler.py test_integrity_handler.py test_verify_logs.py -v
```

---

## Tamper-Proof Logging

Each log entry's full content (timestamp, level, logger, file, line, message) is hashed with SHA-256 and chained to the previous entry's hash — similar to how Git links commits. The hash chain is stored in a sidecar `.integrity` file alongside the main log.

**`cvdlink.log`** stays human-readable and unchanged:
```bash
2026-04-09 10:00:01,123 [INFO] CVDLINK test logger (main.py:51): Service started
2026-04-09 10:00:01,124 [DEBUG] CVDLINK test logger (main.py:50): Debug details
```

**`cvdlink.log.integrity`** stores the hash chain:
```bash
1|sha256=a3f2b8c1...|prev=0000000000000000000000000000000000000000000000000000000000000000
2|sha256=7e1d4af2...|prev=a3f2b8c1...
```

If anyone modifies, deletes, or inserts a log entry, the chain breaks and verification catches it.

## Verifying Log Integrity

### CLI verification
```bash
python verify_logs.py cvdlink.log
```

**Clean output:**
```bash
Verifying cvdlink.log...
Line 1: OK
Line 2: OK
Line 3: OK

Result: PASSED — all entries verified
```

**Tampered output:**
```bash
Verifying cvdlink.log...
Line 1: OK
Line 2: TAMPERED
Line 3: OK

Result: FAILED — 1 tampered, 0 missing entries
```

### Startup verification
The application automatically checks log integrity on startup and logs the result:
```bash
2026-04-09 10:00:00,000 [INFO] CVDLINK test logger: Log integrity check passed.
```

## Graceful immudb Fallback

The system works without immudb running. If immudb is unreachable:
1. A warning is printed: `immudb connection failed: <reason>. Falling back to file-only logging.`
2. Logs continue to file (`cvdlink.log`), integrity sidecar (`.integrity`), and console (stderr).
3. A background thread retries the connection every 30 seconds.
4. When immudb becomes available, logging resumes to immudb automatically.

## TODOs & resources worth reading:  
[Tampering detection using **The Auditor**](https://docs.immudb.io/master/production/auditor.html#running-an-auditor-with-immuclient)
