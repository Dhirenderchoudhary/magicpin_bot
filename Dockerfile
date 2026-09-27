# Dockerfile
FROM python:3.11-slim

# Set a non‑root user for security
ARG UID=1000
ARG GID=1000
RUN addgroup --gid $GID appgroup && \
    adduser --uid $UID --gid $GID --disabled-password --gecos "" appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src ./src
COPY generate_submission.py .
COPY README.md .

# Use non‑root user
USER appuser

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
