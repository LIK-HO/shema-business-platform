-- Discovery persistence.
-- Search candidates are source observations, not canonical identities.
-- Quarantine is an explicit holding area for uncertain/conflicting records.

create table if not exists search_candidate (
    candidate_id uuid primary key,
    candidate_ref text not null,
    name text not null,
    region text not null,
    selection_level text not null check (
        selection_level in ('candidate', 'identified', 'verified')
    ),
    source_ref text not null,
    tax_id text,
    registration_id text,
    contact_refs jsonb not null default '[]'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    observed_at timestamptz not null,
    captured_at timestamptz not null,
    lifecycle text not null default 'active' check (
        lifecycle in ('active', 'superseded', 'quarantined', 'expired')
    ),
    created_at timestamptz not null default now(),
    check (captured_at >= observed_at)
);

create unique index if not exists ux_search_candidate_source_ref
    on search_candidate (source_ref, candidate_ref);

create index if not exists ix_search_candidate_tax_id
    on search_candidate (tax_id)
    where tax_id is not null;

create index if not exists ix_search_candidate_region
    on search_candidate (region);

create table if not exists quarantine_record (
    quarantine_id uuid primary key,
    object_type text not null,
    object_ref text not null,
    reason_code text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    resolution text,
    check (
        (resolved_at is null and resolution is null)
        or (resolved_at is not null and resolution is not null)
    )
);

create index if not exists ix_quarantine_open
    on quarantine_record (created_at)
    where resolved_at is null;
