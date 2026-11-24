-- User-owned SIP instructions. This is planning state only: ATLAS does not
-- place orders or debit an account. Existing holdings and market data are
-- untouched.
CREATE TABLE mutual_fund_sip_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  scheme_code BIGINT NOT NULL,
  scheme_name TEXT NOT NULL,
  monthly_amount NUMERIC(20,2) NOT NULL CHECK(monthly_amount > 0),
  start_date DATE NOT NULL,
  next_installment_date DATE NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  notes VARCHAR(300),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id,scheme_code)
);

CREATE INDEX idx_mutual_fund_sip_plans_user_next
  ON mutual_fund_sip_plans(user_id,active,next_installment_date);
