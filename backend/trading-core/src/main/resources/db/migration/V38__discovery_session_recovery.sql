-- Session-aware recovery; legacy attempt state and cooldowns are retained.
ALTER TABLE discovery_history_attempts ADD COLUMN target_session DATE;
ALTER TABLE discovery_history_attempts ADD COLUMN claim_token UUID;
