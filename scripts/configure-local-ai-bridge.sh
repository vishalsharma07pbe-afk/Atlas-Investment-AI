#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$project_dir/.env"

if [ ! -f "$env_file" ]; then
  echo "Missing .env. Copy .env.example first." >&2
  exit 1
fi

existing=$(sed -n 's/^INTERNAL_SERVICE_TOKEN=//p' "$env_file" | head -n 1)
if [ ${#existing} -ge 32 ]; then
  secret=$existing
else
  secret=$(openssl rand -base64 48 | tr -d '\n')
fi

stamp=$(date +%Y%m%d_%H%M%S)
tmp_file="$env_file.tmp.$stamp"
awk -v token="$secret" '
  BEGIN{token_done=0;proxy_done=0}
  /^INTERNAL_SERVICE_TOKEN=/{print "INTERNAL_SERVICE_TOKEN=" token;token_done=1;next}
  /^ATLAS_AI_PROXY_ENABLED=/{print "ATLAS_AI_PROXY_ENABLED=true";proxy_done=1;next}
  {print}
  END{
    if(!proxy_done) print "ATLAS_AI_PROXY_ENABLED=true"
    if(!token_done) print "INTERNAL_SERVICE_TOKEN=" token
  }
' "$env_file" > "$tmp_file"
chmod 600 "$tmp_file"
mv "$tmp_file" "$env_file"

echo "ATLAS AI bridge enabled with a protected internal token in local .env."
