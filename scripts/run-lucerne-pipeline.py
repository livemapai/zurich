#!/usr/bin/env python3
"""
Run the complete data pipeline for Lucerne 3D viewer.

Downloads and processes all data sources for the Lucerne deck.gl viewer:
- Buildings (LoD2 from Canton Geodatenshop)
- Trees (LIDAR + city curated)
- Amenities (benches, fountains, toilets)
- Heritage buildings
- Hiking trails
- Transit (VBL GTFS)

Usage:
    # Full pipeline (requires manual building download first)
    python scripts/run-lucerne-pipeline.py

    # Individual steps
    python scripts/run-lucerne-pipeline.py --only buildings
    python scripts/run-lucerne-pipeline.py --only trees
    python scripts/run-lucerne-pipeline.py --only amenities
    python scripts/run-lucerne-pipeline.py --only heritage
    python scripts/run-lucerne-pipeline.py --only transit

    # Testing (limited features)
    python scripts/run-lucerne-pipeline.py --test --limit 100

    # Skip elevation sampling (faster)
    python scripts/run-lucerne-pipeline.py --no-elevation
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DOWNLOAD_DIR = SCRIPTS_DIR / "download"
OUTPUT_DIR = PROJECT_ROOT / "public" / "data" / "lucerne"


def run_command(cmd: list[str], description: str, optional: bool = False) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)
    success = result.returncode == 0

    if not success:
        if optional:
            print(f"⚠ Optional step failed: {description}")
        else:
            print(f"❌ Failed: {description}")
    else:
        print(f"✓ Completed: {description}")

    return success


def run_buildings(python: str, limit: Optional[int] = None, wfs: bool = False, input_gdb: Optional[Path] = None) -> bool:
    """Run building download/processing."""
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_buildings.py")]

    if input_gdb:
        cmd.extend(["--input", str(input_gdb)])
    elif wfs:
        cmd.append("--wfs")
    else:
        print("\nBuildings require manual download from:")
        print("  https://daten.geo.lu.ch/download/gebmomit_ds_v1")
        print("\nThen run:")
        print("  python scripts/run-lucerne-pipeline.py --buildings-gdb /path/to/file.gdb")
        print("\nOr try WFS (may have limits):")
        print("  python scripts/run-lucerne-pipeline.py --only buildings --wfs")
        return False

    if limit:
        cmd.extend(["--max-features", str(limit)])

    return run_command(cmd, "Download/process Lucerne buildings")


def run_trees(python: str, limit: Optional[int] = None) -> bool:
    """Run tree download."""
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_trees.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    return run_command(cmd, "Download Lucerne trees (LIDAR + city)")


def run_amenities(python: str, limit: Optional[int] = None) -> bool:
    """Run amenity downloads (benches, fountains, toilets)."""
    success = True

    # Benches
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_benches.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    success = run_command(cmd, "Download Lucerne benches", optional=True) and success

    # Fountains
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_fountains.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    success = run_command(cmd, "Download Lucerne fountains", optional=True) and success

    # Toilets
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_toilets.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    success = run_command(cmd, "Download Lucerne toilets", optional=True) and success

    return success


def run_heritage(python: str, limit: Optional[int] = None) -> bool:
    """Run heritage building download."""
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_heritage.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    return run_command(cmd, "Download Lucerne heritage buildings", optional=True)


def run_trails(python: str, limit: Optional[int] = None) -> bool:
    """Run hiking trail download."""
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_trails.py")]
    if limit:
        cmd.extend(["--max-features", str(limit)])
    return run_command(cmd, "Download Lucerne hiking trails", optional=True)


def run_transit(python: str, limit: Optional[int] = None, no_elevation: bool = False) -> bool:
    """Run VBL GTFS processing."""
    cmd = [python, str(DOWNLOAD_DIR / "lucerne_gtfs.py")]
    if limit:
        cmd.extend(["--limit", str(limit)])
    if no_elevation:
        cmd.append("--no-elevation")
    return run_command(cmd, "Download VBL GTFS transit data")


def validate_output(python: str) -> bool:
    """Validate output files exist and have content."""
    print(f"\n{'='*60}")
    print("Validating output files...")
    print('='*60)

    required_files = [
        "lucerne-buildings.geojson",
        "lucerne-trees.geojson",
    ]

    optional_files = [
        "lucerne-benches.geojson",
        "lucerne-fountains.geojson",
        "lucerne-toilets.geojson",
        "lucerne-heritage.geojson",
        "lucerne-trails.geojson",
        "lucerne-vbl-trips.json",
    ]

    all_valid = True

    for filename in required_files:
        filepath = OUTPUT_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  ✓ {filename}: {size / 1024:.1f} KB")
        else:
            print(f"  ❌ {filename}: MISSING")
            all_valid = False

    for filename in optional_files:
        filepath = OUTPUT_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  ✓ {filename}: {size / 1024:.1f} KB")
        else:
            print(f"  ⚠ {filename}: not generated (optional)")

    return all_valid


def run_pipeline(
    only: Optional[str] = None,
    limit: Optional[int] = None,
    no_elevation: bool = False,
    wfs: bool = False,
    buildings_gdb: Optional[Path] = None,
    skip_validation: bool = False,
) -> bool:
    """
    Run the Lucerne data pipeline.

    Args:
        only: Run only specific step (buildings, trees, amenities, heritage, trails, transit)
        limit: Limit features for testing
        no_elevation: Skip elevation sampling
        wfs: Use WFS for buildings instead of FileGDB
        buildings_gdb: Path to downloaded FileGDB for buildings
        skip_validation: Skip output validation
    """
    python = sys.executable

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    steps_to_run = {
        "buildings": only is None or only == "buildings",
        "trees": only is None or only == "trees",
        "amenities": only is None or only == "amenities",
        "heritage": only is None or only == "heritage",
        "trails": only is None or only == "trails",
        "transit": only is None or only == "transit",
    }

    success = True

    if steps_to_run["buildings"]:
        if not run_buildings(python, limit, wfs, buildings_gdb):
            if not wfs and not buildings_gdb:
                print("\nSkipping buildings (manual download required)")
            else:
                success = False

    if steps_to_run["trees"]:
        if not run_trees(python, limit):
            success = False

    if steps_to_run["amenities"]:
        run_amenities(python, limit)  # Optional, don't fail

    if steps_to_run["heritage"]:
        run_heritage(python, limit)  # Optional

    if steps_to_run["trails"]:
        run_trails(python, limit)  # Optional

    if steps_to_run["transit"]:
        if not run_transit(python, limit, no_elevation):
            print("⚠ Transit download failed (optional)")

    # Validate output
    if not skip_validation:
        if not validate_output(python):
            print("\n⚠ Some required files are missing")

    print("\n" + "="*60)
    if success:
        print("✓ Lucerne pipeline completed!")
    else:
        print("⚠ Pipeline completed with some failures")
    print("="*60)

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    for f in sorted(OUTPUT_DIR.glob("lucerne-*")):
        size = f.stat().st_size / 1024
        print(f"  • {f.name} ({size:.1f} KB)")

    return success


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Lucerne 3D viewer data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all data (trees, amenities, heritage, trails, transit)
  python scripts/run-lucerne-pipeline.py

  # Download only trees
  python scripts/run-lucerne-pipeline.py --only trees

  # Test mode with limited features
  python scripts/run-lucerne-pipeline.py --test --limit 100

  # Process buildings from downloaded FileGDB
  python scripts/run-lucerne-pipeline.py --only buildings --buildings-gdb /path/to/file.gdb

  # Try buildings from WFS (may have limits)
  python scripts/run-lucerne-pipeline.py --only buildings --wfs
        """
    )

    parser.add_argument(
        "--only",
        choices=["buildings", "trees", "amenities", "heritage", "trails", "transit"],
        help="Run only specific step"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode with limited features (default: 100)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of features per source"
    )
    parser.add_argument(
        "--no-elevation",
        action="store_true",
        help="Skip terrain elevation sampling (faster)"
    )
    parser.add_argument(
        "--wfs",
        action="store_true",
        help="Use WFS for buildings (may have feature limits)"
    )
    parser.add_argument(
        "--buildings-gdb",
        type=Path,
        help="Path to downloaded buildings FileGDB"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip output validation"
    )

    args = parser.parse_args()

    # Test mode defaults
    limit = args.limit
    if args.test and not limit:
        limit = 100

    success = run_pipeline(
        only=args.only,
        limit=limit,
        no_elevation=args.no_elevation,
        wfs=args.wfs,
        buildings_gdb=args.buildings_gdb,
        skip_validation=args.skip_validation,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
