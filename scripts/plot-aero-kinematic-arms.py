"""Plot the retained kinematic-arm sensitivity; no production solves."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=root / "docs/validation/aero-kinematic-arms.json")
    parser.add_argument("--output", type=Path, default=root / "docs/validation/aero-kinematic-arms")
    args = parser.parse_args()
    data = json.loads(args.report.read_text())
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "openswing-kinematic-arms"})
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8))
    variants = [("physical_force", "Physical force point", "#2671b7", "o"),
                ("physical_kinematic_arms", "Physical force + control", "#bb5235", "s")]
    for variant, label, color, marker in variants:
        rows = sorted([c for c in data["mode_cases"] if c["variant"] == variant], key=lambda c: c["index"])
        errors = [100 * p["relative_change_from_independent_baseline"] for row in rows for p in row["poles"]]
        axes[0].semilogy(range(4), errors, marker, color=color, label=label)
    axes[0].set_xticks(range(4), ["25%\nmode 1", "25%\nmode 2", "75%\nmode 1", "75%\nmode 2"])
    axes[0].set(title="Eight local mode comparisons", ylabel="Change from virtual-arm baseline (%)")
    axes[0].grid(alpha=.2, which="both")
    axes[0].legend(fontsize=8, loc="lower right")

    baseline = data["baseline"]
    points = [("Virtual arms", baseline["center_speed_m_s"], baseline["bracket_m_s"], "#777777")]
    for variant, label, color, _ in variants:
        row = next(v for v in data["boundaries"] if v["variant"] == variant)
        points.append((label, row["center_speed_m_s"], row["bracket_m_s"], color))
    for y, (label, value, bracket, color) in zip([2, 1, 0], points):
        axes[1].plot(bracket, [y, y], color=color, linewidth=3)
        axes[1].plot(value, y, "o", color=color, markersize=4)
        axes[1].annotate(f"{value:.4f}", (value, y), xytext=(0, 9), textcoords="offset points", ha="center", color=color)
    axes[1].set_yticks([2, 1, 0], ["Virtual", "Force", "Force + control"])
    axes[1].set(title="75% spar: computed local brackets", xlabel="Speed (m/s)", ylim=(-.4, 2.5))
    axes[1].ticklabel_format(useOffset=False, style="plain", axis="x")
    axes[1].margins(x=.3)
    axes[1].grid(alpha=.2, axis="x")

    for y, (label, value, _, color) in zip([3, 2, 1], points):
        axes[2].plot(value, y, "o", color=color)
    published = data["published_speed_m_s"]
    axes[2].plot(published, 0, "D", color="#422f62")
    axes[2].annotate(f"{published:.2f}", (published, 0), xytext=(0, 9), textcoords="offset points", ha="center")
    axes[2].set_yticks([3, 2, 1, 0], ["Virtual", "Force", "Force + control", "Published ASWING"])
    axes[2].set(title="Published gap remains", xlabel="Speed (m/s)", xlim=(22.2, 24.9), ylim=(-.5, 3.4))
    axes[2].grid(alpha=.2, axis="x")
    fig.suptitle("Kinematic-arm sensitivity with the same independent structural and fluid models", fontsize=13)
    fig.text(.5, .047, "Only motion arms vary; virtual influence geometry, mesh and physical properties are fixed.", ha="center")
    fig.text(.5, .013, "Local branches only. These variants do not identify the original ASWING convention or resolve its setup.", ha="center", color="#555555")
    fig.tight_layout(rect=(0, .10, 1, .94), w_pad=2)
    for extension in ["svg", "png", "pdf"]:
        fig.savefig(args.output.with_suffix("." + extension), dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
