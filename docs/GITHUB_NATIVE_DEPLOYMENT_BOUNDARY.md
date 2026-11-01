# GitHub-native delivery and hosting boundary

**Decision date:** 2026-11-01  
**Status:** GitHub is the approved source-control and delivery-control plane. Full production hosting on GitHub Free is **BLOCKED by a first-party runtime capability gap**.

## 1. Decision

The canonical repository, source history, pull requests, CI, release evidence, environment controls and deployment approvals remain in GitHub.

No Replit configuration, Yandex Cloud/Terraform infrastructure, or other provider-specific production deployment module is part of the approved product baseline. No external runtime or database provider may be added without an explicit architecture decision and user approval.

This decision does not authorize describing a static preview, a successful CI run, or an open port as a production deployment.

## 2. What GitHub Free can provide

| GitHub capability | Approved role | Production-hosting boundary |
|---|---|---|
| GitHub repository and pull requests | Canonical source, review, history and change governance | Not an application runtime |
| GitHub Actions | Build, lint, test, dependency audit, create immutable artifacts, release orchestration | Hosted jobs are bounded executions, not continuously running application servers |
| GitHub Environments | Deployment approvals, environment-scoped secrets and branch restrictions for supported repository/plan combinations | Controls a deployment; does not provide compute or a database |
| GitHub Packages / Container Registry | Store versioned packages and container images where plan limits permit | Stores artifacts; does not execute containers |
| GitHub Pages | Static project/documentation hosting where the use case and policy permit | HTML/CSS/JavaScript static hosting only; no Python/FastAPI server or PostgreSQL |
| GitHub Codespaces | Interactive development, debugging and bounded manual diagnostics | Development environment; it idles/stops and has a maximum codespace lifetime |
| GitHub Spark | Not an available option | Retired on 2026-08-31; do not plan against it |

For a personal GitHub Free account, the documented Codespaces allowance is 120 core-hours and 15 GB-month storage. The default idle timeout is 30 minutes and a codespace has a 12-hour maximum lifetime. These are development allowances, not a production SLA.

Standard GitHub-hosted Actions runners are free for public repositories, but the job execution limit is six hours. The runner is released when the job ends. That does not provide a durable web process.

## 3. Why GitHub Pages is not the production Web/PWA host for this product

GitHub Pages publishes static files and does not support server-side languages such as Python. The platform's canonical Web/PWA experience depends on the FastAPI application boundary and PostgreSQL-backed business state.

In addition, GitHub Pages' published usage policy says Pages must not be used as a free web-hosting service to run an online business, e-commerce site, or a website primarily directed at facilitating commercial transactions or commercial SaaS. This product is a B2B commercial-intelligence and operator platform with client intake and business workflows. Therefore, Pages is not approved as its production application host.

Do not bypass this boundary by:
- exposing a production application without its canonical API;
- placing business state in browser storage, repository files, Issues, Projects, Actions artifacts or Packages;
- treating GitHub Pages as a proxy for a missing application server;
- claiming a static shell is an operational Web/PWA product.

A non-commercial static project documentation site is a separate use case and does not constitute deployment of the business platform.

## 4. Why Actions and Codespaces are not substitutes

GitHub Actions jobs are finite workflow executions. They may build/test/package/deploy an application to an actual hosting target, but they are not a permanent server process.

Codespaces provides interactive development compute. Its automatic idle shutdown and maximum lifetime make a forwarded application port unsuitable for production availability, stable service identity, background processing or business continuity.

A self-hosted Actions runner would require an independently operated machine and would not be a GitHub-provided free production runtime.

## 5. Required production capabilities

A complete production deployment must provide all of the following as one coherent system:

- persistent HTTPS FastAPI/API runtime;
- persistent PostgreSQL as the canonical transactional authority;
- database migrations and backward-compatible upgrade/rollback;
- durable jobs, worker leases, outbox delivery and bounded retry;
- OIDC/JWT authentication and server-side authorization;
- public intake protections, rate limiting and bot-verification boundary;
- secret isolation and key rotation;
- backup, restore/PITR and tested recovery;
- observability, health/readiness, alerting and operational ownership;
- stable production URL and availability independent of a developer session.

The GitHub Free first-party services listed above do not provide this complete persistent runtime and managed PostgreSQL capability.

## 6. Approved delivery architecture until the hosting gap is resolved

1. GitHub remains the canonical repository and change-control plane.
2. Pull requests run the complete repository release-gate CI on the final commit.
3. GitHub Actions builds reproducible, immutable release artifacts and runs security/supply-chain checks.
4. GitHub Environments hold only the secrets and approvals required for a separately approved deployment target.
5. GitHub Packages/Container Registry may store versioned artifacts; registry storage is not runtime hosting.
6. Production deployment remains blocked until a supported persistent runtime and PostgreSQL target are available under an explicitly approved decision.

## 7. Explicit prohibitions

- No superseded app-hosting files, workflows, contracts or deployment assumptions.
- No infrastructure-as-code deployment modules, provider-specific launchers, cloud state or logging resources, or provider-specific production deployment assumptions.
- No production hosting through GitHub Actions runners or Codespaces.
- No production Web/PWA publishing through GitHub Pages for this business platform.
- No external host, database or edge provider without explicit user approval and a new architecture decision.
- No change to the frozen v1.4 kernel or v1.5 core semantics to compensate for a hosting limitation.

The independent YandexGPT adapter remains governed by its own provider contract; it is not Yandex Cloud infrastructure and is not removed by this deployment cleanup.

## 8. Evidence required to reopen the deployment boundary

A new deployment proposal must demonstrate, using current official product documentation and account-plan entitlements:

- that the selected GitHub first-party product actually supports a persistent server-side application runtime;
- that it supports persistent PostgreSQL or an explicitly approved canonical database;
- stable public HTTPS and required authentication/authorization controls;
- background work, restart behavior, durable storage, backups and restore;
- service availability, resource limits, quotas and total cost at the intended workload;
- complete E2E, failure, recovery, security and rollback evidence;
- no conflict with the provider's acceptable-use rules.

Until every applicable item is evidenced, the result is **BLOCKED — NOT PRODUCTION-DEPLOYABLE**.
