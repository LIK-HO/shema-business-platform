create table if not exists intake_request (
    request_id text primary key,
    correlation_id text not null,
    idempotency_key text not null unique,
    request_hash text not null,
    status text not null check (status in ('ACCEPTED', 'QUARANTINED_SPAM')),
    service_type text not null,
    location text not null,
    preferred_date_or_period text not null,
    work_or_cargo_description text not null,
    contact_name text not null,
    contact_channel text not null,
    approximate_volume_or_weight text,
    access_or_lifting_constraints text,
    company_name text,
    inn text,
    ogrn_or_ogrnip text,
    comments text,
    utm_source text,
    utm_medium text,
    utm_campaign text,
    referrer text,
    entry_surface text not null,
    preflight_snapshot_id text not null,
    preflight_decision text not null,
    created_at timestamptz not null,
    projected_at timestamptz
);

create index if not exists ix_intake_request_created
    on intake_request (created_at desc);

create index if not exists ix_intake_request_status
    on intake_request (status, created_at desc);

create table if not exists intake_preflight_snapshot (
    snapshot_id text primary key,
    cache_key text,
    request_id text,
    identifier_type text,
    normalized_identifier text,
    decision text not null,
    identity_match text not null,
    canonical_name text,
    legal_status text,
    source_ref text,
    provider_id text,
    observed_at timestamptz not null,
    expires_at timestamptz not null,
    flags jsonb not null default '[]'::jsonb,
    error_code text,
    captured_at timestamptz not null default now()
);

create unique index if not exists ux_intake_preflight_cache
    on intake_preflight_snapshot (cache_key)
    where cache_key is not null;

create index if not exists ix_intake_preflight_request
    on intake_preflight_snapshot (request_id);

create table if not exists intake_outbox_event (
    event_id text primary key,
    request_id text not null,
    event_type text not null,
    payload jsonb not null,
    occurred_at timestamptz not null,
    notify_operator boolean not null default true,
    delivery_attempt integer not null default 0,
    published_at timestamptz
);

create index if not exists ix_intake_outbox_pending
    on intake_outbox_event (occurred_at, event_id)
    where published_at is null;

create table if not exists intake_rate_limit (
    public_client_key_hash text not null,
    budget text not null,
    window_started_at timestamptz not null,
    used_count integer not null check (used_count >= 0),
    primary key (public_client_key_hash, budget, window_started_at)
);
