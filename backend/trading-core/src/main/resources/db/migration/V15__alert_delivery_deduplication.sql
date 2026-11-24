-- In-app alert delivery state. External channels remain opt-in integrations.
ALTER TABLE user_notification_history
  ADD COLUMN dedupe_key VARCHAR(180),
  ADD COLUMN delivery_channel VARCHAR(20) NOT NULL DEFAULT 'IN_APP',
  ADD COLUMN delivery_status VARCHAR(20) NOT NULL DEFAULT 'DELIVERED';

ALTER TABLE user_notification_history
  ADD CONSTRAINT ck_user_notification_delivery_channel
    CHECK(delivery_channel IN ('IN_APP','EMAIL','PUSH')),
  ADD CONSTRAINT ck_user_notification_delivery_status
    CHECK(delivery_status IN ('PENDING','DELIVERED','FAILED'));

CREATE UNIQUE INDEX uq_user_notification_dedupe
  ON user_notification_history(user_id,dedupe_key)
  WHERE dedupe_key IS NOT NULL;

