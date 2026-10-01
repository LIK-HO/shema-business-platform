-- Phase 3A repeat-order continuity state.
-- This is a product/application table around the frozen Order/Economics model.
create table repeat_order_plan (
    plan_id text primary key,
    source_order_id text not null references order_header(order_id),
    identity_id uuid not null references identity(identity_id),
    status text not null check (status in ('active', 'paused', 'cancelled')),
    cadence_unit text not null check (cadence_unit in ('day', 'week', 'month')),
    cadence_interval integer not null check (cadence_interval >= 1),
    scheduled_for timestamptz not null,
    service_scope text not null check (length(trim(service_scope)) > 0),
    capacity_units numeric(18,3) not null check (capacity_units > 0),
    last_order_id text references order_header(order_id),
    pending_order_id text references order_header(order_id),
    skipped_occurrences integer not null default 0
        check (skipped_occurrences >= 0),
    revision integer not null default 1
        check (revision >= 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index repeat_order_plan_identity_idx
    on repeat_order_plan (identity_id, status);

create index repeat_order_plan_pending_idx
    on repeat_order_plan (pending_order_id)
    where pending_order_id is not null;
