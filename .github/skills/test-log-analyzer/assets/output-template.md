# Chat Response Template — Test Log Analyzer

## Key findings:

- **Total parts:** {{total_parts}}
- **Yield:** {{yield_percent}}%
- **Passing parts:** {{passing_parts}}
- **Failing parts:** {{failing_parts}}
- **Total failed test events:** {{failed_test_events}}
- **Top failing tests:**
{{top_failing_tests_bullets}}
- **Most failure-heavy sites:**
{{site_failure_bullets}}
---

## Placeholder guidance

### `{{top_failing_tests_bullets}}`
Use nested bullets, for example:

```md
  - Coff_RF1_1880M — 4 failures
  - Cont_A1_to_GND — 4 failures
  - Roff_DC_RF1_AOFF — 4 failures
```

### `{{site_failure_bullets}}`
Use nested bullets, for example:

```md
  - Site 9: 6 failures
  - Site 6: 4 failures
  - Site 7: 4 failures
  - Site 8: 4 failures
```