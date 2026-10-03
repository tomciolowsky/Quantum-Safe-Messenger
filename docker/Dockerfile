FROM python:3.14-slim

# By default docker containers run as root.
# Create a non-root user with specific UID and GID.
# "Principle of least privilege"
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install git
RUN apt-get update && \
    apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory to /app
WORKDIR /app

# Pythons stdout and stderr are buffered by default.
# With this flag, logs are sent straight to terminal
ENV PYTHONUNBUFFERED=1

# UV optimizations
# Compile bytecode .py to .pyc to speed up containers startup.
# Copy dependencies instead of symlinking them to speed up.
# Do not install dev dependencies to reduce image size.
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1

# Install dependencies first - better chache behavior.
COPY --chown=nonroot:nonroot pyproject.toml uv.lock* ./
RUN uv sync --locked --no-install-project

# Install the project files
COPY --chown=nonroot:nonroot README.md ./
COPY --chown=nonroot:nonroot src/ ./src/
RUN uv sync --locked

# set the PATH 
ENV PATH="/app/.venv/bin:$PATH"

# Set the entrypoint (main program script) to an empty array.
ENTRYPOINT []

# Switch to the non-root user
USER nonroot

# Expose the port that the application will run on
EXPOSE 8000

# Run the app 'uvicorn qsm.api.main:app' with host 0.0.0.0 and port 8000
CMD ["uvicorn", "qsm.api.main:app", "--host", "0.0.0.0", "--port", "8000"]