

The main issue remaining for me is the positioning. 

The paper is at its strongest when it is about **a verifiable semantic transformation of VCF data, with source-based checks, structural validation, fault injection, a realistic linked-data use case, and a clear assessment of the computational trade-offs**. That is already a solid contribution. It is not a product or a clinical workflow (yet), I would therefore *be careful not to oversell* the clinical reanalysis, PGx and governance aspects as if these are fully demonstrated applications. 

They are good motivating scenarios, but the *current experiments do not validate them end-to-end*. Related to this, I would also reconsider “governable” in the title. 

- [x] “Policy-aware” or similar would be better consistent with what we actually test. Governable had different connotations in the regulatory world. This is not to annoy potential bioinformatics/clinical workflow background expertise reviewers if we will get any.

The second important point is reproducibility and what exactly we mean by “verified”. 

- [x] We should make sure the exact evaluated code, configurations, versions and any (*dirty-tree*) changes are frozen and archived with a persistent identifier, and remove the remaining author queries.
- [ ] (doing this currently and will include a zenodo DOI and a "versions used to assessment" statement)

- [ ] I would also write down more explicitly what the validation establishes: *agreement with source-derived queries, structural conformance (via SHACL correct ?), and preservation across serialization*. 

This is strong validation, but it is not full value-by-value semantic equivalence, so being precise here will actually strengthen the paper rather than make it appear weak in my opinion. This is I usually appreciate when I review papers, where authors dont claim full validation but explicitly state what they mean by it.

- [x] Finally, I would suggest to look once more at the comparison with existing VCF-to-RDF tools. At the moment this is mainly documentation-based, this is certainly acceptable if we clearly present it that way, but
- [x] one direct comparison with the closest usable alternative on a common input would substantially strengthen the novelty argument. I am guessing we might judge this is too much to add now, then I would simply tone down any implication that we have experimentally demonstrated superiority over the other converters.
- [ ] The same applies to the large-scale performance results: where we only have single full-WGS runs, in that instance we might consider either replicate the key measurements or keep our conclusions qualitative. (clarify this)

The rest is mostly tightening: 
- [ ] clearly distinguish expected rejection of malformed input from unsupported valid VCF cases,
- [ ] make the independence of the RDF and conventional comparison workflows a bit more east to grasp, and
- [ ] cleaning up the remaining author queries/formatting issues etc.
- [ ] I also would not hide the scalability limitations — actually *I think the finding that RDF might not be the right solution for every workload is one of the more credible and useful aspects of the paper*.

So in short, I would avoid expanding the scope further as the paper already has a strong core; the main job remined in the coming few days now is to sharpen that core and make sure we claim exactly what we have demonstrated.