CREATE TABLE IF NOT EXISTS personal_holdings (
 id BIGSERIAL PRIMARY KEY,
 symbol VARCHAR(50) NOT NULL,
 asset_type VARCHAR(16) NOT NULL CHECK(asset_type IN ('EQUITY','MUTUAL_FUND')),
 quantity NUMERIC(20,6) NOT NULL CHECK(quantity>0),
 average_cost NUMERIC(20,6) NOT NULL CHECK(average_cost>=0),
 last_price NUMERIC(20,6) CHECK(last_price>=0),
 price_as_of TIMESTAMPTZ,
 notes VARCHAR(500),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(symbol,asset_type)
);
CREATE INDEX IF NOT EXISTS idx_personal_holdings_asset ON personal_holdings(asset_type);
