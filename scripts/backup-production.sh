#!/usr/bin/env bash
set -euo pipefail

umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${ATLAS_PRODUCTION_COMPOSE_FILE:-$repo_root/docker-compose.production.yml}"
backup_root="${ATLAS_BACKUP_DIR:-$repo_root/backups}"
environment_file="${ATLAS_PRODUCTION_ENV_FILE:-}"
mode=production
case "${1:-}" in
  --local)
    mode=local
    compose_file="$repo_root/docker-compose.yml"
    environment_file="$repo_root/.env"
    shift
    ;;
  "") ;;
  *) printf 'Usage: bash scripts/backup-production.sh [--local]\n' >&2; exit 2 ;;
esac
if [[ $# -ne 0 ]]; then
  printf 'Unexpected backup arguments\n' >&2
  exit 2
fi
# Relative paths and Compose project discovery must match the normal local
# startup command. Never resolve a different checkout's .env.
cd "$repo_root"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_dir="$backup_root/$timestamp"
compose_args=(-f "$compose_file")
if [[ -n "$environment_file" ]]; then
  if [[ ! -f "$environment_file" ]]; then
    printf 'Selected environment file does not exist\n' >&2
    exit 2
  fi
  compose_args=(--env-file "$environment_file" -f "$compose_file")
fi
# Refuse ambiguous or stopped source stacks instead of creating new volumes
# with a one-off Compose run. No credentials are printed.
docker compose "${compose_args[@]}" config --quiet
for service in postgres intelligence; do
  container_id="$(docker compose "${compose_args[@]}" ps --status running -q "$service")"
  if [[ -z "$container_id" ]]; then
    printf 'Backup blocked: selected %s service %s is not running\n' "$mode" "$service" >&2
    exit 1
  fi
  if [[ ! "$container_id" =~ ^[a-f0-9]{12,64}$ ]]; then
    printf 'Backup blocked: expected exactly one running container per source service\n' >&2
    exit 1
  fi
  if [[ "$service" == intelligence ]]; then
    intelligence_id="$container_id"
  fi
done
# Inspect the actual installed image, not a mutable tag or a Compose build.
intelligence_image="$(docker inspect --format '{{.Image}}' "$intelligence_id")"
if [[ ! "$intelligence_image" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  printf 'Backup blocked: installed intelligence image not identified\n' >&2
  exit 1
fi
mkdir -p "$backup_root"
if [[ -e "$final_dir" || -L "$final_dir" ]]; then
  printf 'Backup destination already exists; refusing overwrite\n' >&2
  exit 1
fi
work_dir="$(mktemp -d "$backup_root/.atlas-backup-${timestamp}.XXXXXX")"
intelligence_stopped=false

cleanup() {
  status=$?
  trap - EXIT
  if [[ "$intelligence_stopped" == "true" ]]; then
    if ! docker compose "${compose_args[@]}" start intelligence >/dev/null; then
      printf 'Backup interrupted: restart intelligence manually\n' >&2
      status=1
    fi
  fi
  if [[ -d "$work_dir" ]]; then
    rm -rf "$work_dir"
  fi
  exit "$status"
}
trap cleanup EXIT

docker compose "${compose_args[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$work_dir/postgres.dump"

# Quiesce SQLite and JSON state before streaming its named volumes.
intelligence_stopped=true
docker compose "${compose_args[@]}" stop intelligence >/dev/null
# Compose run has no portable --no-build option. Use the installed image ID
# and exact stopped source mounts, read-only, without network or env secrets.
docker run --rm --pull never --network none --volumes-from "$intelligence_id:ro" \
  --entrypoint python "$intelligence_image" -m app.ops_snapshot > "$work_dir/intelligence-state.tar.gz"
docker compose "${compose_args[@]}" start intelligence >/dev/null
intelligence_stopped=false

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$work_dir" && sha256sum postgres.dump intelligence-state.tar.gz > SHA256SUMS)
else
  (cd "$work_dir" && shasum -a 256 postgres.dump intelligence-state.tar.gz > SHA256SUMS)
fi

cat > "$work_dir/MANIFEST.txt" <<EOF
ATLAS $mode backup
created_at=$timestamp
contents=PostgreSQL custom dump plus quiesced intelligence state
classification=PRIVATE FINANCIAL RESEARCH DATA
restore_test_required=true
EOF

# Verify the exact artifacts while still in the private staging directory.
python3 "$repo_root/scripts/verify-production-backup.py" "$work_dir" >/dev/null
# Publish without clobbering or nesting under an existing backup directory.
python3 - "$work_dir" "$final_dir" <<'PY'
import os, sys
source, destination = sys.argv[1:]
if os.path.lexists(destination):
    raise SystemExit("Backup destination already exists")
os.rename(source, destination)
PY
trap - EXIT
printf 'Backup created at %s\n' "$final_dir"
printf 'Encrypt and copy it to a separate failure domain before considering it durable.\n'

