"""Fail-closed local ATLAS configuration check. Does not print credential values."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

TRUE = {"true", "1", "yes", "on"}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    password = values.get("POSTGRES_PASSWORD", "")
    if not password or password in {"replace_with_a_unique_random_password", "trading", "password", "changeme"}:
        errors.append("POSTGRES_PASSWORD must be a non-placeholder value")
    if values.get("APP_ENV", "local").lower() not in {"local", "development"}:
        errors.append("This check only approves local/development configuration")
    provider = values.get("MARKET_DATA_PROVIDER", "MANUAL_CSV").upper()
    auto = values.get("MARKET_DATA_AUTO_REFRESH", "false").lower() in TRUE
    feed = values.get("ATLAS_UPSTOX_FEED_ENABLED", "false").lower() in TRUE
    rights = values.get("MARKET_DATA_USAGE_RIGHTS_CONFIRMED", "false").lower() in TRUE
    entitlement = values.get("MARKET_DATA_ENTITLEMENT_CONFIRMED", "false").lower() in TRUE
    if (auto or feed or provider != "MANUAL_CSV") and not (rights and entitlement):
        errors.append("Automated/provider market data requires explicit rights and entitlement confirmation")
    if (auto or feed or provider != "MANUAL_CSV") and not values.get("UPSTOX_ACCESS_TOKEN", ""):
        errors.append("Automated/provider market data requires a locally configured access token")
    if provider not in {"MANUAL_CSV", "UPSTOX"}:
        errors.append("Unknown MARKET_DATA_PROVIDER")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local ATLAS configuration without exposing secrets")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    if not args.env_file.is_file():
        print("BLOCKED: local .env file not found")
        return 1
    errors = validate(parse_env(args.env_file))
    for error in errors:
        print(f"BLOCKED: {error}")
    if errors:
        return 1
    print("Local configuration gate passed. This does not verify provider entitlements, token validity, or production security.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
