create table if not exists public_request_context (
    request_id text primary key,
    correlation_id text not null,
    status text not null,
    service_type text not null,
    location text not null,
    preferred_date_or_period text not null,
    work_or_cargo_description text not null,
    contact_name text not null,
    contact_channel text not null,
    company_name text,
    inn text,
    ogrn_or_ogrnip text,
    preflight_snapshot_id text not null,
    preflight_decision text not null,
    preflight_identity_match text not null,
    source_attribution jsonb not null default '{}'::jsonb,
    created_at timestamptz not null,
    projected_at timestamptz not null,
    updated_at timestamptz not null
);

create index if not exists ix_public_request_context_created
    on public_request_context (created_at desc);

create index if not exists ix_public_request_context_preflight
    on public_request_context (preflight_decision, created_at desc);

create table if not exists operator_notification (
    event_id text primary key,
    request_id text not null,
    event_type text not null,
    severity text not null check (severity in ('LOW', 'INFO', 'ATTENTION', 'HIGH', 'CRITICAL')),
    payload jsonb not null,
    created_at timestamptz not null,
    read_at timestamptz
);

create index if not exists ix_operator_notification_unread
    on operator_notification (created_at desc)
    where read_at is null;
