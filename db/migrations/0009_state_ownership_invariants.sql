-- Database-level ownership invariants.
-- The repository layer already enforces these rules; this migration makes
-- invalid lease/state combinations impossible at the storage boundary.

-- Reassert required outbox lease columns before applying the ownership constraint.
alter table outbox_event
    add column if not exists delivery_attempt integer not null default 0
        check (delivery_attempt >= 0),
    add column if not exists delivery_worker_id text,
    add column if not exists delivery_lease_until timestamptz;

alter table job_execution
    drop constraint if exists job_execution_lease_consistency_check;

alter table job_execution
    add constraint job_execution_lease_consistency_check
        check (
            (
                state = 'running'
                and worker_id is not null
                and lease_until is not null
            )
            or (
                state <> 'running'
                and worker_id is null
                and lease_until is null
            )
        );

alter table outbox_event
    drop constraint if exists outbox_delivery_lease_consistency_check;

alter table outbox_event
    add constraint outbox_delivery_lease_consistency_check
        check (
            (delivery_worker_id is null and delivery_lease_until is null)
            or (
                delivery_worker_id is not null
                and delivery_lease_until is not null
                and published_at is null
            )
        );

alter table commercial_action
    drop constraint if exists commercial_action_send_lease_check;

alter table commercial_action
    add constraint commercial_action_send_lease_check
        check (
            (
                status = 'sending'
                and send_worker_id is not null
                and send_lease_until is not null
            )
            or (
                status <> 'sending'
                and send_worker_id is null
                and send_lease_until is null
            )
        );
