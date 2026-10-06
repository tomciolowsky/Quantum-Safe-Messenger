# Quantum-Safe-Messenger

![CI Pipeline](https://github.com/tomciolowsky/Quantum-Safe-Messenger/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.14-blue.svg?logo=python&logoColor=white
)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9.svg?logo=uv)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-teal.svg?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg?logo=docker)
![Standards](https://img.shields.io/badge/NIST-FIPS%20203%20%7C%20FIPS%20204-green.svg)

My own **End-to-End Encrypted (E2EE) Messaging Relay** built with Post-Quantum Cryptography standards. The system secures asymmetric communication even in case of future quantum computer attacks using **lattice-based cryptography**. Designed around a **Zero-Knowledge** model: the server is never accessing plaintext messages or private keys.

## How it works?

1. **Client Setup:** Users generate post-quantum key pairs locally and register their public keys (KEM & DSA) on the server.
2. **Key Discovery:** Senders query the relay to retrieve the recipient's public keys.
3. **Encryption (Sender):**
   * Derives a 256-bit _symmetric key_ and _ciphertext_ using **ML-KEM**.
   * Encrypts the _message_ using the _symmetric key_ and random _nonce_ with **AES-256-GCM**.
   * Signs the entire package (_ciphertext_ + _nonce_ + _encrypted message_) using **ML-DSA**.
4. **Zero-Knowledge Relay:** The server stores and queues encrypted packages in **PostgreSQL** as meaningless upper-hex encoded bytes.
5. **Decryption (Recipient):** 
    * Pulls pending packages and queries the relay to retrieve sender's public keys
    * Verifies the digital _signature_ (DSA), retrieves _symmetric key_ (KEM), and decrypts the _message_ (AES) locally.
    * Sends message acknowledgement to the server

## Cryptographic Core

I built this project on top of `my own implementations` of the latest NIST standards in pure Python without external libraries:
* **Key Encapsulation (ML-KEM):** [Kyber-KEM](https://github.com/tomciolowsky/Kyber-KEM) (FIPS 203)
* **Digital Signatures (ML-DSA):** [Dilithium-DSA](https://github.com/tomciolowsky/Dilithium-DSA) (FIPS 204)

Additionaly I used AES cipher from `pyca/cryptography` module:
* **Symmetric Encryption:** AES-256-GCM

## Tech Stack

* **Backend:** FastAPI, Pydantic, Uvicorn
* **Database:** SQLAlchemy 2.0, PostgreSQL 16, SQLite (for local tests)
* **DevOps:** Docker, GitHub Actions (CI), `uv`, `pytest`, `ruff`

## REST API Overview

| Method | Endpoint                     | Description                                                 |
| :---:  | :---                         | :---                                                        |
| `POST` | `/users/register`            | Register a new user and their post-quantum public keys      |
| `GET`  | `/users/{username}/keys`     | Fetch user's public keys for encryption & verification      |
| `POST` | `/messages/send`             | Queue an encrypted and signed message to recipient's inbox  |
| `GET`  | `/messages/inbox`            | Retrieve pending messages from inbox for authenticated user |
| `POST` | `/messages/{id}/acknowledge` | Acknowledge message delivery (updates its status to READ)   |
| `GET`  | `/health/benchmark`          | Run a real-time performance benchmark of lattice operations |

Access the interactive API documentation (Swagger UI)

Available at: http://127.0.0.1:8000/docs when running the server:

## Installation

### Using Docker Compose:

Run the API and PostgreSQL database with a single command:

```bash
docker compose up --build
```

### Using uv:

Requires [uv](https://github.com/astral-sh/uv) package manager

```bash
# Clone the repository
git clone https://github.com/tomciolowsky/Quantum-Safe-Messenger.git
cd Quantum-Safe-Messenger

# Install dependencies and package in editable mode 
uv sync

# Start the API server
uv run uvicorn qsm.api.main:app --reload
```

## CLI Demonstration

To see the complete encryption, transmission and decryption between two sides in action, run the demo:

```bash
uv run python examples/alice_and_bob_cli_demo.py
```

## Testing and Code linting

I used `pytest` for unit testing of the cryptography layer, relational database models and the API integration:

```bash
# Run tests
uv run pytest -v
```

I used `ruff` for code linting and quality checks:
```bash
# Run linter
uv run ruff check .
```