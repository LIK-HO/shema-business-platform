-- Durable reservation for an external commercial send.
-- A leased SENDING state closes the READY-to-network TOCTOU window and remains reclaimable.

alter table commercial_action
    add column if not exists send_attempt integer not null default 0
        check (send_attempt >= 0),
    add column if not exists send_worker_id text,
    add column if not exists send_lease_until timestamptz;

alter table commercial_action
    drop constraint if exists commercial_action_status_check;

alter table commercial_action
    add constraint commercial_action_status_check
        check (
            status in (
                'draft',
                'ready',
                'sending',
                'sent',
                'failed',
                'completed',
                'cancelled'
            )
        );

alter table commercial_action
    drop constraint if exists commercial_action_sending_lease_check;

alter table commercial_action
    add constraint commercial_action_sending_lease_check
        check (
            (status = 'sending' and send_worker_id is not null and send_lease_until is not null)
            or status <> 'sending'
        );

create index if not exists ix_commercial_action_send_lease
    on commercial_action (send_lease_until, updated_at, action_id)
    where status = 'sending';
