-- Database-level ownership invariants.
-- The repository layer already enforces these rules; this migration makes
-- invalid lease/state combinations impossible at the storage boundary.

-- Reassert the outbox delivery lease columns so partially adopted v1.4
-- schemas cannot reach the ownership constraint without the required state.
alter table outbox_event
    add column if not exists delivery_attempt integer not null default 0
        check (delivery_attempt >= 0),
    add column if not exists delivery_worker_id text,
    add column if not exists delivery_lease_until timestamptz;

