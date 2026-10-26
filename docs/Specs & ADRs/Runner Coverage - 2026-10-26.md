---
type: spec
status: current
created: 2026-10-26
updated: 2026-10-26
---

# Runner Coverage - 2026-10-26

## Context

A coverage review (2026-10-26) estimated that Testosterone supported about 23% of test framework usage natively (pytest, Behave/BehaveX, Playwright) and could record about 94% through JUnit XML. A third of that 94% needed an extra reporter package first (`jest-junit`, a .NET JUnit logger, `gotestsum`, ...), and JUnit drops what the runner knew: `describe` blocks, retries, files that failed before any test ran, tags. The aim is for Testosterone to be the default results history for any test tool, so the common runners should work with the output they already write, with no extra install.

## Decision

`testo_core/reporting/junit_import.py` stays the one entry for every result file (stage `junit_xml` globs, `testo ingest`, `POST /api/v1/ingest`). It now recognises a file by its **content**, not its name, and hands it to that runner's importer. Each importer writes the same Allure result dicts, so nothing after the import changes.

| File | Written by | Importer |
|------|-----------|----------|
| JUnit XML (`<testsuite>` / `<testsuites>`, and any other XML) | most runners | `junit_import.py` |
| Playwright JSON (`suites` list) | `--reporter=json` | `playwright_import.py` |
| Jest / Vitest JSON (`testResults` list) | `jest --json`, `vitest --reporter=json` | `jest_import.py` |
| TRX (`<TestRun>`) | `dotnet test --logger trx` (xUnit, NUnit, MSTest) | `trx_import.py` |
| `go test -json` lines (`Action` / `Package` events) | `go test -json` | `gotest_import.py` |
| Robot Framework `output.xml` (`<robot>`) | `robot` | `robot_import.py` |
| Allure `*-result.json` | any Allure adapter | `allure_passthrough.py` |

- **Identity.** Each importer builds a stable `fullName`: `file › describe › title` for Jest/Vitest (paths relative to the repo, or to the report's common folder when made elsewhere), `Namespace.Class.Method` for TRX, `package.Test/subtest` for Go, Robot's long name. These are also the names the runners' own "run only this test" options take, which later rerun commands rely on.
- **What JUnit lost.** A Jest test that passed on retry is flaky; a test file that failed to load is one `broken` result; TRX data rows are one result each; a failed Go package with no failing test (build error) is one `broken` result; a Go parent test counts only when it failed on its own, so a failing subtest is not counted twice; Robot tags become Allure tags.
- **Allure folders.** `testo ingest allure-results/` (a folder argument stands for its files) copies each result with the attachments it names, from the same folder only. Containers and the folder's settings files are skipped without a warning.
- **Server uploads.** `POST /api/v1/ingest` keeps a file's safe name and suffix (an Allure result names its attachments by file name) and reads every stored file by content.
- Unknown files are skipped with a note in the stage log, as malformed JUnit always was. They never fail the stage on their own.

## Consequences

- Jest, Vitest, .NET, Go and Robot suites can be recorded with the output their runner writes by default. JUnit XML keeps working for everything else.
- Detection reads each file once more than before (a sniff, then the parse). Result files are small next to the test run.
- `historyId` still hashes the stage's tool with `fullName`, so moving a suite from JUnit XML to its runner's own format starts a new history for its tests (different names).
- Allure containers (fixtures) are not shown; Testosterone has no place for them.

Builds on [Command Adapter and JUnit Import](Command%20Adapter%20and%20JUnit%20Import%20-%202026-09-25.md), [Playwright JSON Import](Playwright%20JSON%20Import%20-%202026-10-22.md) and [Ingest and Team Server](Ingest%20and%20Team%20Server%20-%202026-10-22.md).
