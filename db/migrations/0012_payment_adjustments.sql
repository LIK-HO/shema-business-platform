-- Append-only post-payment provider movements.

create table if not exists payment_adjustment (
    adjustment_id text primary key,
    payment_id text not null references payment_intent(payment_id) on delete restrict,
    provider_event_id text not null unique,
    provider_ref text not null unique,
    kind text not null check (
        kind in ('refund', 'reversal', 'chargeback', 'adjustment')
    ),
    amount numeric(20,8) not null check (amount > 0),
    currency varchar(3) not null check (char_length(currency) = 3),
    occurred_at timestamptz not null
);

create index if not exists ix_payment_adjustment_payment
    on payment_adjustment (payment_id, occurred_at desc);

create index if not exists ix_payment_adjustment_provider_ref
    on payment_adjustment (provider_ref);
