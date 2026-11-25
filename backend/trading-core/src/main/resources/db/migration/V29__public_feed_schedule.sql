CREATE TABLE public_feed_schedule(
 provider VARCHAR(20) PRIMARY KEY CHECK(provider IN ('UPSTOX','AMFI')),
 status VARCHAR(20) NOT NULL DEFAULT 'IDLE' CHECK(status IN ('IDLE','RUNNING','RETRY','SUCCESS','FAILED')),
 attempts INT NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 5),
 interruptions INT NOT NULL DEFAULT 0 CHECK(interruptions>=0),
 claim_id UUID,
 lease_until TIMESTAMPTZ,
 last_attempt_at TIMESTAMPTZ,
 last_success_at TIMESTAMPTZ,
 next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 error_code VARCHAR(60),
 CHECK((status='RUNNING' AND claim_id IS NOT NULL AND lease_until IS NOT NULL)
    OR (status<>'RUNNING' AND claim_id IS NULL AND lease_until IS NULL))
);
ALTER TABLE market_provider_runs ADD COLUMN claim_id UUID;
CREATE UNIQUE INDEX uq_public_feed_run_claim ON market_provider_runs(claim_id) WHERE claim_id IS NOT NULL;
INSERT INTO public_feed_schedule(provider) VALUES ('UPSTOX'),('AMFI');
UPDATE public_feed_schedule s SET status='RETRY'
 WHERE EXISTS(SELECT 1 FROM market_provider_runs r WHERE r.provider=s.provider
   AND r.job_name IN ('MASTER','MASTER_AUTO','NAV','NAV_AUTO') AND r.status IN ('RUNNING','RETRY'));
UPDATE market_provider_runs SET status='FAILED',finished_at=now(),error_message='LEGACY_RETRY_SUPERSEDED'
 WHERE provider IN ('UPSTOX','AMFI') AND job_name IN ('MASTER','MASTER_AUTO','NAV','NAV_AUTO')
   AND status IN ('RUNNING','RETRY');
