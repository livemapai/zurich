"""Download VBZ tram infrastructure data from Stadt Zürich Open Data.

Downloads:
- strecke_gleisachse: Tram track centerlines (~6,200 segments)
- fahrleitungen_mast: Overhead line poles (~4,600 poles)

Data source: VBZ_Infrastruktur_OGD WFS service
License: CC0 (Public Domain)
"""

import json
import requests
from pathlib import Path

WFS_URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/VBZ_Infrastruktur_OGD"


def download_layer(typename: str, output_path: Path) -> int:
    """Download a VBZ layer as GeoJSON in WGS84 coordinates.

    Args:
        typename: WFS layer name (e.g., 'strecke_gleisachse')
        output_path: Path to save the GeoJSON file

    Returns:
        Number of features downloaded
    """
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "typename": typename,
        "outputFormat": "application/vnd.geo+json",
        "srsName": "EPSG:4326",  # Request WGS84 coordinates
    }

    print(f"Downloading {typename}...")
    response = requests.get(WFS_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f)

    count = len(data.get("features", []))
    size_kb = output_path.stat().st_size / 1024
    print(f"  → {count} features, {size_kb:.1f} KB")

    return count


if __name__ == "__main__":
    output_dir = Path("public/data")

    print("VBZ Tram Infrastructure Download")
    print("=" * 40)

    # Tram track centerlines
    tracks = download_layer(
        "strecke_gleisachse",
        output_dir / "zurich-tram-tracks.geojson"
    )

    # Overhead line poles
    poles = download_layer(
        "fahrleitungen_mast",
        output_dir / "zurich-tram-poles.geojson"
    )

    print("=" * 40)
    print(f"Total: {tracks} tracks, {poles} poles")
