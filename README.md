# Quantum-Safe-Messenger

![CI Pipeline](https://github.com/tomciolowsky/Quantum-Safe-Messenger/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.14-blue.svg?logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9.svg?logo=uv)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-teal.svg?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg?logo=docker)
![Standards](https://img.shields.io/badge/NIST-FIPS%20203%20%7C%20FIPS%20204-green.svg)

An **End-to-End Encrypted (E2EE) Messaging Relay** built with NIST Post-Quantum Cryptography standards. The system protects message confidentiality and authenticity against future quantum attacks using **lattice-based cryptography**, designed around a **Zero-Knowledge** relay model where the server never handles plaintext messages or private keys.

## How It Works

1. **Client Setup:** Users generate post-quantum key pairs locally and register their public keys (ML-KEM & ML-DSA) on the relay server.
2. **Key Discovery:** Senders query the relay to retrieve the recipient's public keys.
3. **Client-Side Hybrid Encryption (`HybridParty`):**
   * Derives a 256-bit shared secret and KEM ciphertext using **ML-KEM-768**.
   * Encrypts the plaintext with **AES-256-GCM**, binding `kem_ciphertext + nonce` as Authenticated Associated Data (AAD).
   * Signs the package (`kem_ciphertext + nonce + encrypted_payload`) with **ML-DSA-65** using `context` for domain separation.
4. **Zero-Knowledge Relay:** The server queues and stores encrypted packages in **PostgreSQL** (or async **SQLite** locally) purely as uppercase hex strings.
5. **Client-Side Decryption & Verification:**
   * Recipient fetches messages from the inbox and retrieves the sender's public ML-DSA key.
   * Verifies the **ML-DSA** signature, decapsulates the symmetric key with **ML-KEM**, and decrypts with **AES-256-GCM**.
   * Sends a delivery acknowledgement to mark the message `READ`.

## Cryptographic Core & Security Model

This project builds on my own pure-Python implementations of NIST post-quantum standards paired with `cryptography` AEAD:
* **Key Encapsulation (ML-KEM / FIPS 203):** [Kyber-KEM](https://github.com/tomciolowsky/Kyber-KEM) (`ML_KEM_768` default)
* **Digital Signatures (ML-DSA / FIPS 204):** [Dilithium-DSA](https://github.com/tomciolowsky/Dilithium-DSA) (`ML_DSA_65` default)
* **Symmetric Authenticated Encryption:** AES-256-GCM via `pyca/cryptography` with `kem_ciphertext + nonce` AAD


> **Security Notice:** This implementation is written for educational, research, and prototyping purposes. QSM demonstrates Zero-Knowledge post-quantum message relaying, but the underlying `Kyber-KEM` and `Dilithium-DSA` libraries are pure Python and **not constant-time**, and API user routing uses a lightweight `X-Username-Header` header rather than full session/token authentication.

## Tech Stack

* **Backend:** Async FastAPI, Pydantic v2, Uvicorn
* **Database:** Async SQLAlchemy 2.0 (`AsyncSession` with `psycopg` for PostgreSQL 16 and `aiosqlite` for local development/tests)
* **DevOps & Quality:** Docker Compose, GitHub Actions CI, `uv`, `pytest`, `ruff`

## REST API Overview

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `POST` | `/users/register` | Register a new user and store their ML-KEM and ML-DSA public keys |
| `GET` | `/users/{username}/keys` | Fetch a user's public keys for encryption & signature verification |
| `POST` | `/messages/send` | Queue an encrypted and signed message package for a recipient |
| `GET` | `/messages/inbox` | Retrieve inbox messages (`status`: `PENDING` default, `DELIVERED`, or `READ`; supports `limit` and `offset`) |
| `POST` | `/messages/{message_id}/acknowledge` | Acknowledge a `DELIVERED` message, updating its status to `READ` |
| `GET` | `/health/info` | Service metadata and supported cryptographic standards |
| `GET` | `/health/benchmark` | Run a live threadpool-offloaded benchmark of hybrid crypto operations |

Interactive Swagger UI docs are available at `http://127.0.0.1:8000/docs` while running the server.

## Installation & Running

### Using Docker Compose

Copy `.env.example` to `.env` if you want to customize database credentials, then start the API and PostgreSQL:

```bash
cp .env.example .env  # optional
docker compose up --build
```

### Using `uv`

Requires [`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/tomciolowsky/Quantum-Safe-Messenger.git
cd Quantum-Safe-Messenger

# Install runtime and development dependencies in editable mode
uv sync --all-groups

# Start the async FastAPI relay (uses local sqlite+aiosqlite by default)
uv run uvicorn qsm.api.main:app --reload
```

## CLI Demonstration

With the API server running, execute the end-to-end Alice & Bob demo in another terminal:

```bash
uv run python examples/alice_and_bob_cli_demo.py
```

## Testing & Linting

```bash
uv run pytest -v
uv run ruff check .
```

## License

MIT License — see [LICENSE](LICENSE) for details.