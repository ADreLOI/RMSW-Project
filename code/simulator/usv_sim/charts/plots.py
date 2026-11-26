"""Publication exports for a paired exploratory mission (no inferential intervals)."""
from .figures import paired_mission
from .plotstyle import save


def export_figures(destination, rows):
    save(paired_mission(rows), destination, "paired-mission", ("png", "pdf", "svg"))
