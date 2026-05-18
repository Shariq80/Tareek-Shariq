"""Estimator Orchestrator — runs all estimators for a region config.

Calls sub-estimators in sequence:
  1. demand_estimator  — trip demand, transit config_rate, scaling factors
  2. mode_share_estimator — MATSim scoring + transitRouter params from ACS
     transit share and (optionally) a prior experiment's realised mode shares

Each sub-estimator writes its own log file under logs/ and updates
config_estimated.json in the region folder. That JSON is the single source
of truth: at experiment time, ConfigManager overlays its
matsim.configurable_params onto the base MATSim template
(matsim/configs/<mode>/config.xml). The estimators do not write any XML.

Running the orchestrator is equivalent to running both sub-estimators
individually but with a single command and a combined summary at the end.

Usage:
    python estimators/estimator.py config/USA/TwinCities/config_twin.json
    python estimators/estimator.py config/USA/TwinCities/config_twin.json --no-acs
    python estimators/estimator.py config/USA/TwinCities/config_twin.json --experiment-dir E:/jetstream2_experiments/april2026/experiment_20260430_121156

The --experiment-dir flag is forwarded to BOTH sub-estimators:
  - demand_estimator uses it to load experiment_summary.json and tune demand.
  - mode_share_estimator uses it to load modestats.csv + config.xml and
    apply the clamped log-ratio update toward ACS targets.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _run(script: Path, config_file: str, extra_args: list) -> int:
    """Run a sub-estimator script and stream its output. Returns exit code."""
    cmd = [sys.executable, str(script), config_file] + extra_args
    result = subprocess.run(cmd)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimator orchestrator — runs demand and mode share estimators"
    )
    parser.add_argument(
        "config_file",
        help="Path to config JSON (e.g. config/USA/TwinCities/config_twin.json)",
    )
    parser.add_argument(
        "--no-acs",
        action="store_true",
        help="Skip Census ACS API calls in both sub-estimators",
    )
    parser.add_argument(
        "--experiment-dir",
        type=str,
        default=None,
        help="Path to a previous experiment folder (passed to demand_estimator)",
    )
    parser.add_argument(
        "--skip-demand",
        action="store_true",
        help="Skip demand_estimator and run only mode_share_estimator",
    )
    parser.add_argument(
        "--skip-mode-share",
        action="store_true",
        help="Skip mode_share_estimator and run only demand_estimator",
    )
    args = parser.parse_args()

    estimators_dir = Path(__file__).parent
    demand_script     = estimators_dir / "demand_estimator.py"
    mode_share_script = estimators_dir / "mode_share_estimator.py"

    print("=" * 70)
    print("  ESTIMATOR ORCHESTRATOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Config: {args.config_file}")
    print("=" * 70)

    results = {}

    # ------------------------------------------------------------------
    # 1. Demand estimator
    # ------------------------------------------------------------------
    if not args.skip_demand:
        print()
        print("=" * 70)
        print("  RUNNING: demand_estimator")
        print("=" * 70)
        extra = []
        if args.no_acs:
            extra.append("--no-acs")
        if args.experiment_dir:
            extra += ["--experiment-dir", args.experiment_dir]
        rc = _run(demand_script, args.config_file, extra)
        results["demand_estimator"] = "OK" if rc == 0 else f"FAILED (exit {rc})"
        if rc != 0:
            print(f"\n!! demand_estimator exited with code {rc}")
    else:
        results["demand_estimator"] = "skipped"

    # ------------------------------------------------------------------
    # 2. Mode share estimator
    # ------------------------------------------------------------------
    if not args.skip_mode_share:
        print()
        print("=" * 70)
        print("  RUNNING: mode_share_estimator")
        print("=" * 70)
        extra = []
        if args.no_acs:
            extra.append("--no-acs")
        if args.experiment_dir:
            extra += ["--experiment-dir", args.experiment_dir]
        rc = _run(mode_share_script, args.config_file, extra)
        results["mode_share_estimator"] = "OK" if rc == 0 else f"FAILED (exit {rc})"
        if rc != 0:
            print(f"\n!! mode_share_estimator exited with code {rc}")
    else:
        results["mode_share_estimator"] = "skipped"

    # ------------------------------------------------------------------
    # Combined summary
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  ORCHESTRATOR SUMMARY")
    print("=" * 70)
    for name, status in results.items():
        print(f"  {name:<30}  {status}")
    config_path = Path(args.config_file)
    stem = config_path.stem
    estimated = config_path.with_name(f"{stem}_estimated{config_path.suffix}")
    print()
    print("  Outputs (if estimators succeeded):")
    print(f"    {estimated}")
    print(f"    logs/demand_estimator_*.log")
    print(f"    logs/mode_share_estimator_*.log")
    print()

    any_failed = any("FAILED" in s for s in results.values())
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
