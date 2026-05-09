"""Mode Share Estimator — scoring parameter calibration for MATSim experiments.

Reads Census ACS B08301 commute mode data for the configured region, determines
appropriate MATSim scoring parameters (pt.constant, waitingPt, walk.constant)
based on regional transit share tiers, and writes:

  1. A region-specific config.xml to the same folder as config.json
     (e.g. config/USA/TwinCities/config.xml). ConfigManager checks this folder
     first at simulation time, falling back to matsim/configs/basic/config.xml.
     The file includes an XML comment block listing every change made.

  2. An updated config_estimated.json (or creates it if demand_estimator has
     not run yet) with the recommended scoring params written into
     matsim.configurable_params so ConfigManager picks them up.

Usage:
    python estimators/mode_share_estimator.py config/USA/TwinCities/config_twin.json
    python estimators/mode_share_estimator.py config/USA/TwinCities/config_twin.json --no-acs

Output:
    config/USA/TwinCities/config.xml          (region-specific MATSim config)
    config/USA/TwinCities/config_twin_estimated.json  (updated scoring params)
    logs/mode_share_estimator_YYYYMMDD_HHMMSS.log
"""

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from estimators.demand_estimator import (
    TeeWriter,
    fetch_acs_commute_data,
    _set_with_flat_leaf,
    apply_recommendations,
)

# ---------------------------------------------------------------------------
# Scoring tier table (keyed on ACS regional transit commute share)
# ---------------------------------------------------------------------------
# Each tier sets three MATSim scoring parameters:
#   pt.constant   — alternative-specific constant for PT mode choice
#   waitingPt     — disutility per hour of waiting at PT stops (util/hr)
#   walk.constant — alternative-specific constant for walk mode choice
#
# Rationale for each tier boundary:
#   >30%  NYC-class: PT must dominate; walk is an access/egress connector
#   10-30% Chicago/DC/Boston: PT competitive; walk needs moderate suppression
#   5-10%  Moderate transit: neutralise default PT penalty; standard walk
#   1-5%   Low transit (Twin Cities): keep PT slightly penalised; strong walk
#          suppression to stop walk stealing PT's small share
#   <1%    Near-zero transit: PT barely viable; heavy penalties on both
#
# walk.marginalUtilityOfDistance is intentionally NOT touched here — the
# distance penalty already suppresses walk for suburban trip lengths.
# Only the constant (modal preference gap vs. car) is adjusted.

SCORING_TIERS: List[Tuple[float, Dict[str, float]]] = [
    # (min_transit_share, params)
    (0.30, {"pt.constant": 1.5,  "waitingPt": -1.0, "walk.constant": -1.5}),
    (0.10, {"pt.constant": 0.5,  "waitingPt": -1.5, "walk.constant": -2.0}),
    (0.05, {"pt.constant": 0.0,  "waitingPt": -2.0, "walk.constant": -2.5}),
    (0.01, {"pt.constant": -0.5, "waitingPt": -2.5, "walk.constant": -3.0}),
    (0.00, {"pt.constant": -1.0, "waitingPt": -3.0, "walk.constant": -3.0}),
]

# Defaults that ship in matsim/configs/basic/config.xml — used to detect
# whether a param actually needs to change.
_BASELINE = {
    "pt.constant":   -0.5,
    "waitingPt":     -3.0,
    "walk.constant": -1.0,
}


# ---------------------------------------------------------------------------
# Tier lookup
# ---------------------------------------------------------------------------

def _select_tier(transit_share: float) -> Tuple[Dict[str, float], str]:
    """Return (params_dict, tier_label) for the given ACS transit share."""
    for min_share, params in SCORING_TIERS:
        if transit_share >= min_share:
            if min_share == 0.30:
                label = f"NYC-class (>{min_share:.0%})"
            elif min_share == 0.10:
                label = f"high-transit ({min_share:.0%}–30%)"
            elif min_share == 0.05:
                label = f"moderate-transit ({min_share:.0%}–10%)"
            elif min_share == 0.01:
                label = f"low-transit ({min_share:.0%}–5%)"
            else:
                label = "near-zero transit (<1%)"
            return params, label
    # Fallback (should never reach here)
    return SCORING_TIERS[-1][1], "near-zero transit (<1%)"


# ---------------------------------------------------------------------------
# ACS aggregation
# ---------------------------------------------------------------------------

def _aggregate_acs(acs_data: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Sum ACS B08301 fields across all counties and compute shares."""
    totals: Dict[str, int] = {}
    for county_data in acs_data.values():
        for key, val in county_data.items():
            totals[key] = totals.get(key, 0) + val

    total_workers = max(totals.get("total_workers", 0), 1)
    transit_total = totals.get("public_transit", 0)
    bus           = totals.get("bus", 0)
    subway        = totals.get("subway", 0)
    commuter_rail = totals.get("commuter_rail", 0)
    light_rail    = totals.get("light_rail", 0)
    walked        = totals.get("walked", 0)
    car           = totals.get("car_truck_van", 0)

    return {
        "total_workers":   total_workers,
        "transit_share":   transit_total / total_workers,
        "bus_share":       bus / total_workers,
        "rail_share":      (subway + commuter_rail + light_rail) / total_workers,
        "walk_share":      walked / total_workers,
        "car_share":       car / total_workers,
        "transit_total":   transit_total,
        "bus":             bus,
        "subway":          subway,
        "commuter_rail":   commuter_rail,
        "light_rail":      light_rail,
        "walked":          walked,
        "car":             car,
    }


# ---------------------------------------------------------------------------
# Build recommendations
# ---------------------------------------------------------------------------

def build_recommendations(
    transit_share: float,
    tier_params: Dict[str, float],
    tier_label: str,
    acs: Dict[str, Any],
    current_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return list of recommendation dicts for scoring params that differ from current."""
    recs = []

    configurable = (
        current_config.get("matsim", {}).get("configurable_params", {})
    )

    param_map = {
        "pt.constant":   "matsim.configurable_params.scoring.modeParams.pt.constant",
        "waitingPt":     "matsim.configurable_params.scoring.waitingPt",
        "walk.constant": "matsim.configurable_params.scoring.modeParams.walk.constant",
    }

    current_values = {
        "pt.constant":   float(configurable.get("scoring.modeParams.pt.constant",
                                                  _BASELINE["pt.constant"])),
        "waitingPt":     float(configurable.get("scoring.waitingPt",
                                                  _BASELINE["waitingPt"])),
        "walk.constant": float(configurable.get("scoring.modeParams.walk.constant",
                                                  _BASELINE["walk.constant"])),
    }

    reasons = {
        "pt.constant": (
            f"ACS regional transit commute share is {transit_share:.1%} ({tier_label}). "
            f"pt.constant={tier_params['pt.constant']:+.1f} is the calibrated value for this "
            f"tier to prevent simulated PT share from collapsing below the generated share "
            f"during MATSim replanning (access/egress walk + waiting disutility)."
        ),
        "waitingPt": (
            f"ACS regional transit commute share is {transit_share:.1%} ({tier_label}). "
            f"waitingPt={tier_params['waitingPt']:.1f} util/hr matches the waiting penalty "
            f"appropriate for this transit density (sparse networks have longer headways, "
            f"requiring a less punishing waiting cost to keep PT viable)."
        ),
        "walk.constant": (
            f"ACS regional walk commute share is {acs['walk_share']:.1%}; transit share "
            f"{transit_share:.1%} ({tier_label}). walk.constant={tier_params['walk.constant']:+.1f} "
            f"suppresses walk for suburban trip distances where car/PT are the realistic "
            f"alternatives, preventing walk from absorbing PT's generated share during "
            f"MATSim subtour mode choice."
        ),
    }

    for short_key, full_path in param_map.items():
        recommended = tier_params[short_key]
        current     = current_values[short_key]
        if abs(recommended - current) > 0.05:
            recs.append({
                "parameter":   full_path,
                "current":     current,
                "recommended": recommended,
                "reason":      reasons[short_key],
            })

    return recs


# ---------------------------------------------------------------------------
# Config.xml writer
# ---------------------------------------------------------------------------

def _read_baseline_xml(config: Dict[str, Any]) -> ET.ElementTree:
    """Load the baseline config.xml from matsim/configs/{mode}/."""
    mode = config.get("matsim", {}).get("mode", "basic")
    template_path = project_root / "matsim" / "configs" / mode / "config.xml"
    if not template_path.exists():
        raise FileNotFoundError(f"Baseline config.xml not found: {template_path}")
    return ET.parse(template_path)


def _patch_xml_scoring(
    tree: ET.ElementTree,
    tier_params: Dict[str, float],
    changes: List[str],
) -> None:
    """Patch pt.constant, waitingPt, walk.constant in an ET tree in-place."""
    root = tree.getroot()
    scoring_module = next(
        (m for m in root.findall("module") if m.get("name") == "scoring"), None
    )
    if scoring_module is None:
        raise RuntimeError("scoring module not found in config.xml template")

    scoring_params = scoring_module.find("parameterset[@type='scoringParameters']")
    if scoring_params is None:
        raise RuntimeError("scoringParameters not found in config.xml template")

    # waitingPt — top-level scoringParameters param
    _set_or_create_param(scoring_params, "waitingPt", str(tier_params["waitingPt"]))
    changes.append(f"scoring.waitingPt = {tier_params['waitingPt']}")

    # pt.constant and walk.constant — inside modeParams blocks
    for mode_name, param_key in [("pt", "pt.constant"), ("walk", "walk.constant")]:
        block = _find_mode_params_block(scoring_params, mode_name)
        if block is None:
            block = ET.SubElement(scoring_params, "parameterset", {"type": "modeParams"})
            ET.SubElement(block, "param", {"name": "mode", "value": mode_name})
        _set_or_create_param(block, "constant", str(tier_params[param_key]))
        changes.append(f"scoring.modeParams.{mode_name}.constant = {tier_params[param_key]}")


def _set_or_create_param(parent: ET.Element, name: str, value: str) -> None:
    existing = parent.find(f"param[@name='{name}']")
    if existing is not None:
        existing.set("value", value)
    else:
        ET.SubElement(parent, "param", {"name": name, "value": value})


def _find_mode_params_block(
    scoring_params: ET.Element, mode_name: str
) -> Optional[ET.Element]:
    for ps in scoring_params.findall("parameterset[@type='modeParams']"):
        mode_el = ps.find("param[@name='mode']")
        if mode_el is not None and mode_el.get("value") == mode_name:
            return ps
    return None


def write_region_config_xml(
    config: Dict[str, Any],
    config_path: Path,
    tier_params: Dict[str, float],
    tier_label: str,
    transit_share: float,
    acs: Dict[str, Any],
) -> Path:
    """Write a patched config.xml to the region's config folder.

    The file gets an XML comment block at the top documenting:
      - that it was generated by mode_share_estimator
      - the ACS transit share and tier
      - each scoring parameter that was changed and its old/new value
    """
    tree = _read_baseline_xml(config)
    changes: List[str] = []
    _patch_xml_scoring(tree, tier_params, changes)

    ET.indent(tree, space="    ")

    output_path = config_path.parent / "config.xml"

    # Build the file content
    xml_lines: List[str] = []
    xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_lines.append('<!DOCTYPE config SYSTEM "http://www.matsim.org/files/dtd/config_v2.dtd">')
    xml_lines.append("")
    xml_lines.append("<!--")
    xml_lines.append("  GENERATED BY mode_share_estimator.py")
    xml_lines.append(f"  Date      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    xml_lines.append(f"  Source    : {config_path.name}")
    xml_lines.append(f"  ACS transit share : {transit_share:.2%}  ({tier_label})")
    xml_lines.append(f"  ACS walk share    : {acs['walk_share']:.2%}")
    xml_lines.append("")
    xml_lines.append("  Scoring parameters changed from matsim/configs/basic/config.xml:")
    for ch in changes:
        xml_lines.append(f"    {ch}")
    xml_lines.append("")
    xml_lines.append("  This file is loaded by ConfigManager in preference to the global")
    xml_lines.append("  matsim/configs/basic/config.xml when present in the region folder.")
    xml_lines.append("  Re-run mode_share_estimator.py to regenerate after ACS data updates.")
    xml_lines.append("-->")
    xml_lines.append("")

    # Serialise tree body (skip the auto-generated XML declaration)
    import io
    buf = io.StringIO()
    tree.write(buf, encoding="unicode", xml_declaration=False, method="xml")
    xml_body = buf.getvalue()
    # Strip leading blank lines that ET.indent may add
    xml_body = xml_body.lstrip("\n")
    xml_lines.append(xml_body)

    output_path.write_text("\n".join(xml_lines), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Estimated config.json writer
# ---------------------------------------------------------------------------

def update_estimated_config(
    config: Dict[str, Any],
    config_path: Path,
    recommendations: List[Dict[str, Any]],
) -> Path:
    """Apply recommendations to config_estimated.json (create or update)."""
    stem = config_path.stem
    estimated_path = config_path.with_name(f"{stem}_estimated{config_path.suffix}")

    # Start from existing estimated config if present, otherwise from base config
    if estimated_path.exists():
        with open(estimated_path) as f:
            base = json.load(f)
        print(f"  Updating existing estimated config: {estimated_path.name}")
    else:
        base = copy.deepcopy(config)
        print(f"  Creating new estimated config: {estimated_path.name}")

    new_config = apply_recommendations(base, recommendations)

    with open(estimated_path, "w") as f:
        json.dump(new_config, f, indent=2)

    return estimated_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mode share estimator — calibrate MATSim scoring params from ACS data"
    )
    parser.add_argument(
        "config_file",
        help="Path to config JSON (e.g. config/USA/TwinCities/config_twin.json)",
    )
    parser.add_argument(
        "--no-acs",
        action="store_true",
        help="Skip Census ACS API call (uses zero transit share — for offline testing)",
    )
    args = parser.parse_args()

    # Log file
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"mode_share_estimator_{timestamp}.log"
    tee = TeeWriter(log_path)
    sys.stdout = tee

    print("=" * 70)
    print("  MODE SHARE ESTIMATOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Load config
    config_path = Path(args.config_file)
    if not config_path.is_file():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    print(f"\nLoaded config : {config_path}")
    counties = config.get("region", {}).get("counties", [])
    print(f"Region        : {len(counties)} counties")

    # ------------------------------------------------------------------
    # Step 1: Fetch ACS data
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 1: FETCH ACS B08301 COMMUTE MODE DATA")
    print("-" * 70)

    acs_data: Dict[str, Dict[str, int]] = {}

    if args.no_acs:
        print("  --no-acs: skipping Census API call. Transit share = 0.")
    else:
        api_key = config.get("data", {}).get("census_api_key", "") or config.get("census_api_key", "")
        if not api_key:
            print("  NOTE: no census_api_key in config — proceeding without key")

        # Counties are plain FIPS strings e.g. ["27003", "27019", ...]
        fips_list = [c for c in counties if isinstance(c, str)]
        if not fips_list:
            print("  WARNING: no county FIPS codes found in config.region.counties")
        else:
            print(f"  Fetching ACS for {len(fips_list)} counties ...")
            acs_data = fetch_acs_commute_data(fips_list, api_key)
            print(f"  Received data for {len(acs_data)}/{len(fips_list)} counties")

            missing = set(fips_list) - set(acs_data.keys())
            if missing:
                print(f"  WARNING: missing ACS data for {len(missing)} counties: "
                      f"{', '.join(sorted(missing))}")

    # ------------------------------------------------------------------
    # Step 2: Aggregate and compute transit share
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 2: AGGREGATE REGIONAL MODE SHARES")
    print("-" * 70)

    if acs_data:
        acs = _aggregate_acs(acs_data)
    else:
        acs = {
            "total_workers": 0, "transit_share": 0.0, "bus_share": 0.0,
            "rail_share": 0.0, "walk_share": 0.0, "car_share": 0.0,
            "transit_total": 0, "bus": 0, "subway": 0,
            "commuter_rail": 0, "light_rail": 0, "walked": 0, "car": 0,
        }

    transit_share = acs["transit_share"]

    print(f"  Total workers (ACS)  : {acs['total_workers']:,}")
    print(f"  Car share            : {acs['car_share']:.2%}")
    print(f"  Transit share (total): {transit_share:.2%}")
    print(f"    Bus                : {acs['bus_share']:.2%}")
    print(f"    Rail (sub+comm+LR) : {acs['rail_share']:.2%}")
    print(f"  Walk share           : {acs['walk_share']:.2%}")

    # ------------------------------------------------------------------
    # Step 3: Select scoring tier
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 3: SELECT SCORING TIER")
    print("-" * 70)

    tier_params, tier_label = _select_tier(transit_share)

    print(f"  Transit share {transit_share:.2%}  →  tier: {tier_label}")
    print()
    print(f"  {'Parameter':<45}  {'Value':>8}")
    print(f"  {'-'*45}  {'-'*8}")
    print(f"  {'scoring.modeParams.pt.constant':<45}  {tier_params['pt.constant']:>+8.1f}")
    print(f"  {'scoring.waitingPt':<45}  {tier_params['waitingPt']:>8.1f}")
    print(f"  {'scoring.modeParams.walk.constant':<45}  {tier_params['walk.constant']:>+8.1f}")

    # ------------------------------------------------------------------
    # Step 4: Build recommendations (only params that differ from current)
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 4: COMPARE TO CURRENT CONFIG")
    print("-" * 70)

    recommendations = build_recommendations(
        transit_share, tier_params, tier_label, acs, config
    )

    if not recommendations:
        print("  No changes needed — current scoring params already match the tier.")
    else:
        print(f"  {len(recommendations)} parameter(s) to update:")
        for rec in recommendations:
            print(f"    {rec['parameter']}")
            print(f"      current     : {rec['current']}")
            print(f"      recommended : {rec['recommended']}")

    # ------------------------------------------------------------------
    # Step 5: Write region-specific config.xml
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 5: WRITE REGION-SPECIFIC config.xml")
    print("-" * 70)

    xml_path = write_region_config_xml(
        config, config_path, tier_params, tier_label, transit_share, acs
    )
    print(f"  Written: {xml_path}")
    print("  (ConfigManager will use this file in preference to")
    print("   matsim/configs/basic/config.xml for this region)")

    # ------------------------------------------------------------------
    # Step 6: Update config_estimated.json
    # ------------------------------------------------------------------
    print()
    print("-" * 70)
    print("  STEP 6: UPDATE config_estimated.json")
    print("-" * 70)

    if recommendations:
        estimated_path = update_estimated_config(config, config_path, recommendations)
        print(f"  Written: {estimated_path}")
    else:
        print("  No changes — config_estimated.json not modified.")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Region ACS transit share : {transit_share:.2%}")
    print(f"  Scoring tier             : {tier_label}")
    print(f"  pt.constant              : {tier_params['pt.constant']:+.1f}")
    print(f"  waitingPt                : {tier_params['waitingPt']:.1f} util/hr")
    print(f"  walk.constant            : {tier_params['walk.constant']:+.1f}")
    print()
    print(f"  config.xml  → {xml_path}")
    if recommendations:
        stem = config_path.stem
        estimated_path = config_path.with_name(f"{stem}_estimated{config_path.suffix}")
        print(f"  config.json → {estimated_path}")
    print(f"  log         → {log_path}")
    print()

    tee.close()
    sys.stdout = tee.terminal


if __name__ == "__main__":
    main()
