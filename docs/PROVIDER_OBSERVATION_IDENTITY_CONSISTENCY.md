# Provider Observation Identity Consistency

P20 requires the provider payload identity to agree with the accepted provenance path before a claim is constructed.

Rule:
- `jurisdiction_code` must equal the jurisdiction segment of the canonical OpenCorporates provenance URL;
- `company_number` must equal the company-number segment;
- mismatches discard only the affected observation;
- no normalization or fuzzy matching is performed;
- no network access or canonical business-state write is introduced.

This is an evidence-integrity consistency check, not a claim about authoritative business truth.
