ALTER TABLE upstox_instrument_map
  ADD COLUMN IF NOT EXISTS display_name TEXT;

CREATE INDEX IF NOT EXISTS idx_upstox_search_display_name
  ON upstox_instrument_map(lower(display_name) text_pattern_ops);
