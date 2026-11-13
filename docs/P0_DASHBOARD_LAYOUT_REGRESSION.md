# P0 Dashboard layout regression checklist

This change addresses the user-reported Mac desktop defects: inline form labels, controls overlapping adjacent fields, inconsistent widths, and sidebar navigation disappearing on long pages.

## Automated checks

Run `npm --prefix frontend/trading-dashboard run build` and `npm --prefix frontend/trading-dashboard test -- --run`. CI must pass before merge.

## Manual browser acceptance (required before calling the UX issue resolved)

1. Open the local dashboard at 1440x900, 1280x800, 1024x768, and 390x844 viewport sizes.
2. Scroll a long research/planning page. On desktop, sidebar remains visible and its navigation scrolls independently when too tall. On mobile, navigation remains horizontally scrollable.
3. Check Research Journal, Fees & Compounding, Allocation Planner, Goal Planner, Scenario Comparison, and Stock Explorer: no overlapping labels/fields, no horizontal page overflow, all submit controls reachable.
4. Tab through fields: focus indicator visible, textareas resizable, numeric and select controls remain usable.
5. Verify dark/light and appearance settings at 0%, 50%, and 100% panel opacity.
6. Confirm that empty stock registry is clearly communicated rather than represented as live data.

**Scope:** CSS layout only; no market data, broker access, API behavior, or database records changed. A successful CI build does not replace manual visual verification on the user's Mac.
