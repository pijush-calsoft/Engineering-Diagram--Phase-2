"""Block 8: Insight and report, fact-checked descriptive report with DOCX export (plan Phase 6)."""

from edp_b8_report.block import InsightReport
from edp_b8_report.compose import compose
from edp_b8_report.factcheck import RunStore, check, fmt

__all__ = ["InsightReport", "RunStore", "check", "compose", "fmt"]
