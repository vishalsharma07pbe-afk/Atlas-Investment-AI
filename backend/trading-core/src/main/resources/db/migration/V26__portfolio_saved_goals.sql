CREATE TABLE portfolio_saved_goals (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 10),
  name VARCHAR(80) NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
  target_amount NUMERIC(12,2) NOT NULL CHECK (target_amount > 0 AND target_amount <= 1000000000),
  reserved_amount NUMERIC(12,2) NOT NULL CHECK (reserved_amount >= 0 AND reserved_amount <= 1000000000),
  balance_date DATE NOT NULL,
  deadline DATE NOT NULL,
  monthly_contribution NUMERIC(10,2) NOT NULL CHECK (monthly_contribution >= 0 AND monthly_contribution <= 10000000),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id,slot)
);
