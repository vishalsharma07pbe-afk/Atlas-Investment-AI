#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$project_dir/.env"

if [ ! -f "$env_file" ]; then
  echo "Missing .env. Copy .env.example first." >&2
  exit 1
fi

if sed -n 's/^ATLAS_JWT_SECRET=//p' "$env_file" | grep -q .; then
  echo "ATLAS_JWT_SECRET is already configured; no change made."
  exit 0
fi

secret=$(openssl rand -base64 48 | tr -d '\n')
stamp=$(date +%Y%m%d_%H%M%S)
tmp_file="$env_file.tmp.$stamp"

awk -v value="$secret" 'BEGIN{done=0} /^ATLAS_JWT_SECRET=/{print "ATLAS_JWT_SECRET=" value;done=1;next} {print} END{if(!done) print "ATLAS_JWT_SECRET=" value}' "$env_file" > "$tmp_file"
chmod 600 "$tmp_file"
mv "$tmp_file" "$env_file"

echo "ATLAS_JWT_SECRET generated and stored in the protected local .env file."
