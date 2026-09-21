-- Immutable settlement statement lines used for deterministic reconciliation.

create table if not exists settlement_line (
    line_id text primary key,
    settlement_id text not null references settlement_record(settlement_id) on delete restrict,
    provider_ref text not null,
    amount numeric(20,8) not null check (amount > 0),
    currency varchar(3) not null check (char_length(currency) = 3),
    statement_ref text not null,
    unique (settlement_id, provider_ref)
);

create index if not exists ix_settlement_line_provider_ref
    on settlement_line (provider_ref);

create index if not exists ix_settlement_line_settlement
    on settlement_line (settlement_id, line_id);
