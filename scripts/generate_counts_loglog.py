"""Generate log-log observed-vs-simulated count comparisons across experiments.

Reads MATSim's ``*.countscompare.txt`` (written by the counts module: one row
per count station per hour with scale-corrected, iteration-averaged MATSIM and
Count volumes) and draws log-log scatter plots of simulated vs. observed volumes
at selected hours.

Two layouts (``--mode``):
  * ``overlay``  — one figure per hour, every experiment drawn on the same axes
                   in a different colour/marker (compare experiments directly).
  * ``separate`` — one figure per (experiment, hour), like the paper figures.

Station aggregation:
  This branch names FHA count stations per direction as
  ``FHA_<state>_<id>_<dir>`` (dir in {1,3,5,7}). By default each per-direction
  station is plotted as its own point. Pass ``--sum-directions`` to sum the two
  carriageways back into one point per physical sensor (the evaluator's
  ``_station_base`` convention: strip a trailing ``_<digits>`` suffix, and split
  a combined ``A+B`` id on ``+`` first).

Edit the EXPERIMENTS dict below to choose which runs to plot.

Usage:
    python scripts/generate_counts_loglog.py
    python scripts/generate_counts_loglog.py --mode overlay --hours 7 8 16 17
    python scripts/generate_counts_loglog.py --mode separate --sum-directions
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Root holding the experiment folders. Values in EXPERIMENTS are resolved
# relative to this (or may be absolute paths).
EXPERIMENTS_DIR = Path("e:/projects/Tareek/experiments")

# Where figures are written.
FIGURES_DIR = Path(__file__).resolve().parent.parent / "experiments" / "_figures"

# label shown on the plot/legend  ->  experiment folder (relative to
# EXPERIMENTS_DIR, or an absolute path). Edit freely.
EXPERIMENTS = {
    "Run A": "experiment_20260622_175702",
    "Run B": "experiment_20260623_053227_100iter_0.15sf",
}

# MATSim hour indices to plot (countscompare Hour column is 1..24).
DEFAULT_HOURS = [7, 8, 16, 17]

# Distinct colours/markers for overlaying experiments.
_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf",
            "#8c564b", "#e377c2"]
_MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]


def find_countscompare(folder: Path) -> Path | None:
    """Return the highest-iteration ``*.countscompare.txt`` (excluding *AWTV*).

    Searches the experiment's MATSim output ITERS tree, falling back to a flat
    glob in the folder itself.
    """
    iters = folder / "output" / "ITERS"
    candidates: list[Path] = []
    if iters.exists():
        candidates = [p for p in iters.glob("it.*/*.countscompare.txt")
                      if not p.name.endswith("AWTV.txt")]
    if not candidates:
        candidates = [p for p in folder.glob("**/*.countscompare.txt")
                      if not p.name.endswith("AWTV.txt")]
    if not candidates:
        return None

    def iter_num(path: Path) -> int:
        try:
            return int(path.parent.name.split(".")[-1])
        except (ValueError, IndexError):
            return -1

    candidates.sort(key=iter_num)
    return candidates[-1]


def station_base(cs_id: str) -> str:
    """Strip the trailing _<dir> from an FHA per-direction station id.

    Mirrors SimulationEvaluator._station_base so this script aggregates exactly
    like the evaluator does. 'FHA_27_000026_1' -> 'FHA_27_000026'. A combined
    'A+B' id (two stations on one link) keeps its first segment's base. Ids
    without a numeric direction suffix are returned unchanged.
    """
    sid = str(cs_id).split("+")[0]
    parts = sid.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return sid


def load_hour(counts_file: Path, hour: int, sum_directions: bool) -> pd.DataFrame | None:
    """Load one hour from a countscompare file.

    Returns a DataFrame with columns: station, sim, obs. When *sum_directions*
    is set, per-direction rows are summed into one row per physical station.
    """
    df = pd.read_csv(counts_file, sep="\t")
    df.columns = [c.strip() for c in df.columns]
    required = {"Count Station Id", "Hour", "MATSIM volumes", "Count volumes"}
    missing = required - set(df.columns)
    if missing:
        print(f"  SKIP {counts_file}: missing columns {sorted(missing)}")
        return None

    hour_df = df[df["Hour"] == hour]
    if hour_df.empty:
        return None

    out = pd.DataFrame({
        "station": hour_df["Count Station Id"].astype(str).values,
        "sim": hour_df["MATSIM volumes"].astype(float).values,
        "obs": hour_df["Count volumes"].astype(float).values,
    })

    if sum_directions:
        out["station"] = out["station"].apply(station_base)
        out = out.groupby("station", as_index=False)[["sim", "obs"]].sum()

    return out


def _scatter(ax, plot_df: pd.DataFrame, color: str, marker: str, label: str):
    """Plot one experiment's (obs, sim) points on log-log axes.

    Non-zero-observed points are drawn directly; zero-observed points are
    clipped to obs=1 so they remain visible on the log axis.
    """
    sim = plot_df["sim"].values
    obs = plot_df["obs"].values
    mask_zero = obs == 0

    sim_nz, obs_nz = sim[~mask_zero], obs[~mask_zero]
    sim_z = sim[mask_zero]

    if len(obs_nz) > 0:
        ax.scatter(obs_nz, sim_nz, s=20, color=color, alpha=0.75,
                   marker=marker, linewidths=0, zorder=3, label=label)
    if len(sim_z) > 0:
        ax.scatter(np.ones_like(sim_z), np.clip(sim_z, 1, None), s=20,
                   color=color, alpha=0.45, marker=marker, linewidths=0,
                   zorder=3)


def _finalize_axes(ax, all_obs: np.ndarray, all_sim: np.ndarray, title: str):
    """Add 1:1 / 2x / 0.5x reference lines, log scales, labels, and title."""
    vals = np.concatenate([all_obs, all_sim, [1.0]])
    vals = vals[vals > 0]
    lo = max(vals.min() * 0.5, 1.0)
    hi = vals.max() * 2.0
    x_ref = np.array([lo, hi])
    ax.plot(x_ref, x_ref,       color="#444444", linewidth=1.4, linestyle="-",
            zorder=2, label="1:1 line")
    ax.plot(x_ref, x_ref * 2,   color="#888888", linewidth=1.0, linestyle="--", zorder=2)
    ax.plot(x_ref, x_ref * 0.5, color="#888888", linewidth=1.0, linestyle="--", zorder=2)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(left=100)
    ax.set_ylim(bottom=100)
    ax.set_xlabel("Observed Volumes [veh/h]", fontsize=11)
    ax.set_ylabel("Simulated Volumes [veh/h]", fontsize=11)
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, loc="lower right", framealpha=0.9)


def _new_fig():
    fig, ax = plt.subplots(figsize=(7, 6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    return fig, ax


def generate_overlay(loaded: dict[str, Path], hours: list[int], sum_directions: bool):
    """One figure per hour; every experiment overlaid on shared axes."""
    for hour in hours:
        fig, ax = _new_fig()
        all_obs, all_sim = [], []
        plotted = 0
        for i, (label, counts_file) in enumerate(loaded.items()):
            plot_df = load_hour(counts_file, hour, sum_directions)
            if plot_df is None or plot_df.empty:
                print(f"  SKIP {label} hour {hour}: no data")
                continue
            _scatter(ax, plot_df, _PALETTE[i % len(_PALETTE)],
                     _MARKERS[i % len(_MARKERS)], label)
            all_obs.append(plot_df["obs"].values)
            all_sim.append(plot_df["sim"].values)
            plotted += 1

        if plotted == 0:
            plt.close(fig)
            continue

        agg = "summed" if sum_directions else "per-dir"
        _finalize_axes(ax, np.concatenate(all_obs), np.concatenate(all_sim),
                       f"Counts comparison — hour {hour:02d}:00 ({agg})")
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        suffix = "summed" if sum_directions else "perdir"
        out_path = FIGURES_DIR / f"counts_overlay_h{hour:02d}_{suffix}.pdf"
        fig.savefig(out_path, bbox_inches="tight", dpi=150)
        plt.close(fig)
        print(f"  Figure: {out_path}")


def generate_separate(loaded: dict[str, Path], hours: list[int], sum_directions: bool):
    """One figure per (experiment, hour)."""
    for label, counts_file in loaded.items():
        safe = label.replace(", ", "_").replace(" ", "_")
        for hour in hours:
            plot_df = load_hour(counts_file, hour, sum_directions)
            if plot_df is None or plot_df.empty:
                print(f"  SKIP {label} hour {hour}: no data")
                continue

            fig, ax = _new_fig()
            _scatter(ax, plot_df, _PALETTE[0], _MARKERS[0], "Count stations")
            agg = "summed" if sum_directions else "per-dir"
            _finalize_axes(ax, plot_df["obs"].values, plot_df["sim"].values,
                           f"{label} — hour {hour:02d}:00 ({agg})")
            FIGURES_DIR.mkdir(parents=True, exist_ok=True)
            suffix = "summed" if sum_directions else "perdir"
            out_path = FIGURES_DIR / f"counts_h{hour:02d}_{safe}_{suffix}.pdf"
            fig.savefig(out_path, bbox_inches="tight", dpi=150)
            plt.close(fig)
            print(f"  Figure: {out_path}")


def resolve_experiments() -> dict[str, Path]:
    """Resolve EXPERIMENTS to {label: countscompare_path}, skipping missing ones."""
    loaded: dict[str, Path] = {}
    for label, folder_name in EXPERIMENTS.items():
        if not folder_name:
            print(f"  SKIP {label}: no folder configured")
            continue
        folder = Path(folder_name)
        if not folder.is_absolute():
            folder = EXPERIMENTS_DIR / folder_name
        if not folder.exists():
            print(f"  ERROR {label}: folder not found: {folder}")
            continue
        counts_file = find_countscompare(folder)
        if counts_file is None:
            print(f"  SKIP {label}: no countscompare.txt under {folder}")
            continue
        loaded[label] = counts_file
        print(f"  {label}: {counts_file}")
    return loaded


def main():
    parser = argparse.ArgumentParser(
        description="Log-log observed-vs-simulated count comparison across experiments."
    )
    parser.add_argument(
        "--mode", choices=["overlay", "separate"], default="overlay",
        help="overlay = all experiments on one figure per hour; "
             "separate = one figure per experiment per hour (default: overlay).",
    )
    parser.add_argument(
        "--hours", type=int, nargs="+", default=DEFAULT_HOURS,
        help=f"MATSim hour indices to plot (default: {DEFAULT_HOURS}).",
    )
    parser.add_argument(
        "--sum-directions", action="store_true",
        help="Sum per-direction stations into one point per physical sensor. "
             "Default: plot each direction separately.",
    )
    args = parser.parse_args()

    print(f"Experiments root: {EXPERIMENTS_DIR}")
    loaded = resolve_experiments()
    if not loaded:
        print("No experiments with countscompare data found. Exiting.")
        return

    agg = "summed per station" if args.sum_directions else "per direction"
    print(f"\nMode: {args.mode} | hours: {args.hours} | stations: {agg}\n")

    if args.mode == "overlay":
        generate_overlay(loaded, args.hours, args.sum_directions)
    else:
        generate_separate(loaded, args.hours, args.sum_directions)

    print("\nDone.")


if __name__ == "__main__":
    main()
