# Shema — External Intelligence & Contact System

## 1. Purpose

This document defines the mature external contour of Shema:

SEARCH → RESOLUTION → RESEARCH → EVIDENCE → QUALIFICATION → CONTACT PREPARATION → DOCUMENT PACK → ACTION → RESULT → LEARNING

The external contour is treated as a reliability boundary of information quality.

The internal core protects canonical business truth.
The external contour must protect the quality, provenance, freshness, interpretation and usability of acquired information.

The system is personal-first, but architected so that the same evidence, workflows and contracts remain usable when team mode is introduced.

## 2. Primary design principle

**Do not maximise data volume. Maximise decision-quality per unit of operator attention, time and external cost.**

The system must prefer:
- fewer verified facts over many weak signals;
- explicit uncertainty over false certainty;
- corroborated claims over single-source assertions when the claim is material;
- deterministic identifiers before fuzzy matching;
- fresh evidence before stale evidence;
- a compact operator brief with expandable evidence rather than a wall of raw data.

## 3. Research pipeline

### Stage 0 — Target definition

Before search, construct a bounded target profile:
- target type;
- geography;
- industry/service fit;
- size/operational indicators;
- known identifiers;
- desired decision;
- required evidence;
- maximum time/cost budget.

A search without a defined target is not treated as a high-quality research operation.

### Stage 1 — Recall / discovery

Objective: find a broad candidate set at low cost.

Use:
- official/public registries;
- business sites;
- structured datasets;
- search engines/indexes;
- public procurement/events/directories where relevant;
- intelligence datasets.

The recall phase intentionally tolerates false positives.

Results are observations, not clients.

### Stage 2 — Identity resolution

Resolution is separate from search relevance.

Process:
1. normalize;
2. exact identifier lookup where available;
3. generate candidate matches;
4. compare identifiers and supporting attributes;
5. detect contradictions;
6. classify:
   - MATCH;
   - MERGE;
   - KEEP_SEPARATE;
   - POSSIBLY_SAME;
   - QUARANTINE;
   - MANUAL_REVIEW.

Use a blocking → matching → clustering → splitting pattern for scale, while keeping ambiguous matches separate from canonical identities.

This follows the mature pattern documented by Sayari, while OpenSanctions demonstrates the additional value of identifier-aware matching and explicit thresholds for reducing false positives.

### Stage 3 — Evidence collection

For each material claim capture:
- claim;
- source;
- source type;
- source reliability;
- observed_at;
- captured_at;
- freshness/expiry;
- supporting identifiers;
- confidence;
- contradiction state;
- provenance URL/reference.

Do not collapse source reliability and claim confidence into one opaque score.

A trusted source can still contain a wrong or outdated fact; an unusual source can contain a correct observation. OpenCTI explicitly distinguishes source reliability from information confidence, and FollowTheMoney supports statement-level provenance and temporal metadata.

### Stage 4 — Corroboration / contradiction analysis

For material claims classify:

- confirmed by authoritative source;
- corroborated by independent sources;
- single-source;
- conflicting;
- stale;
- not found;
- explicitly disproven.

Rules:
- absence of evidence is never silently converted to evidence of absence;
- conflicting evidence blocks automatic promotion for critical claims;
- the system shows the conflict instead of averaging it away;
- every derived conclusion links to the claims from which it was derived.

### Stage 5 — Deep research

Only candidates that survive resolution and initial quality gates receive deeper research.

R1 — basic verification  
R2 — extended counterparty check  
R3 — deep intelligence  
R4 — special investigation

Each mode has:
- allowed source classes;
- mandatory checks;
- time budget;
- provider-call budget;
- stopping conditions;
- escalation rules.

A deeper mode must not simply collect more documents; it must answer a more specific decision question.

### Stage 6 — Relationship / graph pivots

For high-value or ambiguous cases, pivot through:
- owners/beneficial ownership where lawfully available;
- directors/managers;
- addresses;
- domains;
- phones/emails where lawfully available;
- related companies;
- contracts/procurement;
- licenses;
- public events;
- legal/public records;
- offshore/network datasets where relevant and lawful.

Graph relationships are evidence-bearing links, not canonical truth by themselves.

Aleph and ICIJ demonstrate the value of cross-dataset entity relationships, timelines and graph exploration for investigative work.

### Stage 7 — Qualification

Qualification consumes evidence. It must not manufacture it.

Minimum dimensions:
- identity;
- service fit;
- geography;
- operational fit;
- likely need;
- contactability;
- economic fit;
- reputation/risk;
- freshness;
- evidence sufficiency.

Output:
- qualified;
- conditionally qualified;
- needs research;
- unsuitable;
- quarantined.

### Stage 8 — Operator intelligence brief

The operator should receive:

**Who → Why relevant → What is verified → What is inferred → What changed → What risk/uncertainty exists → What to say → What not to say → What document pack applies → Next action**

The default view is compact.
Evidence, sources, raw observations and technical diagnostics remain one level deeper.

### Stage 9 — Contact preparation

Before the first contact, the system prepares an evidence-grounded contact plan:

1. identify the likely decision-maker/role from public lawful sources;
2. determine the relevant business context;
3. identify the evidence-backed reason for contact;
4. formulate the customer-specific value hypothesis;
5. choose the appropriate channel;
6. construct a short opening;
7. prepare qualifying questions;
8. prepare likely objections and safe responses;
9. define the desired next step;
10. list claims that must not be made because evidence is insufficient.

The system must never invent a personal detail, role, need or relationship merely to make a script sound personalised.

### Stage 10 — First-contact script

Script structure:

**Context → relevance → specific evidence-backed observation → service hypothesis → short question → value proposition → next step**

Optional branches:
- no decision-maker reached;
- gatekeeper;
- interested;
- not now;
- wrong person;
- asks for price;
- asks for documents;
- asks for credentials/requisites;
- asks for proof of capability.

The script is generated from the current dossier snapshot and must retain the evidence version used to construct it.

### Stage 11 — Document & legal configuration

Document preparation is a separate contract-driven subsystem.

Configuration dimensions:
- customer legal form;
- contractor legal form;
- tax regime;
- VAT applicability/status where relevant;
- service/work type;
- payment model;
- acceptance model;
- electronic-signature/EDO method;
- required supporting documents;
- effective legal-rule version/date.

The system must support combinations such as:
- ООО → ООО;
- ООО → ИП;
- ООО → ИП на НПД;
- ООО → физлицо-плательщик НПД;
- ИП → ООО;
- ИП → ИП;
- ИП → ИП на НПД;
- ИП → физлицо-плательщик НПД;
- and reverse directions where legally and operationally applicable.

The exact document set is selected from the current legal/configuration matrix, not from a fixed static bundle.

### Stage 12 — Document pack

Depending on the configuration, the operator may select or the system may recommend:
- commercial offer;
- cover/introductory letter;
- service agreement;
- contract for work;
- application/order;
- specification;
- statement of work / technical assignment;
- act of completed work/services;
- invoice/account where applicable;
- universal transfer document where applicable;
- required supporting documents;
- NPD status verification;
- NPD receipt/check control;
- EDO/e-signature instructions;
- completion/photo/report attachment where operationally required.

The system must distinguish:
- mandatory;
- conditionally required;
- recommended;
- optional;
- not applicable.

It must never present a legal document as universally valid for every transaction configuration.

### Stage 13 — Legal source control

Every generated legal template must have:
- template ID;
- version;
- effective-from date;
- affected configuration matrix;
- legal source references;
- last legal review date;
- change reason;
- generation snapshot;
- checksum/version identity.

Legal changes must invalidate or revalidate affected templates.

The system is a controlled document-construction tool, not an autonomous legal authority.

### Stage 14 — Manual counterparty check

The operator must have a dedicated manual check action:

**Check counterparty by INN / OGRN / OGRNIP**

The same intelligence pipeline is used, but the entry point is deterministic.

For Russian counterparties the check should start from official FNS sources, including the "Transparent Business" service, which provides access to current EGRUL/EGRIP-related information and supports search by INN/OGRN/name or OGRNIP/INN/FIO. FNS also emphasizes that separate indicators should be considered together rather than treated as a standalone proof of reliability.

For an NPD counterparty, the system should additionally support date-specific status verification by INN through the official FNS NPD status service. FNS explicitly identifies this check as relevant before entering contracts and states that the generated NPD receipt is the key document supporting the customer's expense for an NPD transaction.

Manual check output:
- identity;
- registration;
- tax/regime signals where publicly available;
- registration/status changes;
- evidence;
- conflicts;
- risk flags;
- freshness;
- recommended next verification;
- downloadable verification report.

## 4. Source hierarchy

Source priority is contextual, not one permanent universal ranking.

For a specific claim, prefer the source closest to the underlying fact:
1. official registry/issuer;
2. primary company source;
3. authoritative public record;
4. trusted structured dataset;
5. reputable secondary source;
6. open-web signal;
7. unverified signal.

The system records the source class rather than replacing provenance with a global score.

Examples:
- legal status → registry/official source;
- service offering → company primary source plus independent corroboration where material;
- event/need → dated primary/public event evidence;
- ownership network → official records where available, then structured investigative datasets;
- reputation signal → source-attributed evidence, never an unqualified system verdict.

ICIJ explicitly warns that its Offshore Leaks data is a partial investigative dataset, can contain duplicates, covers defined time ranges and should not by itself be treated as a complete account of a business. The system should model such limitations instead of hiding them.

## 5. Quality model

Do not create a single opaque "reliability score".

Maintain separate dimensions:
- source reliability;
- entity-match confidence;
- claim confidence;
- freshness;
- corroboration count/quality;
- contradiction severity;
- evidence completeness;
- qualification confidence.

A derived readiness state is allowed, but every state must remain explainable from these dimensions.

## 6. Anti-hallucination / anti-overreach rules

The research engine must distinguish:
- OBSERVED;
- VERIFIED;
- CORROBORATED;
- INFERRED;
- HYPOTHESIS;
- NOT_FOUND;
- CONFLICTING;
- EXPIRED.

AI may summarize and propose hypotheses, but cannot silently upgrade:
- hypothesis → fact;
- search relevance → identity;
- source mention → legal conclusion;
- stale fact → current fact;
- possible match → canonical identity.

## 7. Search efficiency / anti-overengineering balance

The default strategy is:

**broad cheap discovery → deterministic resolution → selective deep research → evidence synthesis → contact preparation**

Do not perform R3/R4 research on every candidate.

Deep research is triggered by:
- high commercial value;
- high uncertainty;
- material risk;
- conflicting evidence;
- decision-maker ambiguity;
- unusual ownership/network structure;
- request from operator.

Stop deep research when:
- required decision evidence is complete;
- remaining uncertainty cannot materially change the decision;
- budget/time boundary is reached;
- authoritative evidence is exhausted;
- further research would be redundant.

## 8. Quality metrics

The external contour measures:
- candidate recall;
- duplicate rate;
- identity resolution precision/recall where measurable;
- false-positive rate;
- evidence coverage;
- contradiction rate;
- stale-data rate;
- source freshness;
- contactability rate;
- qualified-candidate yield;
- useful-first-contact rate;
- contact-to-next-step rate;
- document-pack correctness;
- research cost/time per qualified candidate;
- operator correction rate.

Metrics are for improving the system, not for manufacturing a single "AI intelligence score".

## 9. Security / privacy / lawful-access boundary

Only lawful and operationally permitted sources may be used.

For person-related information:
- purpose limitation;
- data minimization;
- provenance;
- access control;
- retention/expiry;
- audit;
- secure handling.

Russian personal-data rules require lawful and purpose-limited processing; the current 152-FZ version expressly defines these principles and includes rules for public personal-data sources.

No scraping, access or collection method is allowed merely because it is technically possible.

## 10. Reliability doctrine

The external contour follows the same philosophy as the core:

**prevent → detect → contain → explain → recover → revalidate → learn**

Internal core:
- protects transaction truth.

External intelligence:
- protects information truth.

Neither side may bypass the other.

## 11. Completion boundary

The Search & Intelligence System is mature only when:
- search is reproducible and bounded;
- identity resolution is explainable;
- material claims retain provenance;
- source reliability and claim confidence are distinct;
- contradiction handling is explicit;
- freshness/revalidation is enforced;
- graph pivots are available for deep cases;
- qualification consumes evidence;
- contact preparation is evidence-grounded;
- legal document packs are configuration-driven and versioned;
- manual INN/OGRN/OGRNIP verification uses the same intelligence path;
- operator can inspect why a result was produced;
- critical failures are recoverable;
- quality and operator-effort metrics are measured.

## 12. External contour principle

The best system is not the one that finds the most information.

It is the one that most reliably answers:

**Who is this?  
What do we actually know?  
How do we know it?  
How fresh is it?  
What contradicts it?  
Why does it matter?  
Who should we contact?  
What should we say?  
What must we avoid claiming?  
Which legal/document configuration applies?  
What is the safest next action?**


## 13. External research basis

Primary reference classes used to shape this boundary:
- OCCRP Aleph — open-source investigative data platform, cross-referencing, investigations, timelines and graph exploration:
  https://docs.aleph.occrp.org/
- OpenSanctions — entity matching, candidate retrieval, identifier-aware scoring and dataset scoping:
  https://www.opensanctions.org/docs/api/
- Sayari — entity resolution, blocking/matching, identity vs possibly-same-as resolution:
  https://documentation.sayari.com/sayari-library/entity-resolution/entity-resolution
- FollowTheMoney — statement-level provenance and structured entity/relationship model:
  https://followthemoney.tech/docs/
- OpenCTI — source reliability and information confidence as separate concepts:
  https://docs.opencti.io/latest/usage/reliability-confidence/
- ICIJ Offshore Leaks — graph-based investigative data with explicit dataset/time-scope limitations:
  https://offshoreleaks.icij.org/
- FNS Transparent Business — Russian legal-entity/counterparty information:
  https://pb.nalog.ru/
- FNS NPD status service:
  https://npd.nalog.ru/check-status/
