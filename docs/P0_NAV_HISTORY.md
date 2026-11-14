# P0 Mutual Fund NAV reliability: local historical observations

This module extends existing manual AMFI snapshot imports to preserve each scheme's distinct dated NAV in a local SQLite history table. Duplicate (scheme_code, nav_date) rows are ignored. Each import writes an audit record with the number of inserted history rows and invalid rows.

- GET /api/v1/intelligence/mutual-funds/{scheme_code}/history?limit=365
- GET /api/v1/intelligence/mutual-funds/import-audit?limit=20

The history API returns **observed-period** percentage return only when at least two imported observations exist. This is not annualized, distribution-adjusted, or independently verified. Ratings are null unless a licensed ratings source is integrated.

Important: this is NOT automatic NAV collection, a streaming feed, a verified rating service or a replacement for provider permissions. Existing local installs migrate automatically on the first catalog access; existing latest-only snapshots cannot be reconstructed as history. No broker tokens or order execution.
