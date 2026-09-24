# Provider Provenance Canonicalization

P18 converts accepted OpenCorporates provenance references into one deterministic URL representation before evidence construction.

Contract:
- only provenance references already passing the host and path integrity checks are eligible;
- explicit non-default ports are rejected;
- an optional trailing slash is normalized away;
- query strings and fragments remain forbidden;
- the canonical representation is exactly `https://opencorporates.com/companies/{jurisdiction}/{company_number}`;
- no network access is performed;
- duplicate references collapse naturally through existing source-reference deduplication;
- canonicalization does not make the external reference canonical business truth.

This is a local evidence-integrity normalization only.
