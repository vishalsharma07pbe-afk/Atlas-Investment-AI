# Investment Analyst: release and acceptance

The overview now exposes a public investment analyst read model over existing current research. It uses separate evidence tiers rather than presenting incomplete observations as fully qualified investments.

- The model committee reuses the existing automatic AI permission, provider ordering, budget and cache mechanism. It reviews up to six stock candidates and three funds per core category per evidence set, one configured provider per scheduled pass. Only public typed fields and evidence-bound decision/rationale codes are sent; no owner data, raw model prose, trade commands, or forecasts are retained. Disagreement or a defer judgment downgrades the research priority. No model vote promotes a strict qualification.
- Growth scenarios reuse current exact-company quarterly earnings persistence and covered original fund weight. These are uncalibrated business scenarios, not price targets, future NAV returns or consensus forecasts.
- Evidence confidence is a categorical research-coverage rubric, not the probability of a profitable investment. Historical risk and illustrative price geometry are separate.
- Owner-local capital planning uses the authenticated portfolio review and public report already available to the UI. No private owner data enters the external model committee. The user supplies surplus capital, horizon and risk tolerance. Illustrative allocation caps and cash reserves are conservative defaults, not personalized suitability certification. Existing holdings and deferred opportunities are not automatically repurchased, and historical matched comparisons do not instruct a switch.
- Model cache failures retain deterministic research. All existing strict eligibility, export, broker and provider permissions remain unchanged.

## Local verification after exact-head CI is green

Use the approved branch/merge and existing protected backup and Compose deployment process; do not reset volumes. Open the overview and the capital planner while signed in, review actual stocks and large/mid/small-cap funds, and open Portfolio Doctor for per-holding actions. Enter only surplus investable capital and compare the reserved/allocated amounts. Verify that model disagreements and missing evidence restrict conclusions, and that owner-specific data is not forwarded externally.

Run:

```bash
python3 scripts/local_research_acceptance.py --investment-analyst-audit --qualification-audit --advanced-audit --recovery-audit
```

For a positive-output acceptance observation also run with `--require-analyst-results`. That requires actual current stock and all three core fund decision lists plus at least one cached model review. It is not a reason to fabricate a candidate when none exists. Use `--require-live` only during a verified live market session. The script emits aggregate counts and does not report private identifiers. Confirm actual model provider permission and availability locally.

The implementation and mocked provider tests do not certify market data coverage, model quality, prospective investment outcomes or actual populated local acceptance. These remain separately verified release criteria.
