# BioInterchange 2.0.5 (commit 49d57012). Upstream published no binary or image, and its source
# build no longer works: CMakeLists.txt clones github.com/indiedotkim/LibDocument, which is gone.
# The one remaining binary is the Linux bottle of the brewsci/bio Homebrew formula (removed from the
# tap on 2025-10-25), still served by GHCR and addressed by its own SHA-256. It was built against
# Python 3.9 and OpenSSL 1.1, so the base is Debian bullseye, with packages from the snapshot
# archive. The JSON-LD contexts the output names now return 404, so the context file is taken from
# the pinned commit and inlined by bi_jsonld_to_nquads.py.
#
# The tool exits when its user has no passwd entry, so the image adds one for the calling UID.
ARG CONV_BI_BASE_IMAGE
FROM ${CONV_BI_BASE_IMAGE}
ARG CONV_DEBIAN_SNAPSHOT
ARG CONV_BI_COMMIT
ARG CONV_BI_BOTTLE_SHA256
ARG CONV_BI_CONTEXT_SHA256
ARG CONV_UID=1000
RUN set -eux; \
    rm -f /etc/apt/sources.list /etc/apt/sources.list.d/*; \
    printf '%s\n' \
      "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${CONV_DEBIAN_SNAPSHOT} bullseye main" \
      "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/${CONV_DEBIAN_SNAPSHOT} bullseye-security main" \
      > /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends libpython3.9 libssl1.1 python3 python3-pyld patchelf curl ca-certificates; \
    token="$(curl -fsS 'https://ghcr.io/token?scope=repository:brewsci/bio/biointerchange:pull' \
      | python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')"; \
    curl -fsSL -H "Authorization: Bearer ${token}" -o /tmp/bottle.tar.gz \
      "https://ghcr.io/v2/brewsci/bio/biointerchange/blobs/sha256:${CONV_BI_BOTTLE_SHA256}"; \
    echo "${CONV_BI_BOTTLE_SHA256}  /tmp/bottle.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/bottle /opt/biointerchange; \
    tar -xzf /tmp/bottle.tar.gz -C /opt/bottle; \
    install -m0755 "$(find /opt/bottle -path '*/bin/biointerchange' -type f)" /usr/local/bin/biointerchange; \
    patchelf --set-interpreter /lib64/ld-linux-x86-64.so.2 --remove-rpath /usr/local/bin/biointerchange; \
    ldd /usr/local/bin/biointerchange | tee /opt/biointerchange/ldd.txt; \
    ! grep -q 'not found' /opt/biointerchange/ldd.txt; \
    curl -fsSL -o /opt/biointerchange/vcf-f1.json \
      "https://raw.githubusercontent.com/BioInterchange/BioInterchangeC/${CONV_BI_COMMIT}/context/vcf-f1.json"; \
    echo "${CONV_BI_CONTEXT_SHA256}  /opt/biointerchange/vcf-f1.json" | sha256sum -c -; \
    useradd --uid "${CONV_UID}" --no-create-home --shell /usr/sbin/nologin conv; \
    apt-get purge -y curl patchelf; apt-get autoremove -y; rm -rf /var/lib/apt/lists/* /tmp/bottle.tar.gz; \
    biointerchange -v
