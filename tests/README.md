## Running the test suite with Allure

```bash
python scripts/write_allure_environment.py
pytest -q --alluredir=allure-results/pytest
```

Notes:
- Integration/E2E/Contract tests automatically attach the last HTTP request/response on failure.
- All tests are auto-labeled into Allure `feature/story/title` based on their location under `tests/`.

