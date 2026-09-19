-- Alignment migration for audit execution context.
-- Existing foundation migrations remain immutable; context is added forward-only.

alter table audit_log
    add column if not exists correlation_id text;

alter table audit_log
    add column if not exists configuration_version text;

create index if not exists ix_audit_correlation
    on audit_log (correlation_id)
    where correlation_id is not null;
