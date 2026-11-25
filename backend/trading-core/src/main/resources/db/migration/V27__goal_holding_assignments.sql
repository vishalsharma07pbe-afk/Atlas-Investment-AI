-- Preserve missing holding assignments as evidence gaps.
ALTER TABLE portfolio_saved_goals ADD CONSTRAINT portfolio_goal_owner_identity UNIQUE(user_id,id);
CREATE TABLE portfolio_goal_holdings (
  user_id UUID NOT NULL,
  goal_id UUID NOT NULL,
  holding_id BIGINT NOT NULL,
  symbol VARCHAR(50) NOT NULL,
  asset_type VARCHAR(20) NOT NULL CHECK (asset_type IN ('EQUITY','MUTUAL_FUND')),
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(user_id,holding_id),
  FOREIGN KEY(user_id,goal_id) REFERENCES portfolio_saved_goals(user_id,id) ON DELETE CASCADE
);
CREATE INDEX portfolio_goal_holdings_goal_idx ON portfolio_goal_holdings(user_id,goal_id);
