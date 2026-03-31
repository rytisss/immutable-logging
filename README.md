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
2025-11-24 20:47:45,064 [DEBUG] CVDLINK test logger (main.py:37): Debug details for developers
2025-11-24 20:47:45,066 [INFO] CVDLINK test logger (main.py:38): Service started
2025-11-24 20:47:45,066 [WARNING] CVDLINK test logger (main.py:39): Memory usage near threshold
2025-11-24 20:47:45,066 [ERROR] CVDLINK test logger (main.py:40): Database connection timeout
2025-11-24 20:47:45,066 [CRITICAL] CVDLINK test logger (main.py:41): System failure
```

## TODOs & resources worth reading:  
[Tampering detection using **The Auditor**](https://docs.immudb.io/master/production/auditor.html#running-an-auditor-with-immuclient)
