# Experiment 18 summary

| Converter | Input | Wall (s, median) | Peak RSS (GB) | Byte-identical replicates | Triples | Triples/record | N-Triples.gz ÷ VCF.gz | QLever index (s) | riot warnings | Q01 | Q02 | Q03 | Q04 | Q05 | Q06 | Q07 | Q08 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| biointerchange | 1000G_10000r_s16 | 0.4 | 0.01 | no | 2,031,215 | 203.1 | 154.3 | 3.2 | 0 | pass | pass | pass | pass | pass | pass | pass | pass |
| biointerchange | HG005_GRCh38_r100000 | 1.5 | 0.02 | no | 4,559,438 | 45.6 | 17.0 | 6.6 | 0 | pass | pass | pass | pass | pass | pass | differs | differs |
| jvarkit | 1000G_10000r_s16 | 1.4 | 0.30 | yes | 1,020,454 | 102.0 | 18.2 | 1.4 | 510,177 (Bad IRI: <…> Bad character in Namespace id (510,177)) | differs | differs | differs | differs | differs | differs | not in graph | not in graph |
| jvarkit | HG005_GRCh38_r100000 | 2.2 | 0.43 | yes | 1,401,613 | 14.0 | 2.1 | 1.8 | 601,008 (Bad IRI: <…> Bad character in Namespace id (601,008)) | pass | pass | pass | pass | pass | pass | not in graph | not in graph |
| sparqling-genomics | 1000G_10000r_s16 | 0.4 | 0.01 | yes | 180,053 | 18.0 | 4.1 | 0.5 | 189,130 (Unwise IRI: <…> Use of user info is deprecated (189,130)) | differs | differs | differs | differs | differs | differs | pass | pass |
| sparqling-genomics | HG005_GRCh38_r100000 | 6.3 | 0.01 | yes | 2,958,769 | 29.6 | 4.8 | 3.3 | 3,057,819 (Unwise IRI: <…> Use of user info is deprecated (3,057,819)) | pass | pass | pass | pass | pass | pass | pass | differs |
| togovar | 1000G_10000r_s16 | 0.1 | 0.01 | yes | 564,940 | 56.5 | 35.0 | 1.0 | 0 | differs | differs | differs | differs | not in graph | not in graph | not in graph | not in graph |
| togovar | HG005_GRCh38_r100000 | 1.3 | 0.01 | yes | 5,728,120 | 57.3 | 15.4 | 6.8 | 0 | pass | differs | differs | pass | not in graph | not in graph | not in graph | not in graph |
| vcf-rdfizer | 1000G_10000r_s16 | 31.4 | 0.93 | no | 5,359,578 | 536.0 | 136.9 | 7.0 | 7,252,206 (Unwise IRI: <…> file: URLs are of the form file:///path/..., not file://path (7,252,206)) | pass | pass | pass | pass | pass | pass | pass | pass |
| vcf-rdfizer | HG005_GRCh38_r100000 | 91.6 | 1.85 | no | 17,098,746 | 171.0 | 25.5 | 20.8 | 23,616,118 (Unwise IRI: <…> file: URLs are of the form file:///path/..., not file://path (23,616,118)) | pass | pass | pass | pass | pass | pass | pass | pass |
