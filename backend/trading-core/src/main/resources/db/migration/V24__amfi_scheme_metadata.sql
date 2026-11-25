-- Preserve explicit official plan/option evidence independently of names.
ALTER TABLE mutual_fund_schemes ADD COLUMN amfi_plan TEXT;
ALTER TABLE mutual_fund_schemes ADD COLUMN amfi_option TEXT;
ALTER TABLE mutual_fund_schemes ADD COLUMN amfi_metadata_date DATE;
