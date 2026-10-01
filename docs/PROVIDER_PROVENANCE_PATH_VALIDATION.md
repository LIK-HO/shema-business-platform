# Provider Provenance Path Validation

P17 constrains OpenCorporates provenance references to the documented company-reference path shape.

Purpose:
- prevent a valid OpenCorporates host from being treated as sufficient provenance when the path points elsewhere;
- reject extra path segments, query/fragment variants and incomplete company references;
- keep the check local and deterministic without following the URL.

Contract:
- scheme must be HTTPS;
- host must be exactly `opencorporates.com`;
- query and fragment must be absent;
- normalized path must have the form `/companies/{jurisdiction}/{company_number}`, with an optional trailing slash;
- invalid path references discard only the affected observation;
- no network fetch or canonical-state write is introduced.
