create table if not exists intake_idempotency_reservation (
    idempotency_key text primary key,
    request_hash text not null,
    request_id text not null unique,
    leased_until timestamptz not null,
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists ix_intake_idempotency_expiry
    on intake_idempotency_reservation (leased_until)
    where completed_at is null;
