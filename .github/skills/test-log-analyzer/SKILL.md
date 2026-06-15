---
name: test-log-analyzer
description: Analyze semiconductor .std / .stdf test logs and return a concise engineering summary directly in chat. Use this skill for std file analysis, yield review, fail count analysis, top failing tests ranking, site-based failure patterns, and first-pass root-cause guidance.
license: Apache-2.0
compatibility: Requires python3, pandas, and pystdf.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.3.0"
  domain: semiconductor-test
  input-formats:
    - std
    - stdf
  primary-output: chat-summary
---

# Test Log Analyzer

## Purpose
This skill reads a semiconductor test log file and returns a practical engineering summary directly in chat.

## When to use
Use this skill when the task is to:
- analyze a `.std` or `.stdf` file
- calculate yield
- count failures
- rank top failing tests
- identify site-based failure concentration
- suggest likely issue areas and where to check first

## Input
Expected input:
- a valid `.std` or `.stdf` file path

Example:
```text
C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\Mobile Device Test_10Jun2026_1458.std
```

## Required outputs
This skill must return the result **in chat**.

Primary output in chat:
- key findings
- top failing tests
- most failure-heavy sites
- interpretation of likely issues

## Mandatory response rule
Before answering, always read `output-template.md`.

The final response in chat must follow `output-template.md` exactly.

Do not:
- change section names
- invent alternative headings
- reorder sections
- add extra sections
- add optional suggestions outside the template
- output a free-form summary instead of the template

If some values are unavailable, keep the section and write `N/A`.


## Strict output rule
Do **not** generate these report files:
- `*_summary.md`
- `*_summary.json`


The answer must be:
- written directly in chat
- short
- structured
- engineer-friendly
- focused on action


## Final output contract
The assistant must return the final answer in chat using `output-template.md` as a strict format contract.

This is mandatory.

The assistant must not return:
- a custom summary style
- renamed sections
- additional sections
- optional recommendations outside the template
- alternative bullet layouts

The assistant must fill the placeholders from the parsed test results and return only that formatted response.


## Workflow
1. Read the input `.std` / `.stdf` file.
2. Parse available test records.
3. Extract useful data such as:
   - part ID
   - site number
   - test number / test name
   - measured result
   - limits
   - fail status
   - hard bin / soft bin if available
4. Compute:
   - total parts tested
   - passing part count
   - failing part count
   - yield %
   - total failed test events
   - top failing tests
   - site-based fail concentration
5. Interpret the result.
6. Return the summary directly in chat using `output-template.md`.
7. Generate only a normalized `.csv` file when needed.

## Interpretation rules
Do not return only counts.
Always return:
- interpretation
- likely issue direction
- first validation steps
- practical suggestions

Examples of expected reasoning:
- If failures are concentrated on one site, suggest a possible socket/contact/loadboard/site hardware issue.
- If one test dominates failures, suggest checking limits, test method, recent program changes, and instrument setup.
- If failures are spread across all sites, suggest checking common rails, shared instruments, environment, or process/product conditions.
- If yield is still high but failures are concentrated, explain that the issue may be localized rather than systemic.

## Behavior rules
- Focus on the most important failure trends.
- Do not dump raw records unless requested.
- Do not create any markdown or JSON summary report files.
- Always provide interpretation, not only raw counts.
- Always explain what looks suspicious.
- Always say where the user should check first.
- Always suggest next actions or improvements.
- If data is incomplete, still provide the best first-pass engineering assessment.
- If parsing dependencies are missing, report the missing package clearly.
- Format the answer with bullets and short sections, not long paragraphs.
- Keep the `Key findings` section concise and easy to scan.

## Quality rules
A poor response is:
- `Site 9: 6 failures`

A good response continues with reasoning such as:
- whether Site 9 dominates the fail population
- whether this suggests a site hardware issue or a broader problem
- whether the user should inspect socket/contact/loadboard/instrument path first
- whether the dominant failing tests suggest a setup/test-method issue instead of a DUT issue
- what should be checked first and what should be improved next

## Success criteria
A good result must:
- correctly calculate yield
- correctly count failed events
- correctly rank top failing tests
- clearly summarize the key findings in chat
- clearly summarize site-related fail patterns
- provide useful first-pass root-cause guidance
- tell the user what to verify first
- suggest actionable next steps
- return the summary in chat only
- generate only the normalized `.csv` file if file output is needed