import matplotlib.pyplot as plt

# --- Physical Size (inches) ---
# Assumes 1:1 usage in LaTeX with \includegraphics[width=\columnwidth]{...}.
# This ensures no scaling occurs and specified pt sizes are printed as-is.
FIGSIZE_DOUBLE = (4.5, 3.0)  # For two figures side-by-side
FIGSIZE_TRIPLE = (3.5, 3.0)  # For three figures side-by-side
FIGSIZE_WIDE = (14.0, 4.0)  # For two-column wide (CPU/node comparison)
# For two figures side-by-side within LNCS single-column text width
# (each minipage is 0.48 * 12.2 cm ~= 2.3 in; used 1:1, no LaTeX scaling)
FIGSIZE_HALF = (2.3, 1.68)
DPI = 300

# --- Font Size (DOUBLE: two figures side-by-side) ---
FONT_DOUBLE = {
    "label": 14,
    "tick": 12,
    "title": 16,
    "annot": 9,
    "legend": 14,
}

# --- Font Size (TRIPLE: three figures side-by-side) ---
FONT_TRIPLE = {
    "label": 14,
    "tick": 12,
    "title": 12,
    "annot": 14,
    "legend": 14,
}

# --- Font Size (HALF: two figures side-by-side in LNCS single column) ---
FONT_HALF = {
    "label": 9,
    "tick": 8,
    "title": 10,
    "annot": 7,
    "legend": 8,
}

# --- Font Size (WIDE: two-column wide) ---
FONT_WIDE = {
    "label": 18,
    "tick": 14,
    "title": 18,
    "annot": 18,
    "legend": 18,
}

# Backward compatibility: default values for existing scripts that reference FONT_LABEL, etc. directly
# (DOUBLE is used as default)
FONT_LABEL = FONT_DOUBLE["label"]
FONT_TICK = FONT_DOUBLE["tick"]
FONT_TITLE = FONT_DOUBLE["title"]
FONT_ANNOT = FONT_DOUBLE["annot"]
FONT_LEGEND = FONT_DOUBLE["legend"]

# --- Unified Margins ---
# Using the same margins for all figures ensures plot areas align when placed side-by-side.
LEFT_MARGIN = 0.20
RIGHT_MARGIN = 0.95
BOTTOM_MARGIN = 0.18
TOP_MARGIN = 0.92


def apply_common_layout(fig):
    """Apply unified margins to all figures.
    Use this function instead of tight_layout()."""
    fig.subplots_adjust(
        left=LEFT_MARGIN,
        right=RIGHT_MARGIN,
        bottom=BOTTOM_MARGIN,
        top=TOP_MARGIN,
    )


def apply_font(size="double"):
    """Apply font sizes to rcParams according to layout.

    Call this at the beginning of each script (before creating fig).
    Example:
        plot_config.apply_font("triple")
        fig, ax = plt.subplots(figsize=plot_config.FIGSIZE_TRIPLE, ...)

    Parameters
    ----------
    size : str
        "double" — Font for two figures side-by-side (default)
        "triple" — Font for three figures side-by-side
    """
    fonts = {
        "double": FONT_DOUBLE,
        "triple": FONT_TRIPLE,
        "half": FONT_HALF,
        "wide": FONT_WIDE,
    }
    f = fonts.get(size, FONT_DOUBLE)

    plt.rcParams.update(
        {
            "axes.labelsize": f["label"],
            "axes.labelweight": "normal",
            "xtick.labelsize": f["tick"],
            "ytick.labelsize": f["tick"],
            "legend.fontsize": f["legend"],
        }
    )


def apply_global_settings():
    """Update Matplotlib defaults in bulk for paper publication.

    Settings that should be common across all figures (e.g., fontsize / fontweight of axis labels)
    are specified here in bulk. Individual scripts do not need to specify fontsize= or fontweight=
    (rcParams are applied automatically).
    """
    plt.rcParams.update(
        {
            # Font settings
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "pdf.fonttype": 42,  # Conference submission requirements (font embedding)
            # Axis labels (xlabel / ylabel) — default is DOUBLE
            "axes.labelsize": FONT_DOUBLE["label"],
            "axes.labelweight": "normal",
            # Tick labels
            "xtick.labelsize": FONT_DOUBLE["tick"],
            "ytick.labelsize": FONT_DOUBLE["tick"],
            # Legend
            "legend.fontsize": FONT_DOUBLE["legend"],
            # Line width (thick enough to remain visible when scaled down)
            "axes.linewidth": 1.0,
            "grid.linewidth": 0.6,
            "lines.linewidth": 1.5,
            "patch.linewidth": 1.0,
            # Layout
            # Do not use tight_layout/autolayout; control explicitly with apply_common_layout()
            "figure.autolayout": False,
            "savefig.bbox": "standard",
            "savefig.pad_inches": 0.0,
        }
    )


# Apply settings immediately upon import
apply_global_settings()
