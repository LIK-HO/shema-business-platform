-- Canonical provider activation/rollback state.
-- This is the shared kill-switch authority across all runtime replicas.
create table if not exists provider_activation_state (
    provider_id text primary key,
    enabled boolean not null,
    configuration_version text,
    activation_version text,
    activated_by text,
    activated_at timestamptz,
    max_cost numeric(20,8),
    max_duration_seconds numeric(20,8),
    rollback_by text,
    rollback_at timestamptz,
    rollback_reason text,
    updated_at timestamptz not null default now(),
    check (
        (enabled = false)
        or (
            configuration_version is not null
            and activation_version is not null
            and activated_by is not null
            and activated_at is not null
            and (
                max_cost is null
                or (
                    max_cost > 0
                    and max_duration_seconds is not null
                    and max_duration_seconds > 0
                )
            )
        )
    )
);
