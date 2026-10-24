---
name: unit_test_runner
description: Automated test runner and failure diagnosis for Python (pytest), Rust (cargo test), and Node/TS (npm test / jest).
category: Coding
autonomy_required: LEVEL_1
parameters: framework:string:Test framework (pytest, cargo, npm, jest), workdir:string:Project root directory, test_target:string:Specific test file or module to run, extra_flags:string:Additional flags (e.g. -v, --nocapture)
tags: [testing, pytest, cargo, jest, npm, code, verification, diagnostics]
---

# Automated Unit Test Runner & Diagnostics

This skill executes unit and integration test suites across multiple languages, captures failure logs, and diagnoses root causes for failed assertions.

## Supported Frameworks & Command Patterns

1. **Python (`pytest`)**:
   - Command: `pytest {test_target} {extra_flags} --tb=short` in `{workdir}`.
   - Parses summary line (`X failed, Y passed in Zs`) and extracts short tracebacks for failures.

2. **Rust (`cargo test`)**:
   - Command: `cargo test {test_target} -- {extra_flags}` in `{workdir}`.
   - Captures compiler errors, panics, and assertion mismatches.

3. **JavaScript / TypeScript (`npm test` / `jest`)**:
   - Command: `npm test -- {test_target} {extra_flags}` or `npx jest {test_target} {extra_flags}` in `{workdir}`.
   - Extracts failing test names and stack traces.

## Diagnostic Workflow
1. **Execute Tests**: Run the specified test suite within the sandboxed environment or host workspace.
2. **Analyze Results**:
   - If all tests pass: Return a clean success summary with execution time and test counts.
   - If tests fail: Isolate the exact failing file, function name, line number, and assertion error message.
3. **Generate Fix Recommendations**:
   - Provide actionable code snippets or hypotheses explaining why the test failed based on the stack trace.

## Output Format
Return markdown with:
- Status badge: `[PASS]` or `[FAIL]`
- Summary statistics table (Total, Passed, Failed, Skipped, Duration)
- Collapsible details or highlighted code blocks for failing test stack traces
