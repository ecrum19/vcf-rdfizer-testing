FROM node:22.19.0-bookworm-slim@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90

ARG COMUNICA_VERSION=5.3.0

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bcftools \
        python3 \
        python3-venv \
        raptor2-utils \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@comunica/query-sparql-file@${COMUNICA_VERSION}"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends time \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/vcf-query-test-requirements.txt
RUN python3 -m venv /opt/vcf-query-test-venv \
    && /opt/vcf-query-test-venv/bin/python -m pip install \
        --no-cache-dir \
        --requirement /tmp/vcf-query-test-requirements.txt

ENV PATH="/opt/vcf-query-test-venv/bin:${PATH}"

WORKDIR /workspace
ENTRYPOINT ["python3", "tests/test-queries/run_suite.py"]
