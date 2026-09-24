# Provider Duplicate Observation Collapse

P21 collapses duplicate provider observations by canonical provenance reference before constructing evidence claims.

Contract:
- deduplication happens after provenance canonicalization, field bounds and identity consistency checks;
- the first valid observation for a canonical provenance reference wins deterministically;
- subsequent observations with the same canonical reference are discarded from claim construction;
- source references and claims therefore remain one-to-one for accepted observations;
- no network access, retry, billing, persistence or kernel semantic is introduced.
