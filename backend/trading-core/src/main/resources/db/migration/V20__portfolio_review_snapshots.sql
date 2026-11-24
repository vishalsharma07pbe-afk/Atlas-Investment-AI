-- Owner-scoped derived research cache; no position or transaction changes.
CREATE TABLE portfolio_review_snapshots (
  user_id UUID PRIMARY KEY REFERENCES atlas_users(id) ON DELETE CASCADE,
  holdings_revision TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  result JSONB NOT NULL
);
