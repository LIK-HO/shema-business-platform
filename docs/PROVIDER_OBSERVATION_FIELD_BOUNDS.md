# Provider Observation Field Bounds

P19 bounds provider observation fields before evidence claim construction.

Operational bounds:
- company name: 512 characters maximum;
- jurisdiction code: 32 characters maximum;
- company number: 128 characters maximum;
- current status: 64 characters maximum;
- non-string identity/status fields are rejected for that observation rather than stringified.

The limits are platform resource/integrity controls, not claims about an OpenCorporates upstream hard limit.

Invalid observations are discarded locally. No retry, network access, canonical business-state write or kernel semantic is introduced.
