-- PostgreSQL transactional authority.
-- Adapters never write these tables directly.

create table if not exists identity (
    identity_id uuid primary key,
    canonical_name text not null,
    state text not null,
    tax_id text,
    registration_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists ux_identity_tax_id
    on identity (tax_id)
    where tax_id is not null;

create table if not exists evidence (
    evidence_id uuid primary key,
    subject_ref text not null,
    claim text not null,
    source_ref text not null,
    truth_class text not null,
    trust_level text not null,
    confidence numeric(5,4) not null check (confidence >= 0 and confidence <= 1),
    observed_at timestamptz not null,
    captured_at timestamptz not null
);

create index if not exists ix_evidence_subject on evidence(subject_ref, captured_at desc);

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
