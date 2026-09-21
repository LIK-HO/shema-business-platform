-- Provider-neutral payment and settlement state.
-- Concrete provider credentials and transport remain outside the database schema.

create table if not exists payment_intent (
    payment_id text primary key,
    order_id text not null references order_header(order_id),
    amount numeric(20,8) not null check (amount > 0),
    currency varchar(3) not null check (char_length(currency) = 3),
    idempotency_key text not null unique,
    status text not null check (
        status in ('draft', 'pending', 'processing', 'succeeded', 'failed', 'cancelled')
    ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists ix_payment_intent_order
    on payment_intent (order_id, updated_at desc);

create index if not exists ix_payment_intent_status
    on payment_intent (status, updated_at desc);

create table if not exists payment_attempt (
    attempt_id text primary key,
    payment_id text not null references payment_intent(payment_id),
    attempt_number integer not null check (attempt_number >= 1),
    external_idempotency_key text not null unique,
    status text not null check (
        status in ('ready', 'sending', 'pending', 'succeeded', 'failed', 'expired')
    ),
    provider_ref text,
    send_worker_id text,
    send_lease_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (payment_id, attempt_number),
    check (
        (status = 'sending' and send_worker_id is not null and send_lease_until is not null)
        or status <> 'sending'
    )
);

create index if not exists ix_payment_attempt_payment
    on payment_attempt (payment_id, attempt_number desc);

create index if not exists ix_payment_attempt_lease
    on payment_attempt (send_lease_until, updated_at, attempt_id)
    where status = 'sending';

create table if not exists provider_event (
    event_id text primary key,
    provider_ref text not null,
    event_type text not null,
    signature_verified boolean not null,
    payload_hash text not null,
    received_at timestamptz not null,
    status text not null check (
        status in ('received', 'processed', 'ignored')
    ),
    processed_at timestamptz
);

create index if not exists ix_provider_event_provider_ref
    on provider_event (provider_ref, received_at desc);

create table if not exists settlement_record (
    settlement_id text primary key,
    provider_settlement_ref text not null unique,
    gross_amount numeric(20,8) not null check (gross_amount >= 0),
    fees numeric(20,8) not null check (fees >= 0),
    net_amount numeric(20,8) not null check (net_amount >= 0),
    currency varchar(3) not null check (char_length(currency) = 3),
    settled_at timestamptz not null,
    status text not null check (
        status in ('expected', 'reconciling', 'settled', 'discrepancy')
    ),
    check (net_amount = gross_amount - fees)
);

create table if not exists reconciliation_item (
    reconciliation_id text primary key,
    settlement_id text not null references settlement_record(settlement_id),
    reason_code text not null,
    expected_amount numeric(20,8),
    observed_amount numeric(20,8),
    currency varchar(3) not null check (char_length(currency) = 3),
    status text not null check (status in ('open', 'resolved')),
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    check (
        expected_amount is null or expected_amount >= 0
    ),
    check (
        observed_amount is null or observed_amount >= 0
    )
);

create index if not exists ix_reconciliation_open
    on reconciliation_item (status, created_at desc);
