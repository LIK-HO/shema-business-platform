alter table settlement_record
    add column if not exists statement_hash text;

update settlement_record
set statement_hash = 'legacy:' || provider_settlement_ref
where statement_hash is null;

alter table settlement_record
    alter column statement_hash set not null;

create index if not exists ix_settlement_statement_hash
    on settlement_record (statement_hash);
