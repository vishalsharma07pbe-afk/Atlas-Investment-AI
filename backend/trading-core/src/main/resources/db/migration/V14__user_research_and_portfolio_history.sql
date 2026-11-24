-- User-scoped research state and performance evidence. All additions are
-- non-destructive; existing holdings and provider data remain untouched.

CREATE TABLE saved_screeners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  name VARCHAR(80) NOT NULL,
  definition JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id,name)
);

CREATE TABLE watchlist_items (
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  instrument_id BIGINT NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(user_id,instrument_id)
);

CREATE TABLE user_alert_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  alert_type VARCHAR(30) NOT NULL CHECK(alert_type IN ('PRICE','NAV','NEWS','PORTFOLIO_CHANGE')),
  target_identifier VARCHAR(120) NOT NULL,
  condition JSONB NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id,name)
);

CREATE TABLE user_notification_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  alert_rule_id UUID REFERENCES user_alert_rules(id) ON DELETE SET NULL,
  event_type VARCHAR(40) NOT NULL,
  title VARCHAR(180) NOT NULL,
  message TEXT NOT NULL,
  source_code VARCHAR(60),
  source_reference TEXT,
  occurred_at TIMESTAMPTZ NOT NULL,
  read_at TIMESTAMPTZ,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(user_id,event_type,source_code,source_reference,occurred_at)
);
CREATE INDEX idx_user_notifications_unread
  ON user_notification_history(user_id,occurred_at DESC) WHERE read_at IS NULL;

CREATE TABLE portfolio_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  symbol VARCHAR(50) NOT NULL,
  asset_type VARCHAR(16) NOT NULL CHECK(asset_type IN ('EQUITY','MUTUAL_FUND','CASH')),
  transaction_type VARCHAR(20) NOT NULL CHECK(transaction_type IN ('BUY','SELL','DIVIDEND','FEE','DEPOSIT','WITHDRAWAL')),
  transaction_date DATE NOT NULL,
  quantity NUMERIC(20,6),
  unit_price NUMERIC(20,6),
  cash_amount NUMERIC(20,6) NOT NULL CHECK(cash_amount>=0),
  source_code VARCHAR(60) NOT NULL DEFAULT 'MANUAL',
  source_reference VARCHAR(180),
  notes VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(quantity IS NULL OR quantity>0),
  CHECK(unit_price IS NULL OR unit_price>=0)
);
CREATE INDEX idx_portfolio_transactions_user_date
  ON portfolio_transactions(user_id,transaction_date,id);

CREATE TABLE portfolio_valuation_snapshots (
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  valuation_date DATE NOT NULL,
  total_value NUMERIC(20,6) NOT NULL CHECK(total_value>=0),
  priced_positions INTEGER NOT NULL CHECK(priced_positions>=0),
  unpriced_positions INTEGER NOT NULL CHECK(unpriced_positions>=0),
  source_code VARCHAR(60) NOT NULL DEFAULT 'ATLAS_HOLDINGS',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(user_id,valuation_date)
);

