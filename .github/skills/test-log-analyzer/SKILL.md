\
---
name: test-log-analyzer
description: Analyze semiconductor .std / .stdf test logs and return a strict, repeatable summary directly in chat. Use this skill for total parts, yield, passing parts, failing parts, top failing tests, top failing sites, and failed-coordinate pattern analysis.
license: Apache-2.0
compatibility: Requires python3, pandas, and pystdf.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.4.0"
  domain: semiconductor-test
  input-formats:
    - std
    - stdf
  output-format: chat-only
---

# Test Log Analyzer

## Purpose
This skill reads a semiconductor STD / STDF file and returns a short, structured summary directly in chat.

## When to use
Use this skill when the task is to:
- analyze a `.std` or `.stdf` file
- calculate total parts, passing parts, failing parts, and yield
- rank top failing tests
- rank top failing sites
- analyze failed coordinates to determine whether failures are concentrated in a specific location or scattered

## Input
Expected input:
- a valid `.std` or `.stdf` file path

Example:
```text
C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\Mobile Device Test_10Jun2026_1458.std
```

## Required output
Return the final answer **only in chat**.

The answer must contain only these items:
- Total parts
- Yield
- Passing parts
- Failing parts
- Top failing tests
- Top failing sites
- Failed coordinate pattern analysis

## Strict output rules
Do **not** generate any output files.
Do **not** generate:
- `*_summary.md`
- `*_summary.json`
- `*.csv`

Do **not** add extra sections outside the template.
Do **not** return a free-form summary.

## Output contract
Before answering, always read `output-template.md`.
The final chat reply must follow `output-template.md` exactly.

If a value is unavailable, keep the section and write `N/A`.

## Workflow
1. Read the input `.std` / `.stdf` file.
2. Parse the relevant records.
3. Extract:
   - part result information
   - site number information
   - test number / test name information
   - fail status information
   - coordinate information if available
4. Compute:
   - total parts
   - passing parts
   - failing parts
   - yield
   - top failing tests
   - top failing sites
5. Analyze failed coordinates:
   - determine whether failures are concentrated at one / a few coordinates
   - or whether failing coordinates are scattered
6. Return the response in chat using `output-template.md`.

## Behavior rules
- Keep the answer short and structured.
- Use the exact section names from `output-template.md`.
- Do not add optional closing suggestions.
- Do not add file-save messages.
- Do not mention generating reports.
- Coordinate analysis must clearly state whether failures are concentrated or scattered.
- If coordinates are missing, explicitly say that coordinate analysis is unavailable.

## Success criteria
A good result must:
- correctly calculate total parts
- correctly calculate yield
- correctly calculate passing parts and failing parts
- correctly rank top failing tests
- correctly rank top failing sites
- clearly state whether failing coordinates are concentrated or scattered
- always follow the same chat structure defined in `output-template.md`
