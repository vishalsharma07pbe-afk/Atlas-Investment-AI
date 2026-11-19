#!/usr/bin/env bash
set -euo pipefail

umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${ATLAS_PRODUCTION_COMPOSE_FILE:-$repo_root/docker-compose.production.yml}"
backup_root="${ATLAS_BACKUP_DIR:-$repo_root/backups}"
environment_file="${ATLAS_PRODUCTION_ENV_FILE:-}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_dir="$backup_root/$timestamp"
compose_args=(-f "$compose_file")
if [[ -n "$environment_file" ]]; then
  if [[ ! -f "$environment_file" ]]; then
    printf 'Production environment file does not exist: %s\n' "$environment_file" >&2
    exit 2
  fi
  compose_args=(--env-file "$environment_file" -f "$compose_file")
fi
mkdir -p "$backup_root"
work_dir="$(mktemp -d "$backup_root/.atlas-backup-${timestamp}.XXXXXX")"
intelligence_stopped=false

cleanup() {
  if [[ "$intelligence_stopped" == "true" ]]; then
    docker compose "${compose_args[@]}" start intelligence >/dev/null
  fi
  if [[ -d "$work_dir" ]]; then
    rm -rf "$work_dir"
  fi
}
trap cleanup EXIT

docker compose "${compose_args[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$work_dir/postgres.dump"

# Quiesce SQLite and JSON state before streaming its named volumes.
docker compose "${compose_args[@]}" stop intelligence >/dev/null
intelligence_stopped=true
docker compose "${compose_args[@]}" run --rm --no-deps -T intelligence python -m app.ops_snapshot > "$work_dir/intelligence-state.tar.gz"
docker compose "${compose_args[@]}" start intelligence >/dev/null
intelligence_stopped=false

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$work_dir" && sha256sum postgres.dump intelligence-state.tar.gz > SHA256SUMS)
else
  (cd "$work_dir" && shasum -a 256 postgres.dump intelligence-state.tar.gz > SHA256SUMS)
fi

cat > "$work_dir/MANIFEST.txt" <<EOF
ATLAS production backup
created_at=$timestamp
contents=PostgreSQL custom dump plus quiesced intelligence state
classification=PRIVATE FINANCIAL RESEARCH DATA
restore_test_required=true
EOF

mv "$work_dir" "$final_dir"
trap - EXIT
printf 'Backup created at %s\n' "$final_dir"
printf 'Encrypt and copy it to a separate failure domain before considering it durable.\n'

