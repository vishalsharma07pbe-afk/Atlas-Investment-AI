-- V7: owner claims are explicit; no invented/default identity.
-- New installations get an enforced owner FK. Legacy installations with orphans
-- fail migration until ATLAS_CLAIM_LEGACY_OWNER_EMAIL has been applied by the
-- pre-migration operator command. This prevents accidental cross-user assignment.
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM personal_holdings WHERE user_id IS NULL) THEN
   RAISE EXCEPTION 'Unclaimed legacy holdings. Run explicit owner-claim command before V7.';
 END IF;
END $$;
ALTER TABLE personal_holdings ALTER COLUMN user_id SET NOT NULL;
