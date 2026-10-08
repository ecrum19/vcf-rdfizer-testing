# JVarkit vcf2rdf, built from a pinned commit. Upstream publishes no jar for it, and its own
# Dockerfile builds an older commit from another branch.
#
# Pinned by commit, not by tag: the v2026.04.30 tag was moved after its release was published.
# The Gradle wrapper does not pin its distribution, so its SHA-256 is added here. The build
# fetches its ~45 library jars from Maven Central at fixed versions but checks no checksums, so
# the SHA-256 of every jar it used is recorded in /opt/jvarkit/build-sha256.txt. The jar embeds a
# compile date, so cite this image's ID rather than the jar's hash.
ARG CONV_BASE_IMAGE
FROM ${CONV_BASE_IMAGE} AS build
ARG CONV_DEBIAN_SNAPSHOT
ARG CONV_JVARKIT_COMMIT
ARG CONV_GRADLE_SHA256
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${CONV_DEBIAN_SNAPSHOT} trixie main" \
      > /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends openjdk-21-jdk-headless git ca-certificates; \
    rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN set -eux; \
    git init -q .; \
    git remote add origin https://github.com/lindenb/jvarkit.git; \
    git fetch -q --depth 1 origin "${CONV_JVARKIT_COMMIT}"; \
    git checkout -q --detach FETCH_HEAD; \
    test "$(git rev-parse HEAD)" = "${CONV_JVARKIT_COMMIT}"; \
    echo "distributionSha256Sum=${CONV_GRADLE_SHA256}" >> gradle/wrapper/gradle-wrapper.properties; \
    ./gradlew --no-daemon -q -Djvarkit.generate.doc=false jvarkit; \
    { sha256sum dist/jvarkit.jar; \
      find . -name '*.jar' -not -path './.git/*' -not -path './dist/*' -print0 | sort -z | xargs -0 sha256sum; \
    } > build-sha256.txt

FROM ${CONV_BASE_IMAGE}
ARG CONV_DEBIAN_SNAPSHOT
ARG CONV_JVARKIT_COMMIT
RUN set -eux; \
    rm -f /etc/apt/sources.list.d/debian.sources; \
    echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${CONV_DEBIAN_SNAPSHOT} trixie main" \
      > /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends openjdk-21-jre-headless; \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /src/dist/jvarkit.jar /src/build-sha256.txt /opt/jvarkit/
RUN echo "${CONV_JVARKIT_COMMIT}" > /opt/jvarkit/COMMIT
