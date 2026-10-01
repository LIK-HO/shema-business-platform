-- Durable commercial execution and economic lineage.
-- All state changes remain under PostgreSQL transaction authority.

create table if not exists commercial_action (
    action_id text primary key,
    identity_id text not null,
    contact_ref text not null,
    channel text not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    status text not null check (
        status in ('draft', 'ready', 'sent', 'failed', 'completed', 'cancelled')
    ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_commercial_action_identity
    on commercial_action (identity_id, updated_at desc);

create index if not exists ix_commercial_action_status
    on commercial_action (status, updated_at desc);

create table if not exists order_header (
    order_id text primary key,
    identity_id text not null,
    source_action_id text not null references commercial_action(action_id),
    status text not null check (
        status in ('draft', 'confirmed', 'in_progress', 'completed', 'cancelled', 'failed')
    ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_order_identity
    on order_header (identity_id, updated_at desc);

create index if not exists ix_order_source_action
    on order_header (source_action_id);

create table if not exists order_line (
    line_id text primary key,
    order_id text not null references order_header(order_id) on delete cascade,
    description text not null,
    quantity numeric(20,8) not null check (quantity > 0),
    unit_price numeric(20,8) not null check (unit_price >= 0),
    currency varchar(3) not null check (char_length(currency) = 3),
    created_at timestamptz not null default now()
);

create index if not exists ix_order_line_order
    on order_line (order_id);

create table if not exists economic_entry (
    entry_id text primary key,
    entity_ref text not null,
    kind text not null check (
        kind in ('provider_cost', 'ai_cost', 'order_cost', 'revenue', 'adjustment')
    ),
    amount numeric(20,8) not null,
    currency varchar(3) not null check (char_length(currency) = 3),
    source_ref text not null,
    occurred_at timestamptz not null,
    check (kind = 'adjustment' or amount >= 0)
);

create index if not exists ix_economic_entry_entity
    on economic_entry (entity_ref, occurred_at desc);
