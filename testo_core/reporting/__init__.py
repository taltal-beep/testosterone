"""Post-execution reporting: collect → generate → serve / export.

Only the CLI's ``testo report`` command depends on this module.  The runtime
engine writes raw ``allure-results/`` only; HTML and any UI is produced on
demand here.
"""

from testo_core.reporting.collector import CollectedResults, collect_results
from testo_core.reporting.entry import dispatch_report

__all__ = ["CollectedResults", "collect_results", "dispatch_report"]
