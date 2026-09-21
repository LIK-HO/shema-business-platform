-- Durable ownership for external outbox delivery.
-- Expired delivery leases remain reclaimable and published_at remains authoritative.

alter table outbox_event
    add column if not exists delivery_attempt integer not null default 0
        check (delivery_attempt >= 0),
    add column if not exists delivery_worker_id text,
    add column if not exists delivery_lease_until timestamptz;

create index if not exists ix_outbox_delivery_lease
    on outbox_event (delivery_lease_until, occurred_at, event_id)
    where published_at is null;
