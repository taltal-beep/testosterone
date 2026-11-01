# pytest-testo

Record every pytest run and see **what broke, what's flaky and what got slower** since the last one.

```bash
pip install pytest-testo
pytest --testo          # records this run in the local history (SQLite)
testo flaky --cycle my-project   # the cycle defaults to the project folder's name
pip install 'testo-core[api]' && testo ui    # the web UI on that history
```

This package installs [testo-core](https://pypi.org/project/testo-core/) (Testosterone), which
provides the pytest plugin. Installing `testo-core` directly gives you exactly the same thing; this
name exists so the plugin shows up next to the other `pytest-*` plugins.

`pytest --testo-affected` runs only the tests a change can affect, and `pytest --testo-shard 1/4`
splits the suite by recorded test time. All options:
[pytest --testo](https://taltal-beep.github.io/testosterone/docs/cli-commands/command-reference/#pytest-testo).

No install at all: drop a JUnit XML file on <https://taltal-beep.github.io/testosterone/try>.

Source, issues and docs: <https://github.com/taltal-beep/testosterone>. MIT licensed.
