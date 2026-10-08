# The runner: bash, python3, and the Docker CLI with Compose, so the driver needs nothing from the
# host but the Docker socket. busybox-static is the measuring binary that measure.sh mounts into
# every converter container. All packages come from the pinned Debian snapshot.
ARG CONV_BASE_IMAGE
FROM ${CONV_BASE_IMAGE}
ARG CONV_DEBIAN_SNAPSHOT
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${CONV_DEBIAN_SNAPSHOT} trixie main" \
      > /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      bash python3 python3-yaml coreutils gzip procps curl ca-certificates busybox-static \
      docker-cli docker-compose docker-buildx; \
    rm -rf /var/lib/apt/lists/*; \
    docker --version; docker compose version; busybox time -v true
