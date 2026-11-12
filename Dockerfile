# Yaqidh in one container: the API, the dashboard and the real scan tools (Playwright, Semgrep, Trivy).
#
#   docker build -t yaqidh .
#   docker run -p 8080:8080 -e YAQIDH_DEMO_PASSWORD=... -e YAQIDH_ALLOWED_HOSTS=your.domain.com yaqidh
#
# Semgrep's official rules are NOT put into the image by default: their licence (Semgrep Rules License v1.0) limits use
# to internal purposes and restricts offering them as a service. Without them, a Semgrep scan stops with a clear
# "rules not found" error. Build with --build-arg FETCH_SEMGREP_RULES=1 only once the licence question is settled.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUTF8=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TRIVY_CACHE_DIR=/data/trivy

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Trivy, pinned to the version the project was built and tested with.
ARG TRIVY_VERSION=0.76.2
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin v${TRIVY_VERSION}

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install . \
    && playwright install --with-deps chromium

COPY . .
ARG FETCH_SEMGREP_RULES=0
RUN if [ "$FETCH_SEMGREP_RULES" = "1" ]; then bash scripts/fetch_semgrep_rules.sh; fi \
    && chmod +x scripts/start_container.sh

# Everything the system writes (evidence, history, the Trivy database) lives in /data. Mount a volume there to keep it.
RUN useradd --create-home --shell /usr/sbin/nologin yaqidh \
    && mkdir -p /data \
    && chown -R yaqidh:yaqidh /app /data
USER yaqidh

EXPOSE 8080
CMD ["scripts/start_container.sh"]
