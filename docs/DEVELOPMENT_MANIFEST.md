# СХЕМА Business Platform — Development Manifest
## Формальный манифест зрелого ядра и рациональной разработки

**Status:** v1.5 Core Maturity Certified / Kernel Frozen  
**Current branch:** v1.5/core-maturity  
**Base:** v1.5-runtime  
**Current HEAD:** resolved live from GitHub at every development-session entry; never treated as a static manifest fact.  
**Current PR:** #8 — Core Maturity / Migration Safety / Recovery  
**Kernel baseline:** v1.4 frozen  
**Runtime baseline:** v1.5.0

---

## 1. Назначение

Этот документ является формальной точкой синхронизации разработки.

Он фиксирует:
1. что уже сделано в ядре;
2. на какой стадии мы находимся;
3. какие свойства обязательны для зрелого ядра;
4. какие проверки ещё необходимы;
5. где заканчивается развитие ядра и начинается продуктовый/интеграционный слой;
6. какие принципы считаются архитектурными инвариантами.

После прохождения финальной сертификации зрелости семантика ядра считается frozen. Новые возможности реализуются поверх неё через application workflows, adapters, integrations и experience/product layers.

Работа с GitHub не должна зависеть от памяти предыдущего диалога. Вход в каждый новый development session выполняется по `docs/GITHUB_WORK_PROTOCOL.md`, `docs/DEVELOPMENT_STATE.md` и `AGENTS.md`; текущий branch/HEAD/PR/CI всегда читаются заново из GitHub.

---

# 2. Формальный статус на 2026-09-23

Мы на стадии:

**v1.5 Core Maturity Certified — B10 Controlled Release Candidate / Final Semantic Freeze**

Это означает:
- v1.4 business/domain kernel сформирован и frozen;
- v1.5 runtime boundary сформирован;
- B2 unified v1.5 candidate прошёл полный CI/release verification;
- B3 безопасный adoption существующих v1.4 databases доказан executable integration proof;
- B4 crash-after-external-effect recovery доказан реальным commercial send integration proof;
- B5 physical backup/restore/PITR доказан реальным PostgreSQL 16 drill и измеренным RTO/RPO;
- B6 end-to-end observability correlation доказан реальным HTTP→workflow→audit→telemetry integration proof;
- B7 security certification matrix закрыт и подтверждён CI #1015;
- B8 SLO/error-budget baseline закрыт и подтверждён CI #1020;
- B9 capacity/overload baseline закрыт и подтверждён CI #1027;
- B10 controlled release candidate/final semantic freeze закрыт и подтверждён CI #1035;
- дальнейшее развитие ядра остановлено: новые возможности реализуются за пределами frozen kernel.

CI run #1011 на PR #8 head `006493ce4ae710324718bff23a57dfcd0b66641a` завершился зелёным по всем семи jobs. PR #8 остаётся открытым, draft и mergeable; это ещё не production release.

# 3. Что уже сделано в ядре

## 3.1. v1.4 — frozen kernel

Утверждённые 12 элементов:

1. Foundation / Architecture Contract
2. Identity
3. Canonical Search
4. Discovery + Qualification
5. Transactional Persistence
6. Intelligence / Research
7. AI Gateway
8. MAX / Communication Adapter
9. Commercial Action
10. Order
11. Economics
12. Canonical API / Experience Boundary

Состояние:

| Элемент | Состояние |
|---|---|
| Foundation / Architecture Contract | implemented + hardened |
| Identity | implemented + hardened |
| Canonical Search | implemented + hardened |
| Discovery + Qualification | implemented + hardened |
| Transactional Persistence | implemented + hardened |
| Intelligence / Research | implemented + hardened |
| AI Gateway | implemented + hardened |
| MAX / Communication Adapter | adapter contract |
| Commercial Action | implemented + hardened |
| Order | implemented + hardened |
| Economics | implemented + hardened |
| Canonical API / Experience Boundary | contract + runtime edge |

v1.4 semantics не переписываются для решения задач v1.5 runtime.

## 3.2. Identity and Truth Boundary

Закреплено:
- canonical entity = Identity;
- source candidate не является canonical identity;
- INN — основной cross-source deduplication key для текущего российского B2B контура;
- lifecycle RAW → CANDIDATE → IDENTIFIED → VERIFIED → ACTIVE / INACTIVE / UNKNOWN;
- MATCH / MERGE / KEEP_SEPARATE / QUARANTINE / MANUAL_REVIEW;
- ambiguity не повышается до verified truth автоматически.

## 3.3. Evidence / Intelligence

Закреплены:
- R1-R4 research depths;
- required / optional / prohibited source classes;
- provider waterfall;
- budget controls;
- source provenance;
- persisted Evidence;
- conservative qualification;
- quarantine/review для uncertainty.

Внешнее утверждение не считается canonical business truth без evidence.

## 3.4. AI Gateway

AI подчинён:
- authorization;
- policy;
- evidence;
- budget;
- model/prompt versioning;
- provider-result validation;
- audit.

AI не обладает authority над canonical business state.

## 3.5. Idempotency

Закреплена PostgreSQL-backed idempotency model:
- caller-supplied operation key;
- request hash;
- unique key;
- conflict при изменённом запросе;
- durable result reference;
- race-safe reservation;
- transactional completion.

Повтор critical command не должен создавать второй бизнес-эффект.

## 3.6. Transactional Atomicity

Для critical workflows закреплена транзакционная связка:

business state + idempotency + outbox + audit

в рамках одного PostgreSQL transaction.

При ошибке обязательного шага операция откатывается.

## 3.7. Durable Jobs

Реализован durable execution plane:
- persisted job state;
- lease;
- worker ownership;
- expiration;
- reclaim;
- bounded retry;
- current-holder-only completion;
- controlled lease renewal;
- idempotent handlers;
- handler registry.

Handler не получает произвольный UnitOfWork/persistence access.

## 3.8. Transactional Outbox

Закреплены:
- state + event в одной транзакции;
- durable outbox;
- delivery lease;
- worker ownership;
- attempt counter;
- expired lease reclaim;
- current-holder-only publish completion;
- immutable event id;
- downstream idempotent delivery requirement.

At-least-once является сознательной семантикой. Exactly-once на распределённой сети не принимается как предположение.

## 3.9. Commercial Send

Закрыт опасный READY → network TOCTOU:

READY → leased SENDING → external effect → SENT

Стабильный external-effect idempotency key:

commercial-send:{action_id}

Есть reservation, worker, attempt, lease, reclaim и current-worker-only completion.

## 3.10. Order and Economics

Order:
- требует SENT/COMPLETED commercial action;
- имеет явный lifecycle;
- сериализует конкурирующие lifecycle updates;
- сохраняет lineage.

Economics:
- append-only entries;
- traceable source lineage;
- deterministic money;
- cost/revenue/margin lineage.

## 3.11. Database Defense-in-Depth

Migration 0009 state_ownership_invariants добавляет PostgreSQL constraints, которые дополнительно запрещают невозможные lease/state combinations для jobs, outbox delivery и commercial send.

Для существующих v1.4 databases принят отдельный adoption path: migrations 0001-0008 не переисполняются. Schema shape сначала проверяется против обязательного v1.4 baseline, затем migration ledger 0001-0008 создаётся транзакционно с утверждёнными checksums, после чего обычный runner продолжает с 0009.

Инвариант закреплён одновременно в domain/application, repository и database.

## 3.12. Migration Integrity

Введён MigrationRunner с:
- contiguous version sequence;
- filename validation;
- SHA-256 checksums;
- immutable historical migration check;
- transactional application;
- PostgreSQL advisory transaction lock;
- migration ledger.

Историческая migration не должна изменяться незаметно.

## 3.13. Recovery Drills

Уже есть executable drills для:
- worker crash/retry;
- outbox external publication/reclaim.

Следующий уровень drills закреплён в разделе certification.

## 3.14. Architecture Dependency Boundaries

Автоматически проверяется, что domain и foundation не зависят от:
- application;
- adapters;
- experience;
- platform.

Архитектурные границы являются executable rule, а не только документацией.

## 3.15. Release Contract

Есть deterministic release contract, проверяющий:
- frozen kernel contract;
- core maturity contract;
- migration baseline;
- project version;
- maturity gates.

## 3.16. v1.5 Production Controls

Отдельно разработаны:
- production IAM: OIDC/JWT boundary, issuer/audience/expiry, HTTPS, bounded JWKS cache, explicit asymmetric algorithms, permission materialization, fail-closed unknown permissions;
- production security/telemetry/supply-chain: fail-closed configuration, redacted telemetry, correlation context, запрет записи request bodies и authorization headers, dependency audit.

Эти направления сведены в единый проверенный v1.5 candidate; дальнейшая работа идёт через доказательство эксплуатационных свойств и безопасного перехода существующих данных, без изменения frozen v1.4 semantics.

---

# 4. Архитектурная истина

## 4.1. Единственная canonical transactional authority

PostgreSQL.

Не являются system of record:
- Airtable;
- Replit;
- Bitrix24;
- MAX;
- AI provider;
- CRM;
- UI;
- intelligence provider.

Они могут быть adapters/integrations, но не источниками canonical business truth.

## 4.2. Modular monolith остаётся осознанным решением

Service extraction разрешён только при наличии измеренной причины:
- independent scaling;
- fault isolation;
- deployment independence;
- organizational ownership;
- capacity constraint;
- security boundary.

Microservices не являются самостоятельной целью.

## 4.3. Сложность должна находиться внутри платформы

Оператор должен видеть понятные состояния и минимальное число технических решений.

Система сама поглощает:
- recovery;
- deduplication;
- retry;
- evidence;
- auditing;
- leases;
- provider failover.

---

# 5. Что означает «зрелое и бессмертное ядро»

«Бессмертное» — не обещание нулевых отказов.

100% абсолютная безопасность, доступность и отсутствие дефектов для произвольной программной системы недостижимы. Поэтому инженерное определение такое:

> Система считается бессмертной в рациональном продуктовом смысле, если известные классы отказов не уничтожают canonical business truth, операции имеют детерминированные recovery paths, ошибки обнаруживаются, критические изменения аудируются, историческое состояние защищено, внешние зависимости заменяемы, а выпуск новой версии не требует нарушения фундаментальных инвариантов.

Цель — не отсутствие отказов.

Цель — контролируемость последствий отказа.

---

# 6. Семь gates зрелости

## Gate 1 — Correctness

Обязательно:
- domain invariants;
- invalid state rejection;
- identity truth boundary;
- evidence boundary;
- lifecycle correctness;
- money correctness;
- canonical error semantics;
- negative tests.

## Gate 2 — Atomicity

Обязательно:
- critical command atomicity;
- idempotency atomicity;
- state + outbox;
- state + audit;
- rollback consistency.

## Gate 3 — Concurrency

Обязательно:
- duplicate command race;
- lease race;
- expired lease reclaim;
- current-worker-only completion;
- order lifecycle serialization;
- concurrent migration protection.

## Gate 4 — Recovery

Обязательно:
- worker crash before completion;
- worker crash after external effect;
- duplicate delivery;
- dependency timeout;
- lease expiry;
- DB rollback;
- backup restore;
- point-in-time recovery;
- upgrade rollback;
- controlled degraded mode.

Должны быть определены RTO и RPO.

## Gate 5 — Security

Обязательно:
- authentication;
- authorization;
- policy;
- least privilege;
- fail-closed behavior;
- secret handling;
- data isolation;
- encryption;
- dependency vulnerability gate;
- security test matrix;
- OWASP ASVS-style control mapping;
- auditability;
- production configuration validation.

## Gate 6 — Observability

Для каждого critical workflow должна существовать correlation lineage:

request/correlation id → command → authorization/policy → idempotency key → DB transaction → audit → job → outbox event → external effect → result.

Нужно уметь восстановить:
- что произошло;
- с каким объектом;
- кто инициировал;
- какая версия policy/configuration использовалась;
- какая внешняя операция вызывалась;
- какой результат получен;
- где произошёл failure.

## Gate 7 — Release Safety

Обязательно:
- architecture contract validation;
- maturity contract validation;
- lint;
- compile;
- unit;
- PostgreSQL integration tests;
- security tests;
- recovery drills;
- supply-chain audit;
- migration integrity;
- reproducible release artifact;
- controlled rollout;
- rollback path.

---

# 7. Дополнительные maturity controls

## 7.1. SLI/SLO/Error Budget

Для production должны быть определены:
- user-facing SLIs;
- SLOs;
- latency objectives;
- critical workflow success rate;
- recovery objectives;
- error budgets.

При исчерпании error budget изменения, не устраняющие reliability/security defects, должны приостанавливаться.

## 7.2. Capacity and Performance

Нужны:
- load baseline;
- concurrency baseline;
- queue depth limits;
- rate limits;
- bounded retries;
- backpressure;
- timeout budgets;
- capacity model;
- overload behavior;
- graceful degradation.

## 7.3. Data Governance

Для чувствительных и externally-derived данных должны быть определены:
- provenance;
- retention;
- expiry;
- ownership;
- access boundary;
- audit;
- deletion policy;
- source freshness;
- evidence confidence.

## 7.4. AI Safety Boundary

AI output:
- не является canonical truth;
- traceable;
- имеет model/prompt/config version;
- имеет evidence refs;
- имеет budget;
- проходит policy;
- не может самостоятельно менять критическое состояние.

## 7.4A. AI Provider Policy

AI Gateway остаётся provider-neutral application boundary. Конкретные модели и провайдеры не являются частью frozen kernel.

### Облачные AI-провайдеры

Разрешены только два облачных AI-класса:
- **YandexGPT** через Yandex Cloud AI Studio;
- **GigaChat** через GigaChat API.

Любой другой облачный LLM/AI provider считается **запрещённым по умолчанию** и не может быть активирован без отдельного архитектурного решения и явного изменения этого манифеста.

Для облачных провайдеров обязательны:
- отдельный adapter;
- explicit activation;
- runtime-only credentials;
- bounded request/response/resource/cost/time limits;
- readiness/health;
- provenance/evidence discipline;
- fail-closed behavior;
- отсутствие прямого доступа провайдера к canonical business state;
- отсутствие автоматического provider-specific retry без доказанной семантики повторного выполнения.

### Локальные / self-hosted LLM

Система должна поддерживать установку и использование локальных/self-hosted LLM-моделей с **правом бесплатного использования для предполагаемого коммерческого сценария**.

«Бесплатное использование» означает отсутствие обязательной лицензионной/API-платы за использование самой модели; вычислительные ресурсы, электричество, GPU/CPU, хранение и эксплуатация остаются операционными затратами.

Для каждой установленной локальной модели должны быть зафиксированы:
- model identifier и version;
- источник/репозиторий;
- license и URL лицензии;
- дата проверки прав на использование;
- artifact/model digest;
- runtime/adapter;
- resource limits;
- статус безопасности и происхождения.

Локальная модель подключается только через тот же provider-neutral AI Gateway. Она не становится canonical truth и не получает прямого права изменять критическое состояние.

### Production activation gate

Для production cloud AI обязательно действует отдельный reversible activation gate:
- default state — disabled;
- activation only from an immutable production configuration snapshot;
- runtime credential is never stored in the snapshot;
- explicit operator activation is required;
- readiness, cost and deadline ceilings are checked before provider traffic;
- configuration version must match the request scope;
- rollback disables subsequent traffic immediately;
- activation state is operational metadata only and cannot become canonical business state.

### Правило выбора

- Cloud AI → только YandexGPT или GigaChat.
- Local/self-hosted AI → разрешён только при подтверждённом праве бесплатного коммерческого использования.
- Нет неявного fallback Cloud → Local или Local → Cloud.
- Провайдер, модель и configuration version должны быть наблюдаемы и воспроизводимы.
- Появление нового AI provider не является основанием для изменения frozen kernel.

## 7.5. Controlled Change

Каждое изменение core должно ответить:
1. Какой инвариант сохраняется?
2. Какой риск снимается?
3. Каким тестом это доказано?
4. Что происходит при rollback?

Нет ответа — изменение не должно попадать в core.

---

# 8. Что ещё необходимо до Core Maturity Certification

## B1 — GREEN CI — CLOSED / VERIFIED
Полный green подтверждён CI run #970.

## B2 — Unified v1.5 candidate — CLOSED / VERIFIED
Единый baseline подтверждён CI run #989:
- v1.5-runtime;
- production IAM;
- production security/telemetry/supply-chain;
- core maturity.

## B3 — Migration adoption
Для существующих v1.4 databases нужен контролируемый путь:

existing schema → verified baseline → migration ledger → 0009+

без разрушения данных. B3 — текущая активная сертификационная граница.

## B4 — Crash-after-external-effect integration proof — CLOSED / VERIFIED
CI run #999 подтвердил recovery после внешнего эффекта для real commercial send path.

## B5 — Backup / Restore / PITR — CLOSED / VERIFIED

Доказано:
- physical PostgreSQL 16 base backup;
- WAL archiving;
- point-in-time recovery to a controlled target timestamp;
- preservation of canonical identity, commercial action, order, order line, economics and audit lineage;
- exclusion of the later sentinel commit;
- measured RTO = **2.039s**;
- measured RPO = **2.053s** for the controlled drill window;
- recovery is a release-gated CI control.

CI run #1005 (`35841541121`) прошёл все семь jobs, включая `backup-recovery` и `release-contract`.

## B6 — End-to-end observability correlation — CLOSED / VERIFIED

Доказано через PostgreSQL integration test:
- incoming correlation ID reaches canonical API context;
- the same ID reaches a real critical workflow;
- the ID is persisted in audit;
- telemetry emits the same ID;
- authorization headers and request bodies are excluded from telemetry;
- proof passes on Python 3.12 and 3.13.

CI run #1011 подтвердил B6 вместе с backup-recovery и release-contract.

## B7 — Security certification matrix — CLOSED / VERIFIED
Каждый production security control получает:

control → implementation → test → result → release gate.

## B8 — SLO / error-budget baseline — CLOSED / VERIFIED
Определён минимум для:
- API availability;
- critical mutation success;
- job recovery;
- outbox lag;
- external-effect completion;
- latency.

## B9 — Capacity / overload test — CLOSED / VERIFIED
Проверено:
- concurrent critical commands;
- worker saturation;
- retry storm;
- queue backlog;
- DB contention;
- rate limiting;
- graceful degradation.

## B10 — Controlled release candidate / final semantic freeze — CLOSED / VERIFIED

Проведён финальный controlled release-candidate run CI #1035 (`35892641331`) на HEAD `4f5df0346c544ce30525723e4c8748336615ef75`.

Все семь release gates зелёные. `architecture/release_candidate_contract.json` и `docs/CORE_SEMANTIC_FREEZE.md` закрепляют final boundary: v1.4 kernel semantics frozen, новые функции остаются вне ядра, а исключительный core change требует доказанного invariant/security/data-integrity/fundamental reliability defect, regression tests, impact analysis и rollback plan.

B10 не авторизует merge или production deployment.

---

# 9. Что после этого запрещено делать с ядром

После Core Maturity Certification запрещено расширять core просто ради:
- новой интеграции;
- нового UI;
- нового AI provider;
- нового CRM;
- нового канала коммуникации;
- нового low-code инструмента;
- модного архитектурного паттерна;
- microservices без measured constraint.

Такие изменения реализуются за границей ядра.

Изменение frozen core допускается только при:
- доказанном дефекте инварианта;
- security issue;
- data-corruption risk;
- доказанном scalability/reliability boundary;
- изменении фундаментального business invariant.

Требуются:
- architecture decision;
- regression tests;
- migration plan;
- rollback plan;
- impact analysis.

---

# 10. Исследовательская база

Манифест сформирован на основе публично доступных engineering/architecture/reliability materials. Закрытые внутренние процессы компаний не предполагаются и не выдаются за проверенные факты.

## Google / SRE
SLI/SLO, error budgets, supervised rollout, rollback-first, backoff+jitter, automation, toil reduction.

https://sre.google/sre-book/service-level-objectives/
https://sre.google/sre-book/service-best-practices/
https://sre.google/sre-book/embracing-risk/
https://sre.google/sre-book/introduction/

## Microsoft / Azure
Well-Architected reliability, idempotent consumer, bounded retry, backoff, jitter, timeout, health, outbox, chaos/fault injection, reliability maturity and simplicity.

https://learn.microsoft.com/en-us/azure/well-architected/reliability/design-patterns
https://learn.microsoft.com/en-us/azure/well-architected/design-guides/handle-transient-faults
https://learn.microsoft.com/en-us/azure/well-architected/reliability/maturity-model
https://learn.microsoft.com/en-us/azure/well-architected/reliability/checklist
https://learn.microsoft.com/en-us/azure/architecture/patterns/saga

## IBM
Resilience, end-to-end observability, recovery readiness, continuous resiliency testing and automation.

https://www.ibm.com/think/architectures/well-architected/resiliency
https://www.ibm.com/think/topics/observability
https://www.ibm.com/think/topics/observability-engineering

## Yandex / YDB
Failure-first thinking, overload protection, buffering, strict consistency/ACID where required, recovery, retry semantics.

https://github.com/ydb-platform/ydb
https://github.com/ydb-platform/ydb/blob/main/ydb/docs/en/core/recipes/ydb-sdk/retry.md
https://habr.com/ru/companies/yandex/articles/828168/
https://habr.com/ru/companies/yandex/articles/835112/

## VK
Simplicity under scale, reusable platform primitives, technology-independent architecture, asynchronous buffering, release testing.

https://habr.com/ru/companies/vk/articles/683192/
https://habr.com/ru/companies/vk/articles/927836/
https://habr.com/ru/companies/vk/articles/837060/
https://habr.com/ru/companies/vk/articles/703230/

## Sber
High-load resilience, architecture evolution, hiding infrastructure complexity from users, architecture standards and controlled scaling.

https://habr.com/ru/companies/sberbank/articles/796243/
https://habr.com/ru/companies/sberbank/articles/727312/
https://habr.com/ru/companies/sberbank/articles/857524/
https://habr.com/ru/companies/sberbank/articles/807769/

## Salesforce
Event-driven architecture, producer/consumer/channel separation, business event schemas, loose coupling.

https://developer.salesforce.com/docs/platform/platform-events/guide/platform-events-intro-architecture.html
https://github.com/salesforce

## Oracle
Application Continuity, recoverable session handling, transaction replay and ambiguity around lost commit acknowledgements.

https://docs.oracle.com/en/database/oracle/oracle-database/26/odpnt/featAppCont.html
https://docs.oracle.com/en/database/oracle/oracle-database/26/adfns/high-availability.html

## SAP
Clean core, released interfaces, side-by-side extensibility, upgrade safety, API governance, event-driven integration.

https://www.sap.com/documents/2026/07/503068a8-5d7f-0010-bca6-c68f7e60039b.html
https://www.sap.com/documents/2024/09/20aece06-d87e-0010-bca6-c68f7e60039b.html
https://github.com/SAP/architecture-center
https://github.com/SAP-samples/abap-partner-reference-application

## Zoho
Secure-by-design, RBAC, audit trails, change management, environment separation, vulnerability scanning, scaling, async scheduling and API gateway controls.

https://help.zoho.com/portal/en/kb/creator/faqs/getting-started/articles/faq-privacy-security
https://help.zoho.com/portal/en/kb/creator/developer-guide/getting-started/articles/zoho-creator-best-practices
https://catalyst.zoho.com/cookbook/catalyst-101/understanding-catalyst-architecture/

## 1C-Bitrix
Clustering, failover, replication, distributed cache, load balancing and geographical redundancy.

https://www.dev.1c-bitrix.ru/user_help/settings/cluster/index.php
https://www.1c-bitrix.ru/products/cms/modules/web-cluster/
https://www.1c-bitrix.ru/products/cms/performance/

## BPMSoft
Explicit integration boundary, REST/SOAP/OData/webhooks, OAuth/LDAP and external integration performance/resilience review.

https://edu.bpmsoft.ru/baza-znaniy/start-razrabotki/instrumenty-i-printsipy-razrabotki/
https://market.bpmsoft.ru/upload/files/BPMSoft_PartnerProgram-MP.pdf

## Диасофт
Platformized development, development factory, avoidance of distributed monoliths, async/sync integration, CI/CD and automated testing.

https://www.diasoft.ru/about/publications/20088/
https://www.diasoft.ru/about/publications/20761/
https://www.diasoft.ru/about/publications/20897/
https://www.diasoft.ru/about/publications/21490/

## AlphaSense
Research-plan transparency, citations, verification, deep research and repeatable research workflows.

https://help.alpha-sense.com/hc/en-us/articles/41666587181203-Interacting-with-Generative-Search
https://developer.alpha-sense.com/agent-api/gensearch

## Contify
Vetted sources, signal/noise filtering, deduplication, disambiguation, HITL, knowledge-graph grounding and source-grounded AI.

https://www.contify.com/solutions/competitive-intelligence/
https://www.contify.com/ai-info/
https://www.contify.com/resources/blog/competitive-intelligence/

## Valona Intelligence
Decision-centric intelligence, repeatable collection/analysis/delivery and trusted intelligence infrastructure.

https://valonaintelligence.com/resources/blog/insights-blog-competitive-intelligence-best-practices
https://valonaintelligence.com/news/intelligence-infrastructure-thats-built-to-meet-the-moment

## Northern Light
Governed knowledge foundation, trusted source collections, source-linked AI answers and citations.

https://www.northernlight.com/blog/northern-light-announces-generative-ai-question-answering-capability-for-singlepoint-strategic-research-portals
https://www.northernlight.com/blog/singlepoints-generative-ai-capability-gets-conversational

## Crayon
Multi-channel signal capture, filtering, saved/repeatable searches, scheduled analysis and workflow-native delivery.

https://www.crayon.co/product/aggregate
https://www.crayon.co/product/organize
https://www.crayon.co/product/publish
https://www.crayon.co/blog/market-intelligence

## Similarweb / Semrush
Continuously updated intelligence, large-scale data collection, automated pipelines, IaC, CI/CD, data-quality/availability monitoring and cost-aware data engineering.

https://www.similarweb.com/blog/
https://careers.semrush.com/jobs/2083484_Serbia/

## Birdeye / Reputation / NiceJob
Enterprise security/compliance, encryption, monitoring, backups/recovery, multi-source reputation signals and integrations into existing workflows.

https://birdeye.com/security/
https://reputation.com/legal-information/reputation-data-processing-addendum
https://reputation.com/
https://partners.nicejob.com/integrations

---

# 11. Synthesis

Across the publicly verifiable material the durable common principles are:

1. Canonical truth must have an owner.
2. Boundaries matter more than technology fashion.
3. Retries require idempotency.
4. At-least-once delivery requires duplicate-safe consumers.
5. External effects must be isolated from local transactions.
6. Failures must be expected, observable and recoverable.
7. Recovery must be tested, not merely documented.
8. Complexity should be absorbed by platform primitives.
9. Architecture should remain simpler than business scale requires.
10. Interfaces and events should be stable and governed.
11. AI must be grounded, traceable and subordinate to business controls.
12. Security belongs in the development lifecycle.
13. Production quality requires release discipline and measurable operational targets.
14. Microservices are a scaling/isolation tool, not a maturity badge.
15. Actionable intelligence matters more than raw information volume.
16. Automated controls are stronger than verbal process agreements.
17. Mature platforms extend around a stable core instead of repeatedly redefining the core.

---

# 12. Development doctrine

### Core doctrine
Frozen semantics → measurable invariants → executable tests → controlled release → bounded evolution

### Product doctrine
Core → application capabilities → adapters → integrations → experience

### Intelligence doctrine
Sources → observations → identity resolution → evidence → qualification → action → outcome → learning

### Reliability doctrine
Prevent where cheap → detect quickly → contain → recover → audit → learn

### AI doctrine
Evidence → model → constrained output → verification → policy → action

### Security doctrine
Least privilege → fail closed → isolate → encrypt → audit → test → recover

### Architecture doctrine
Simple core first → standard patterns → measured scaling → extracted services only when justified

---

# 13. Definition of Done — Mature Core

- [ ] v1.4 kernel contract remains frozen and green.
- [ ] v1.5 IAM/security/gates integrated into one candidate.
- [ ] CI fully green on supported Python versions.
- [ ] Critical workflow atomicity integration-proven.
- [ ] Concurrent idempotent commands race-safe.
- [ ] Job/outbox/commercial-send reclaim integration-proven.
- [ ] Crash-after-external-effect proven with stable external idempotency.
- [ ] Migration adoption proven for existing databases.
- [ ] Migration history checksum-protected.
- [ ] Backup/restore/PITR proven.
- [ ] RTO/RPO measured.
- [ ] End-to-end correlation proven.
- [ ] SLI/SLO/error-budget baseline exists.
- [ ] Capacity/overload behavior tested.
- [ ] Security controls mapped to tests.
- [ ] Dependency/supply-chain audit green.
- [ ] Release artifact and rollback path deterministic.
- [ ] Final release candidate passes controlled deployment checks.
- [ ] Core semantic freeze formally declared.

---

# 14. Stop line

После выполнения Definition of Done:

**Core Maturity = CERTIFIED**

Дальше новые возможности идут за пределами ядра:
- approved cloud AI providers: YandexGPT and GigaChat;
- installable local/self-hosted free-use LLMs;
- MAX transport;
- intelligence providers;
- payments/settlement;
- Web/PWA/Android;
- team mode;
- CRM integrations;
- product/reporting features;
- integration ecosystem.

Core изменяется только по доказанному invariant defect, security/data-integrity defect или measured fundamental scalability/reliability constraint.

Любое исключение требует architecture decision, regression tests, migration plan, rollback plan и impact analysis.

---

## Universal development doctrine

The repository adopts `docs/UNIVERSAL_DEVELOPMENT_DOCTRINE.md` as the reusable development standard for integrity, reliability, security, scalability, maintainability, observability, intelligence/data governance and release safety. The doctrine governs *how* development is performed; project manifests govern the project's own product and architecture semantics.

## Operational authority

The repository-level operating contract is:
- `AGENTS.md` — mandatory agent operating rules;
- `docs/GITHUB_WORK_PROTOCOL.md` — resumable GitHub development protocol;
- `docs/DEVELOPMENT_STATE.md` — durable interruption cursor;
- `architecture/development_work_protocol.json` — machine-readable version of the workflow protocol.

The agent must restore these documents before substantive GitHub work. A conversation-memory assumption is never allowed to override the repository state ledger.

## Authority

Манифест является development-level interpretation of:
- ARCHITECTURE.md
- architecture/contract.json
- architecture/core_maturity_contract.json
- docs/V1.4_KERNEL.md
- docs/V1.4_KERNEL_CHECKPOINT.md
- docs/V1.5_CORE_MATURITY.md
- docs/V1.5_RUNTIME.md

При расхождении документов расхождение считается defect до разрешения.

The current source-tree HEAD is never copied into this manifest as a permanent value. Live GitHub state is authoritative for branch, commit, PR and CI status.

**Новые core semantics не добавляются только потому, что появилась новая feature request.**
