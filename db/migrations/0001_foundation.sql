-- PostgreSQL transactional authority.
-- Adapters never write these tables directly.
-- The application must commit state changes and outbox inserts in one transaction.

create table if not exists identity (
    identity_id uuid primary key,
    canonical_name text not null,
    state text not null check (
        state in ('raw', 'candidate', 'identified', 'verified', 'active', 'inactive', 'unknown')
    ),
    tax_id text,
    registration_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists ux_identity_tax_id
    on identity (tax_id)
    where tax_id is not null;

create unique index if not exists ux_identity_registration_id
    on identity (registration_id)
    where registration_id is not null;

create table if not exists evidence (
    evidence_id uuid primary key,
    subject_ref text not null,
    claim text not null,
    source_ref text not null,
    truth_class text not null check (
        truth_class in ('fact', 'evidence', 'signal', 'hypothesis')
    ),
    trust_level text not null check (
        trust_level in ('T0', 'T1', 'T2', 'T3', 'T4')
    ),
    confidence numeric(5,4) not null check (confidence >= 0 and confidence <= 1),
    provenance jsonb not null default '{}'::jsonb,
    observed_at timestamptz not null,
    captured_at timestamptz not null,
    expires_at timestamptz,
    lifecycle text not null default 'active' check (
        lifecycle in ('active', 'expired', 'superseded', 'quarantined')
    ),
    check (captured_at >= observed_at)
);

create index if not exists ix_evidence_subject on evidence(subject_ref, captured_at desc);
create index if not exists ix_evidence_expiry on evidence(expires_at)
    where expires_at is not null;

create table if not exists idempotency_key (
    key text primary key,
    request_hash text not null,
    result_ref text not null,
    created_at timestamptz not null default now()
);

create table if not exists audit_log (
    audit_id uuid primary key,
    actor_id text not null,
    action text not null,
    resource_type text not null,
    resource_id text,
    outcome text not null,
    occurred_at timestamptz not null,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists outbox_event (
    event_id uuid primary key,
    event_type text not null,
    aggregate_type text not null,
    aggregate_id text not null,
    payload jsonb not null,
    occurred_at timestamptz not null default now(),
    published_at timestamptz
);

create index if not exists ix_outbox_pending
    on outbox_event (occurred_at)
    where published_at is null;
