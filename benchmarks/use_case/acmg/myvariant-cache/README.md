# Recorded MyVariant.info responses (2026-09-28)

These are the 21 responses MyVariant.info returned to the `rsid-myvariant` linker for arm 1's two PGP
files: 10 for NB72462M and 11 for NG131FQA1I. The paper's MyVariant.info result rests on them.

**To reproduce that result, use these responses, not the live service.** The `link_myvariant` stage of
[`17_use_case_acmg.sh`](../../../17_use_case_acmg.sh) reads them by default, with the linker's
`--offline`, and sends no request. MyVariant.info's data change as dbSNP and its other sources are
updated. A live query (`BM_ALLOW_NETWORK=1`) therefore answers a different question, whether today's
service confirms the rsIDs, and its counts can differ from the paper's.

## What is here

The layout is the linker's cache (`--links-cache`): `responses/rsid-myvariant/1.0.0/<request>.json`.
`<request>` is the SHA-256 of the request's method, URL, and JSON body, a batch of up to 1,000 rsIDs, so
the linker finds a response by the request it would send. Each file holds the response as served:
- its status and headers;
- the body, base64-encoded, and the body's SHA-256;
- when it was fetched.

The linker refuses a file whose body does not match its SHA-256. Request headers, including the contact
address the linker sends, are not stored.

Each body is MyVariant.info's batch-query result for the field `dbsnp.rsid`. Per queried rsID, it gives
either the matching variant's HGVS identifier, a score, and the dbSNP rsID with the `_license` link the
service attaches, or `notfound`.

## Provenance

- **Fetched** on 2026-09-28 from `https://myvariant.info/v1/query`, on vcf-bench-1. A pre-release
  VCF-RDFizer tree's `rsid-myvariant` linker made the requests, the only time this study queried the
  service.
- **Same requests in v3.3.1.** That linker's manifest (`linker.ttl`, SHA-256 `97febb24…`) and resolver
  (`resolver.py`, `23a81743…`) are byte-identical to VCF-RDFizer v3.3.1's. v3.3.1 therefore builds the
  same requests from the same derived VCFs.
- **Replayed by the reported run.** The v3.3.1 run the paper reports replayed these files:
  [`BioMedSem_2026/benchmark-results/vcf-bench-1/v331-rerun/`](../../../../BioMedSem_2026/benchmark-results/vcf-bench-1/v331-rerun/).
  - Its `inputs.bench1-myvariant.sha256` holds each file's SHA-256.
  - Each `link_myvariant__*/out/*.links.json` lists the responses it used, by request and body SHA-256.

## Licence and credit

These files are not covered by this repository's licences (MIT for code, CC BY 4.0 for data). They are
MyVariant.info's responses, reproduced unmodified so the result can be reproduced, under
[MyVariant.info's terms of use](https://myvariant.info/terms/) and the licences of the sources it
aggregates. Each record keeps the `_license` link the service attached. The identifiers come from NCBI's
dbSNP.

Cite MyVariant.info as: Xin J, Mark A, Afrasiabi C, et al. High-performance web services for querying
gene and variant annotation. *Genome Biology* 17, 91 (2016).
[doi:10.1186/s13059-016-0953-9](https://doi.org/10.1186/s13059-016-0953-9)
