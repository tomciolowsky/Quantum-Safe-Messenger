import time

from fastapi import APIRouter, status
from fastapi.concurrency import run_in_threadpool

from qsm.api.schemas import BenchmarkResponseSchema, BenchmarkResultSchema
from qsm.crypto import HybridParty

router = APIRouter(
    prefix="/health",
    tags=["System and Diagnostics"],
)


def _execute_crypto_benchmark() -> list[BenchmarkResultSchema]:
    hybrid = HybridParty()
    benchmark_results: list[BenchmarkResultSchema] = []

    def benchmark_method(method_to_test, description: str, *args, **kwargs):
        time_0 = time.perf_counter()
        result = method_to_test(*args, **kwargs)
        time_1 = time.perf_counter()

        benchmark_results.append(
            BenchmarkResultSchema(
                algorithm="ML-KEM-768 + ML-DSA-65",
                operation=description,
                duration_ms=round((time_1 - time_0) * 1000, 2),
            )
        )
        return result

    keys = benchmark_method(hybrid.generate_keys, "Key Pair Generation (KEM + DSA)")
    package = benchmark_method(
        hybrid.encrypt_package,
        "Package Encryption (KEM encapsulation + AES encryption + DSA signing)",
        receiver_kem_pk=keys.kem.public_key,
        sender_dsa_sk=keys.dsa.secret_key,
        plaintext=b"Benchmarking the encryption operation.",
    )
    benchmark_method(
        hybrid.decrypt_package,
        "Package Decryption (KEM decapsulation + AES decryption + DSA verification)",
        receiver_kem_sk=keys.kem.secret_key,
        sender_dsa_pk=keys.dsa.public_key,
        package=package,
    )
    return benchmark_results


@router.get(
    "/info",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Basic health check of the system and a list of supported standards.",
)
async def health_check():
    """
    Endpoint to check the health of the system and retrieve supported standards.
    """
    return {
        "status": "healthy",
        "service": "Quantum-Safe Messenger API",
        "supported_standards": [
            "FIPS 203 (ML-KEM)",
            "FIPS 204 (ML-DSA)",
            "AES-256-GCM",
        ],
    }


@router.get(
    "/benchmark",
    response_model=BenchmarkResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Benchmark the cryptographic operations",
    description="Benchmarks the cryptographic operations used in the system and returns the time taken for each operation.",
)
async def run_benchmark():
    """
    Endpoint to benchmark the cryptographic operations used in the system.
    """
    results = await run_in_threadpool(_execute_crypto_benchmark)
    return BenchmarkResponseSchema(results=results)
