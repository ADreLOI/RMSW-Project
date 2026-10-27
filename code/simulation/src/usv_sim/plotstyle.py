"""One publication style for every matplotlib figure (report, run bundles, dashboard).

Colours come from web/tokens.css so the browser and the paper share one palette.
Type follows the LaTeX report (Computer Modern, 11 pt article class).
"""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TOKENS = Path(__file__).parent / "web" / "tokens.css"
DPI = 300
COLUMN_IN = 6.5  # \textwidth of the report on A4 with standard margins
MARKERS = {"S1": "s", "S2": "v", "S3": "D", "S4-T": "o", "S4-P": "^", "S4-E": "P",
           "S4-K": "X", "S4-G": "h", "S4-L": "<", "S4-M": ">", "S4-O": "*"}
CENSORED_NOTE = "Open marker: at least one run censored at the 7200 s cutoff"


def tokens(path=TOKENS):
    """CSS custom properties with literal hex values, e.g. {"policy-S1": "#64748b"}."""
    text = Path(path).read_text(encoding="utf-8")
    return {name: value.lower() for name, value in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", text)}


_TOKENS = tokens()
COLORS = {name.removeprefix("policy-"): value for name, value in _TOKENS.items() if name.startswith("policy-")}
USV = (_TOKENS["usv-1"], _TOKENS["usv-2"])
INK, MUTED, GRID, DANGER, WARNING = (_TOKENS[k] for k in ("foreground", "muted-foreground", "border", "danger", "warning"))

RC = {
    "font.family": "serif",
    "font.serif": ["cmr10", "Computer Modern Roman", "CMU Serif", "DejaVu Serif"],
    "mathtext.fontset": "cm",
    "axes.formatter.use_mathtext": True,  # cmr10 has no Unicode minus
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "legend.frameon": False,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "xtick.color": INK,
    "ytick.color": INK,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "lines.linewidth": 1.1,
    "lines.markersize": 3.6,
    "errorbar.capsize": 2,
    "figure.dpi": 100,
    "savefig.dpi": DPI,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
}


@contextmanager
def paper():
    """Temporarily apply the publication style without leaking global state."""
    with plt.rc_context(RC):
        yield


def save(fig, folder, stem, formats=("png", "pdf")):
    """Write the figure as <stem>.<ext> and close it; PNGs use 300 dpi."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(RC):
        for extension in formats:
            fig.savefig(folder / f"{stem}.{extension}", dpi=DPI)
    plt.close(fig)


def png_bytes(fig):
    stream = BytesIO()
    with plt.rc_context(RC):
        fig.savefig(stream, format="png", dpi=DPI)
    plt.close(fig)
    return stream.getvalue()
