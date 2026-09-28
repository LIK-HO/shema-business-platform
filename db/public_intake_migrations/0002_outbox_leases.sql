alter table intake_outbox_event
    add column if not exists delivery_worker_id text,
    add column if not exists delivery_lease_until timestamptz;

create index if not exists ix_intake_outbox_claim
    on intake_outbox_event (published_at, delivery_lease_until, occurred_at, event_id);
