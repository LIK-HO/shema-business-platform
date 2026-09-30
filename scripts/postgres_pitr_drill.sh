#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
WORK_ROOT="${RUNNER_TEMP:-/tmp}/shema-postgres-pitr"
ARCHIVE_DIR="$WORK_ROOT/archive"
BASEBACKUP_DIR="$WORK_ROOT/basebackup"
SOURCE_CONTAINER="shema-pitr-source"
RESTORE_CONTAINER="shema-pitr-restore"

rm -rf "$WORK_ROOT"
mkdir -p "$ARCHIVE_DIR" "$BASEBACKUP_DIR"
chmod 777 "$ARCHIVE_DIR" "$BASEBACKUP_DIR"

cleanup() {
  docker rm -f "$RESTORE_CONTAINER" "$SOURCE_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d \
  --name "$SOURCE_CONTAINER" \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=shema \
  -p 55432:5432 \
  -v "$ARCHIVE_DIR:/var/lib/postgresql/archive" \
  postgres:16 \
  postgres \
    -c wal_level=replica \
    -c archive_mode=on \
    -c "archive_command=test ! -f /var/lib/postgresql/archive/%f && cp %p /var/lib/postgresql/archive/%f" \
  >/dev/null

for _ in {1..60}; do
  if docker exec "$SOURCE_CONTAINER" pg_isready -U postgres -d shema >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker exec "$SOURCE_CONTAINER" pg_isready -U postgres -d shema >/dev/null 2>&1; then
  echo "PostgreSQL source did not become ready" >&2
  exit 1
fi

export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:55432/shema"

python - <<'PY'
import os
from pathlib import Path
import psycopg

from shema_platform.platform.migrations import MigrationPlan, MigrationRunner

plan = MigrationPlan.from_directory(
    Path(os.environ["GITHUB_WORKSPACE"]) / "db" / "migrations"
)
runner = MigrationRunner(
    lambda: psycopg.connect(os.environ["DATABASE_URL"]),
    plan,
)
report = runner.apply()
assert report.current_version == 9
assert report.applied == tuple(range(1, 10))
PY

python - <<'PY'
import os
import psycopg

dsn = os.environ["DATABASE_URL"]

with psycopg.connect(dsn) as connection:
    connection.execute(
        """
        insert into identity (
            identity_id, canonical_name, state, tax_id
        ) values (
            '00000000-0000-0000-0000-000000000501',
            'PITR baseline identity',
            'verified',
            '7700000001'
        )
        """
    )
    connection.execute(
        """
        insert into commercial_action (
            action_id, identity_id, contact_ref, channel, evidence_refs, status
        ) values (
            'pitr-action-1',
            '00000000-0000-0000-0000-000000000501',
            'pitr-contact',
            'max',
            '["evidence:pitr"]'::jsonb,
            'ready'
        )
        """
    )
    connection.execute(
        """
        insert into order_header (
            order_id, identity_id, source_action_id, status
        ) values (
            'pitr-order-1',
            '00000000-0000-0000-0000-000000000501',
            'pitr-action-1',
            'confirmed'
        )
        """
    )
    connection.execute(
        """
        insert into order_line (
            line_id, order_id, description, quantity, unit_price, currency
        ) values (
            'pitr-line-1',
            'pitr-order-1',
            'PITR recovery fixture',
            1,
            1000,
            'RUB'
        )
        """
    )
    connection.execute(
        """
        insert into economic_entry (
            entry_id, entity_ref, kind, amount, currency, source_ref, occurred_at
        ) values (
            'pitr-economic-1',
            'pitr-order-1',
            'revenue',
            1000,
            'RUB',
            'pitr:fixture',
            now()
        )
        """
    )
    connection.execute(
        """
        insert into audit_log (
            audit_id, actor_id, action, resource_type, resource_id,
            outcome, occurred_at, metadata, correlation_id, configuration_version
        ) values (
            '00000000-0000-0000-0000-000000000502',
            'pitr-drill',
            'pitr.baseline.created',
            'order',
            'pitr-order-1',
            'success',
            now(),
            '{}'::jsonb,
            'corr-pitr-baseline',
            '1.5.0'
        )
        """
    )
    connection.commit()
PY

docker exec -e PGPASSWORD=postgres "$SOURCE_CONTAINER" \
  pg_basebackup \
  -h 127.0.0.1 \
  -U postgres \
  -D /tmp/basebackup \
  -Fp \
  -Xs \
  -P

docker cp "$SOURCE_CONTAINER:/tmp/basebackup/." "$BASEBACKUP_DIR/"

SENTINEL1_TIME="$(docker exec -e PGPASSWORD=postgres "$SOURCE_CONTAINER" psql -U postgres -d shema -Atqc "
begin;
insert into audit_log (
    audit_id, actor_id, action, resource_type, resource_id,
    outcome, occurred_at, metadata, correlation_id, configuration_version
) values (
    '00000000-0000-0000-0000-000000000503',
    'pitr-drill',
    'pitr.sentinel.1',
    'order',
    'pitr-order-1',
    'success',
    now(),
    '{}'::jsonb,
    'corr-pitr-sentinel-1',
    '1.5.0'
);
commit;
select clock_timestamp();
")"

sleep 2

SENTINEL2_TIME="$(docker exec -e PGPASSWORD=postgres "$SOURCE_CONTAINER" psql -U postgres -d shema -Atqc "
begin;
insert into audit_log (
    audit_id, actor_id, action, resource_type, resource_id,
    outcome, occurred_at, metadata, correlation_id, configuration_version
) values (
    '00000000-0000-0000-0000-000000000504',
    'pitr-drill',
    'pitr.sentinel.2',
    'order',
    'pitr-order-1',
    'success',
    now(),
    '{}'::jsonb,
    'corr-pitr-sentinel-2',
    '1.5.0'
);
commit;
select clock_timestamp();
")"

docker exec -e PGPASSWORD=postgres "$SOURCE_CONTAINER" \
  psql -U postgres -d shema -Atqc "select pg_switch_wal();" >/dev/null

for _ in {1..60}; do
  if [[ "$(find "$ARCHIVE_DIR" -type f | wc -l)" -gt 0 ]]; then
    break
  fi
  sleep 1
done

if [[ "$(find "$ARCHIVE_DIR" -type f | wc -l)" -eq 0 ]]; then
  echo "No WAL segment was archived" >&2
  exit 1
fi

rm -f "$BASEBACKUP_DIR/recovery.signal"
sed -i "/^restore_command = /d;/^recovery_target_time = /d;/^recovery_target_action = /d;/^recovery_target_timeline = /d" \
  "$BASEBACKUP_DIR/postgresql.auto.conf" 2>/dev/null || true

cat >> "$BASEBACKUP_DIR/postgresql.auto.conf" <<EOF
restore_command = 'cp /var/lib/postgresql/archive/%f %p'
recovery_target_time = '$SENTINEL1_TIME'
recovery_target_action = 'promote'
recovery_target_timeline = 'latest'
EOF

touch "$BASEBACKUP_DIR/recovery.signal"

RESTORE_START_NS="$(date +%s%N)"

docker run -d \
  --name "$RESTORE_CONTAINER" \
  -e POSTGRES_PASSWORD=postgres \
  -p 55433:5432 \
  -v "$BASEBACKUP_DIR:/var/lib/postgresql/data" \
  -v "$ARCHIVE_DIR:/var/lib/postgresql/archive:ro" \
  postgres:16 \
  postgres \
  >/dev/null

RECOVERED="f"
for _ in {1..180}; do
  if docker exec "$RESTORE_CONTAINER" pg_isready -U postgres -d shema >/dev/null 2>&1; then
    RECOVERED="$(docker exec "$RESTORE_CONTAINER" psql -U postgres -d shema -Atqc \
      "select not pg_is_in_recovery();")"
    RECOVERED="$(printf '%s' "$RECOVERED" | tr -d '[:space:]')"
    if [[ "$RECOVERED" == "t" ]]; then
      break
    fi
  fi
  sleep 1
done

RESTORE_END_NS="$(date +%s%N)"

if [[ "$RECOVERED" != "t" ]]; then
  docker logs "$RESTORE_CONTAINER" >&2 || true
  echo "PostgreSQL PITR restore did not promote within 180 seconds" >&2
  exit 1
fi

RTO_SECONDS="$(python - <<PY
start = int("$RESTORE_START_NS")
end = int("$RESTORE_END_NS")
print(f"{(end - start) / 1_000_000_000:.3f}")
PY
)"

RPO_SECONDS="$(python - <<PY
from datetime import datetime
first = datetime.fromisoformat("$SENTINEL1_TIME".replace(" ", "T"))
second = datetime.fromisoformat("$SENTINEL2_TIME".replace(" ", "T"))
print(f"{(second - first).total_seconds():.3f}")
PY
)"

python - <<PY
rto = float("$RTO_SECONDS")
if rto >= 120:
    raise SystemExit(f"RTO exceeds CI drill threshold: {rto:.3f}s")
PY

CANONICAL="$(docker exec "$RESTORE_CONTAINER" psql -U postgres -d shema -Atqc "
select
    (select count(*) from identity where identity_id = '00000000-0000-0000-0000-000000000501'),
    (select count(*) from commercial_action where action_id = 'pitr-action-1' and status = 'ready'),
    (select count(*) from order_header where order_id = 'pitr-order-1' and source_action_id = 'pitr-action-1'),
    (select count(*) from order_line where line_id = 'pitr-line-1'),
    (select count(*) from economic_entry where entry_id = 'pitr-economic-1'),
    (select count(*) from audit_log where audit_id = '00000000-0000-0000-0000-000000000502'),
    (select count(*) from audit_log where audit_id = '00000000-0000-0000-0000-000000000503'),
    (select count(*) from audit_log where audit_id = '00000000-0000-0000-0000-000000000504'),
    (select count(*) from schema_migration where version = 9)
")"

EXPECTED="1|1|1|1|1|1|1|0|1"
if [[ "$CANONICAL" != "$EXPECTED" ]]; then
  echo "Unexpected PITR canonical-state result: $CANONICAL" >&2
  docker logs "$RESTORE_CONTAINER" >&2 || true
  exit 1
fi

echo "PITR_DRILL=PASS"
echo "PITR_TARGET_TIME=$SENTINEL1_TIME"
echo "PITR_LATER_COMMIT_TIME=$SENTINEL2_TIME"
echo "RTO_SECONDS=$RTO_SECONDS"
echo "RPO_SECONDS=$RPO_SECONDS"
echo "CANONICAL_STATE=$CANONICAL"

if [[ -v GITHUB_STEP_SUMMARY ]]; then
  {
    echo "## PostgreSQL PITR drill"
    echo ""
    echo "- Result: PASS"
    echo "- Recovery target: $SENTINEL1_TIME"
    echo "- Later commit deliberately excluded: $SENTINEL2_TIME"
    echo "- Measured RTO: $RTO_SECONDS"
    echo "- Measured RPO: $RPO_SECONDS"
    echo "- Canonical state after recovery: identity, commercial action, order, order line, economics, baseline audit and migration ledger preserved; later sentinel absent."
  } >> "$GITHUB_STEP_SUMMARY"
fi
