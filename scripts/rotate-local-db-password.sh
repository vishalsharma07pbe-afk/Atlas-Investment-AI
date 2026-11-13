#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$project_dir/.env"
backup_dir="$project_dir/backups"

if [ ! -f "$env_file" ]; then
  echo "Missing .env. Copy .env.example first." >&2
  exit 1
fi

mkdir -p "$backup_dir"
chmod 600 "$env_file"
db_name=$(sed -n 's/^POSTGRES_DB=//p' "$env_file")
db_user=$(sed -n 's/^POSTGRES_USER=//p' "$env_file")
stamp=$(date +%Y%m%d_%H%M%S)
backup_file="$backup_dir/atlas_before_password_rotation_$stamp.dump"

docker compose -f "$project_dir/docker-compose.yml" exec -T postgres pg_dump -U "$db_user" -d "$db_name" -Fc > "$backup_file"

new_password=$(openssl rand -base64 36 | tr -dc 'A-Za-z0-9_-' | cut -c1-40)
escaped_password=$(printf '%s' "$new_password" | sed "s/'/''/g")
docker compose -f "$project_dir/docker-compose.yml" exec -T postgres psql -X -U "$db_user" -d "$db_name" -v ON_ERROR_STOP=1 -c "ALTER ROLE \"$db_user\" PASSWORD '$escaped_password'" >/dev/null

tmp_file="$env_file.tmp.$stamp"
awk -v password="$new_password" 'BEGIN{done=0} /^POSTGRES_PASSWORD=/{print "POSTGRES_PASSWORD=" password;done=1;next} {print} END{if(!done) print "POSTGRES_PASSWORD=" password}' "$env_file" > "$tmp_file"
chmod 600 "$tmp_file"
mv "$tmp_file" "$env_file"

echo "Database password rotated and .env updated. Backup: $backup_file"
echo "Restart services with: docker compose up -d --force-recreate postgres backend"
