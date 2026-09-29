create table if not exists counterparty_monitoring_batch (
    batch_id text primary key,
    batch_key text not null unique,
    scheduled_at timestamptz not null,
    status text not null check (status in ('collecting', 'running', 'completed')),
    next_cursor text,
    collection_complete boolean not null default false,
    created_at timestamptz not null,
    completed_at timestamptz
);

create index if not exists ix_counterparty_monitoring_batch_status
    on counterparty_monitoring_batch (status, scheduled_at);

create table if not exists counterparty_monitoring_batch_item (
    batch_id text not null references counterparty_monitoring_batch(batch_id) on delete cascade,
    monitor_id text not null references counterparty_monitor(monitor_id) on delete cascade,
    state text not null check (state in ('pending', 'running', 'retryable', 'completed', 'failed')),
    attempt integer not null default 0 check (attempt >= 0),
    available_at timestamptz not null,
    lease_worker_id text,
    lease_until timestamptz,
    last_error_code text,
    last_error_at timestamptz,
    completed_at timestamptz,
    primary key (batch_id, monitor_id)
);

create index if not exists ix_counterparty_monitoring_batch_item_claim
    on counterparty_monitoring_batch_item (
        batch_id, state, available_at, lease_until, monitor_id
    );
