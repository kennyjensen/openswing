"""Plot the retained independent coupled reference; no numerical solves."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=root / "docs/validation/loaded-aeroelastic-reference.json")
    parser.add_argument("--output", type=Path, default=root / "docs/validation/loaded-aeroelastic-reference")
    args = parser.parse_args()
    data = json.loads(args.report.read_text())
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "openswing-loaded-aeroelastic-reference"})
    fig, axes = plt.subplots(1, 3, figsize=(14.8, 4.9), gridspec_kw={"width_ratios": [1, 1.2, 1]})
    for wing, color in [("25", "#2671b7"), ("75", "#bb5235")]:
        cases = [c for c in data["cases"] if c["wing"] == wing]
        for mode, style in [(0, "-o"), (1, "--s")]:
            axes[0].loglog([c["requested_intervals"] for c in cases],
                          [100 * c["independent_continuum"]["poles"][mode]["relative_root_change"] for c in cases],
                          style, color=color, label=f"{wing}% spar, mode {mode + 1}")
    axes[0].set(title="Selected coupled modes", xlabel="Requested intervals", ylabel="Difference from production (%)")
    axes[0].set_xticks([8, 16, 32], ["8", "16", "32"])
    axes[0].xaxis.set_minor_formatter(NullFormatter())
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=.2, which="both")

    boundary = data["boundary"]
    points = sorted(boundary["cases"], key=lambda c: c["speed_m_s"])
    axes[1].axhline(0, color="#666666", linewidth=.8)
    axes[1].axvspan(*boundary["production_bracket_m_s"], color="#b9b9b9", alpha=.65, label="Production bracket")
    axes[1].axvspan(*boundary["bracket_m_s"], color="#72bdb3", alpha=.65, label="Independent bracket")
    axes[1].plot([c["speed_m_s"] for c in points], [c["pole"]["rate_per_s"][0] for c in points],
                 "o-", color="#126b65", markersize=4, label="Independent solutions")
    axes[1].set(title="75% spar: local crossing", xlabel="Speed (m/s)", ylabel="Growth rate (1/s)")
    axes[1].ticklabel_format(useOffset=False, style="plain", axis="x")
    axes[1].set_xticks([22.57, 22.58, 22.59], ["22.57", "22.58", "22.59"])
    axes[1].legend(fontsize=8, loc="upper left")
    axes[1].grid(alpha=.2)

    values = [boundary["center_speed_m_s"], boundary["production_near_neutral_speed_m_s"], boundary["published_speed_m_s"]]
    for y, value, color in zip([2, 1, 0], values, ["#126b65", "#777777", "#bb5235"]):
        axes[2].plot(value, y, "o", color=color)
        axes[2].annotate(f"{value:.4f}" if y else f"{value:.2f}", (value, y), xytext=(0, 9),
                         textcoords="offset points", ha="center", color=color)
    axes[2].set_yticks([2, 1, 0], ["Independent", "Production", "Published"])
    axes[2].set(xlim=(22.15, 24.98), ylim=(-.45, 2.5), title="Published gap remains", xlabel="Speed (m/s)")
    axes[2].grid(alpha=.2, axis="x")
    fig.suptitle("Independent continuum structure + discrete aerodynamic coupling", fontsize=14)
    fig.text(.5, .045, "Six equilibria, twelve local poles; finest selected-root difference < 0.015%. No complete-spectrum claim.", ha="center", fontsize=10)
    fig.text(.5, .008, "Shared aerodynamic conventions and uncertain original ASWING setup remain; no parameter fitting.", ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, .095, 1, .95), w_pad=2)
    for extension in ["svg", "png", "pdf"]:
        fig.savefig(args.output.with_suffix("." + extension), dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
