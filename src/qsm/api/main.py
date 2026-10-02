from contextlib import asynccontextmanager
from fastapi import FastAPI

from qsm.storage import init_db
from qsm.api.routes import authorization_router, messages_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize the database when the application starts.
    """
    init_db()
    yield


app = FastAPI(
    title="Quantum Safe Messenger API",
    description="End-to-end encrypted messaging service using post-quantum cryptography: NIST FIPS 203 (ML-KEM) and NIST FIPS 204 (ML-DSA).",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(authorization_router)
app.include_router(health_router)
app.include_router(messages_router)