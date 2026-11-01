# __DIST__

A Testosterone plugin written by `testo plugins new __NAME__`: a framework adapter (`equipment: __NAME__`) and a reporter (`type: __NAME__-summary`).

```bash
pip install -e .
testo plugins --check        # __NAME__ and __NAME__-summary are listed, status ok
testo run --cycle unit       # runs tests/ through the plugin; reports/summary.json written
python -m unittest           # the plugin's own check
```

- `pyproject.toml` registers both through the `testo.frameworks` and `testo.reporters` entry point groups.
- `__MODULE__/__init__.py` has the adapter (`build_argv` returns the command to run) and the reporter (`publish` gets the collected results).
- `__MODULE__/runner.py` runs unittest and writes one Allure `*-result.json` per test. Replace it with your runner: that file format is all Testosterone needs to count, diff and track the tests.

Plugin interface: https://taltal-beep.github.io/testosterone/docs/cli-commands/command-reference/#plugins
