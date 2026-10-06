"""``testo`` CLI package.

The Typer app lives in :mod:`testo_core.cli.app`; ``testo run`` delegates to
:class:`testo_core.services.cycle_run.CycleRunService` via :mod:`testo_core.cli.runner`.
The deprecated ``uqo`` alias (:mod:`testo_core.cli.deprecated`) forwards to the same app.
"""
