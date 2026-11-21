"""Plot the saved, isolated AE-1 lift-slope comparison; no solver imports."""
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs/validation"
report = json.loads((DEST / "isae-ae1-section.json").read_text())
rows = [row for row in report["comparisons"] if row["intervals_per_half"] == 60]
colors = re.findall(
    r"'(#\w{6})'",
    re.search(
        r"plotColors = Object.freeze\(\[(.*?)\]\)",
        (ROOT / "web/plot-colors.js").read_text(),
        re.S,
    ).group(1),
)
series = (
    ("experiment", "Published experiment"),
    ("baseline", "OpenSwing: 6.1185/rad"),
    ("candidate", "OpenSwing: 2π/rad"),
    ("primary_beam_control", "Primary UM/NAST-VLM"),
)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for axis, quantity, title, ylabel in zip(
    axes,
    ("displacement_percent_semispan", "twist_deg"),
    ("Tip midchord displacement", "Projected tip twist"),
    ("Root-normal displacement (% nominal semispan)", "Twist (degrees)"),
):
    for i, (key, label) in enumerate(series):
        axis.bar(
            [j + (i - 1.5) * 0.19 for j in range(len(rows))],
            [row[key][quantity] for row in rows],
            width=0.18, color=colors[i], label=label,
            edgecolor="#555555", linewidth=0.45, zorder=3,
        )
    axis.set_xticks(range(len(rows)), [
        f"{row['alpha_deg']:g}° / {row['speed_m_s']:g} m/s" for row in rows
    ])
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.2, zorder=0)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.04),
           ncol=2, fontsize=9)
fig.suptitle("ISAE AE-1 Pazy: isolated lift-slope sensitivity, 60 intervals per half", fontsize=12)
fig.text(0.5, 0.012, "Three operating points; no coefficient fit or experimental pass. Displacement-axis ambiguity remains.",
         ha="center", fontsize=8.5)
fig.tight_layout(rect=(0, 0.18, 1, 0.94))
for suffix in ("svg", "png"):
    fig.savefig(DEST / f"isae-ae1-section.{suffix}", dpi=150)
plt.close(fig)
