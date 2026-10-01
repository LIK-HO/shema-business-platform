-- Resource ownership is a security boundary.
-- Existing rows remain NULL and therefore fail closed until explicitly assigned.
alter table commercial_action
    add column if not exists owner_actor_id text;

alter table order_header
    add column if not exists owner_actor_id text;

alter table repeat_order_plan
    add column if not exists owner_actor_id text;

create index if not exists ix_commercial_action_owner_actor
    on commercial_action (owner_actor_id);

create index if not exists ix_order_header_owner_actor
    on order_header (owner_actor_id);

create index if not exists ix_repeat_order_plan_owner_actor
    on repeat_order_plan (owner_actor_id);
