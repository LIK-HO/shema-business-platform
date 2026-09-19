-- Traceable AI execution results.
-- The gateway persists only after provider result validation and budget checks.

create table if not exists ai_run (
    run_id text primary key,
    task_id text not null,
    provider_id text not null,
    model text not null,
    model_version text not null,
    prompt_version text not null,
    input_refs jsonb not null default '[]'::jsonb,
    evidence_refs jsonb not null default '[]'::jsonb,
    output text not null,
    tokens bigint not null check (tokens >= 0),
    cost numeric(20,8) not null check (cost >= 0),
    duration_seconds numeric(20,8) not null check (duration_seconds >= 0),
    created_at timestamptz not null default now()
);

create index if not exists ix_ai_run_task
    on ai_run (task_id, created_at desc);

create index if not exists ix_ai_run_provider
    on ai_run (provider_id, created_at desc);
