-- Durable worker execution state.
-- Jobs are infrastructure state. Handlers remain responsible for domain truth.

create table if not exists job_execution (
    job_id text primary key,
    job_type text not null,
    attempt integer not null default 1 check (attempt >= 1),
    state text not null check (
        state in ('queued', 'running', 'succeeded', 'retryable_failure', 'failed', 'cancelled')
    ),
    idempotency_key text not null unique,
    payload jsonb not null default '{}'::jsonb,
    available_at timestamptz not null default now(),
    worker_id text,
    lease_until timestamptz,
    last_error text,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
        (state = 'running' and worker_id is not null and lease_until is not null)
        or state <> 'running'
    )
);

create index if not exists ix_job_execution_ready
    on job_execution (available_at, created_at)
    where state in ('queued', 'retryable_failure');

create index if not exists ix_job_execution_expired
    on job_execution (lease_until)
    where state = 'running' and lease_until is not null;

create index if not exists ix_job_execution_type_state
    on job_execution (job_type, state, updated_at desc);
