# Apache Jena riot. Streams each converter's native output (RDF/XML, Turtle, JSON-LD) to N-Triples,
# so every graph is counted, sized, and indexed the same way. Build arguments come from pins.env.
ARG CONV_BASE_IMAGE
FROM ${CONV_BASE_IMAGE}
ARG CONV_DEBIAN_SNAPSHOT
ARG CONV_JENA_VERSION
ARG CONV_JENA_SHA512
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${CONV_DEBIAN_SNAPSHOT} trixie main" \
      > /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends openjdk-21-jre-headless time curl ca-certificates; \
    curl -fsSL -o /tmp/jena.tar.gz \
      "https://archive.apache.org/dist/jena/binaries/apache-jena-${CONV_JENA_VERSION}.tar.gz"; \
    echo "${CONV_JENA_SHA512}  /tmp/jena.tar.gz" | sha512sum -c -; \
    tar -xzf /tmp/jena.tar.gz -C /opt; \
    ln -s "/opt/apache-jena-${CONV_JENA_VERSION}" /opt/jena; \
    rm /tmp/jena.tar.gz; \
    apt-get purge -y curl; apt-get autoremove -y; rm -rf /var/lib/apt/lists/*
ENV PATH=/opt/jena/bin:$PATH
