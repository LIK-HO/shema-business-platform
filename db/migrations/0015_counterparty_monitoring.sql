create table if not exists counterparty_monitor (
    monitor_id text primary key,
    actor_id text not null,
    identifier_type text not null check (identifier_type in ('INN', 'OGRN', 'OGRNIP')),
    identifier text not null,
    status text not null default 'active'
        check (status in ('active', 'paused')),
    frequency_seconds integer not null default 86400
        check (frequency_seconds > 0),
    next_check_at timestamptz not null,
    last_checked_at timestamptz,
    last_snapshot_id text,
    last_error_code text,
    last_error_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    unique (actor_id, identifier_type, identifier)
);

create index if not exists ix_counterparty_monitor_due
    on counterparty_monitor (status, next_check_at, monitor_id);

create table if not exists counterparty_favorite (
    favorite_id text primary key,
    actor_id text not null,
    identifier_type text not null check (identifier_type in ('INN', 'OGRN', 'OGRNIP')),
    identifier text not null,
    created_at timestamptz not null,
    unique (actor_id, identifier_type, identifier)
);

create index if not exists ix_counterparty_favorite_actor
    on counterparty_favorite (actor_id, created_at desc, favorite_id);

create table if not exists counterparty_snapshot (
    snapshot_id text primary key,
    monitor_id text not null references counterparty_monitor(monitor_id),
    observed_at timestamptz not null,
    source_ref text not null,
    source_version text not null,
    payload jsonb not null,
    payload_hash text not null,
    created_at timestamptz not null,
    unique (monitor_id, observed_at, payload_hash)
);

create index if not exists ix_counterparty_snapshot_monitor
    on counterparty_snapshot (monitor_id, observed_at desc, snapshot_id desc);

create table if not exists counterparty_change_event (
    change_id text primary key,
    monitor_id text not null references counterparty_monitor(monitor_id),
    before_snapshot_id text not null references counterparty_snapshot(snapshot_id),
    after_snapshot_id text not null references counterparty_snapshot(snapshot_id),
    changed_parameters jsonb not null,
    severity text not null check (severity in ('INFO', 'ATTENTION', 'HIGH', 'CRITICAL')),
    source_ref text not null,
    freshness text not null check (freshness in ('FRESH', 'EXPIRED')),
    correlation_id text not null,
    notification_id text not null unique,
    detected_at timestamptz not null,
    unique (monitor_id, before_snapshot_id, after_snapshot_id)
);

create index if not exists ix_counterparty_change_monitor
    on counterparty_change_event (monitor_id, detected_at desc, change_id desc);
