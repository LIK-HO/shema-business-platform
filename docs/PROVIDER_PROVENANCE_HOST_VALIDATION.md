# Provider Provenance Host Validation

P16 constrains materialized OpenCorporates provenance references to the expected HTTPS origin.

Purpose:
- prevent an arbitrary HTTPS origin from being accepted as OpenCorporates provenance;
- reject lookalike hosts and userinfo-based URL confusion;
- keep provenance validation at the concrete provider adapter boundary.

Contract:
- source references must parse as URLs with scheme `https`;
- the parsed hostname must be exactly `opencorporates.com`;
- invalid or lookalike provenance references discard only that observation;
- no network fetch or canonical-state write is performed as part of this validation;
- no kernel, retry scheduler, durable job, billing ledger, or deployment semantic is introduced.
