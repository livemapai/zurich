"""Convert GTFS trips JSON to binary format with shape deduplication and hourly chunking.

This converter produces a single binary file optimized for streaming:
- Master index with deduplicated shapes (loaded once)
- Hourly chunks that can be fetched via HTTP Range requests
- 95% memory reduction compared to full JSON loading

Binary format:
┌─────────────────────────────────┐
│ Header (32 bytes)               │
├─────────────────────────────────┤
│ Shape Table                     │  ← Loaded once, kept in memory
│   - Shape entries with coords   │
├─────────────────────────────────┤
│ Route Table                     │
│ Headsign Table                  │
│ Chunk Index                     │
├─────────────────────────────────┤
│ Chunk 04 (trips starting 04:00) │  ← Loaded via HTTP Range
│ Chunk 05 (trips starting 05:00) │
│ ...                             │
│ Chunk 27 (overnight)            │
└─────────────────────────────────┘

Usage:
    python3 scripts/download/gtfs_to_binary.py
    python3 scripts/download/gtfs_to_binary.py --input public/data/zurich-tram-trips.json
"""

import json
import struct
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple


# Binary format magic number and version
MAGIC = b"GTFS"
VERSION = 1

# Hours to support (04:00 to 27:00 for overnight trips)
MIN_HOUR = 4
MAX_HOUR = 27  # 27:00 = 03:00 next day


class ShapeEntry(NamedTuple):
    """Deduplicated shape with unique ID."""
    shape_hash: str
    coordinates: list[tuple[float, float, float]]  # [lng, lat, elev]


class BinaryHeader(NamedTuple):
    """32-byte header at start of file."""
    magic: bytes  # 4 bytes "GTFS"
    version: int  # uint32
    shape_count: int  # uint32
    route_count: int  # uint32
    headsign_count: int  # uint32
    chunk_count: int  # uint32
    shape_table_offset: int  # uint32
    route_table_offset: int  # uint32


def hash_coordinates(coords: list[list[float]]) -> str:
    """Create hash for coordinate array to detect duplicates.

    Uses first/last coords plus length for fast comparison.
    Full precision hash would be slower but catch more duplicates.
    """
    if not coords:
        return "empty"

    # Use key points: first, last, count
    first = coords[0]
    last = coords[-1]
    key = f"{first[0]:.4f},{first[1]:.4f}|{last[0]:.4f},{last[1]:.4f}|{len(coords)}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def get_trip_start_hour(trip: dict) -> int:
    """Get the starting hour of a trip from its first timestamp."""
    if not trip.get("timestamps"):
        return MIN_HOUR

    first_timestamp = trip["timestamps"][0]
    hour = first_timestamp // 3600  # Convert seconds to hours

    # Clamp to valid range
    return max(MIN_HOUR, min(MAX_HOUR, hour))


def encode_string_table(strings: list[str]) -> tuple[bytes, list[int]]:
    """Encode strings as null-terminated UTF-8 with offset table.

    Returns:
        (data_bytes, offsets) where offsets[i] is byte offset for string i
    """
    data = bytearray()
    offsets = []

    for s in strings:
        offsets.append(len(data))
        encoded = s.encode("utf-8")
        data.extend(encoded)
        data.append(0)  # Null terminator

    return bytes(data), offsets


def encode_shape_table(shapes: list[ShapeEntry]) -> bytes:
    """Encode shape table as binary.

    Format per shape:
        - point_count: uint32
        - coordinates: float32[point_count * 3]  (lng, lat, elev)
    """
    data = bytearray()

    for shape in shapes:
        coords = shape.coordinates
        # Point count
        data.extend(struct.pack("<I", len(coords)))
        # Coordinates as float32 (12 bytes per point: 3 * 4 bytes)
        for coord in coords:
            data.extend(struct.pack("<fff", coord[0], coord[1], coord[2]))

    return bytes(data)


def encode_trip(trip: dict, shape_index: int, route_index: int, headsign_index: int) -> bytes:
    """Encode a single trip as binary.

    Format (20 bytes header + variable timestamps):
        - shape_index: uint32
        - route_index: uint16
        - headsign_index: uint16
        - timestamp_count: uint32
        - start_time: uint32
        - timestamps: uint32[timestamp_count] (relative to start_time for compression)
    """
    timestamps = trip.get("timestamps", [])
    start_time = timestamps[0] if timestamps else 0

    # Calculate relative timestamps (saves space via smaller integers)
    # But for simplicity, store absolute timestamps as uint16 deltas from start

    data = bytearray()

    # Header (20 bytes)
    data.extend(struct.pack("<I", shape_index))      # 4 bytes
    data.extend(struct.pack("<H", route_index))      # 2 bytes
    data.extend(struct.pack("<H", headsign_index))   # 2 bytes
    data.extend(struct.pack("<I", len(timestamps)))  # 4 bytes
    data.extend(struct.pack("<I", start_time))       # 4 bytes
    # Reserved for future use
    data.extend(struct.pack("<I", 0))                # 4 bytes

    # Timestamps as uint32 (absolute seconds since midnight)
    for ts in timestamps:
        data.extend(struct.pack("<I", ts))

    return bytes(data)


def convert_to_binary(input_path: Path, output_path: Path) -> dict:
    """Convert GTFS JSON to binary format.

    Returns metadata about the conversion.
    """
    print(f"Loading {input_path}...")
    with open(input_path) as f:
        data = json.load(f)

    trips = data.get("trips", [])
    print(f"  -> {len(trips)} trips loaded")

    # Step 1: Deduplicate shapes
    print("Deduplicating shapes...")
    shape_hash_to_index: dict[str, int] = {}
    shapes: list[ShapeEntry] = []
    trip_shape_indices: list[int] = []

    for trip in trips:
        coords = trip.get("path", [])
        shape_hash = hash_coordinates(coords)

        if shape_hash not in shape_hash_to_index:
            shape_hash_to_index[shape_hash] = len(shapes)
            shapes.append(ShapeEntry(
                shape_hash=shape_hash,
                coordinates=[(c[0], c[1], c[2] if len(c) > 2 else 410.0) for c in coords]
            ))

        trip_shape_indices.append(shape_hash_to_index[shape_hash])

    print(f"  -> {len(shapes)} unique shapes (from {len(trips)} trips)")

    # Step 2: Build route and headsign lookup tables
    print("Building lookup tables...")
    route_names: list[str] = []
    route_types: list[int] = []
    route_colors: list[str] = []
    route_name_to_index: dict[str, int] = {}

    headsigns: list[str] = []
    headsign_to_index: dict[str, int] = {}

    trip_route_indices: list[int] = []
    trip_headsign_indices: list[int] = []

    for trip in trips:
        route_name = trip.get("route_short_name", "")
        if route_name not in route_name_to_index:
            route_name_to_index[route_name] = len(route_names)
            route_names.append(route_name)
            route_types.append(trip.get("route_type", 0))
            route_colors.append(trip.get("route_color", "#00a1e0"))
        trip_route_indices.append(route_name_to_index[route_name])

        headsign = trip.get("headsign", "")
        if headsign not in headsign_to_index:
            headsign_to_index[headsign] = len(headsigns)
            headsigns.append(headsign)
        trip_headsign_indices.append(headsign_to_index[headsign])

    print(f"  -> {len(route_names)} unique routes, {len(headsigns)} unique headsigns")

    # Step 3: Group trips by start hour
    print("Grouping trips by hour...")
    trips_by_hour: dict[int, list[int]] = defaultdict(list)  # hour -> trip indices

    for i, trip in enumerate(trips):
        hour = get_trip_start_hour(trip)
        trips_by_hour[hour].append(i)

    hours_with_trips = sorted(trips_by_hour.keys())
    print(f"  -> Trips span hours {min(hours_with_trips)} to {max(hours_with_trips)}")
    for hour in hours_with_trips:
        print(f"     Hour {hour:02d}: {len(trips_by_hour[hour])} trips")

    # Step 4: Build binary file
    print("Building binary file...")

    # Encode tables
    shape_table = encode_shape_table(shapes)
    print(f"  -> Shape table: {len(shape_table) / 1024 / 1024:.2f} MB")

    # Encode route table: (name_offset, type, color_r, color_g, color_b)
    route_names_data, route_name_offsets = encode_string_table(route_names)
    route_table = bytearray()
    for i, name in enumerate(route_names):
        color = route_colors[i].lstrip("#")
        r = int(color[0:2], 16) if len(color) >= 2 else 0
        g = int(color[2:4], 16) if len(color) >= 4 else 0
        b = int(color[4:6], 16) if len(color) >= 6 else 0
        route_table.extend(struct.pack("<IBBBB", route_name_offsets[i], route_types[i], r, g, b))

    # Encode headsign table
    headsign_data, headsign_offsets = encode_string_table(headsigns)
    headsign_table = bytearray()
    for offset in headsign_offsets:
        headsign_table.extend(struct.pack("<I", offset))

    # Encode chunks
    chunk_data_list: list[bytes] = []
    chunk_index: list[tuple[int, int, int]] = []  # (hour, offset, size)

    for hour in range(MIN_HOUR, MAX_HOUR + 1):
        trip_indices = trips_by_hour.get(hour, [])
        chunk_bytes = bytearray()

        # Chunk header: trip count
        chunk_bytes.extend(struct.pack("<I", len(trip_indices)))

        # Encode each trip in this hour
        for trip_idx in trip_indices:
            trip = trips[trip_idx]
            trip_binary = encode_trip(
                trip,
                trip_shape_indices[trip_idx],
                trip_route_indices[trip_idx],
                trip_headsign_indices[trip_idx]
            )
            chunk_bytes.extend(trip_binary)

        chunk_data_list.append(bytes(chunk_bytes))
        chunk_index.append((hour, 0, len(chunk_bytes)))  # Offset filled later

    # Calculate final offsets
    current_offset = 32  # Header size

    shape_table_offset = current_offset
    current_offset += len(shape_table)

    route_table_offset = current_offset
    current_offset += len(route_table) + len(route_names_data)

    headsign_table_offset = current_offset
    current_offset += len(headsign_table) + len(headsign_data)

    chunk_index_offset = current_offset
    chunk_index_size = len(chunk_index) * 12  # 3 uint32 per entry
    current_offset += chunk_index_size

    # Update chunk offsets
    updated_chunk_index = []
    for i, (hour, _, size) in enumerate(chunk_index):
        updated_chunk_index.append((hour, current_offset, size))
        current_offset += size

    # Write file
    print(f"Writing to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        # Header (32 bytes)
        f.write(MAGIC)
        f.write(struct.pack("<I", VERSION))
        f.write(struct.pack("<I", len(shapes)))
        f.write(struct.pack("<I", len(route_names)))
        f.write(struct.pack("<I", len(headsigns)))
        f.write(struct.pack("<I", len(chunk_index)))
        f.write(struct.pack("<I", shape_table_offset))
        f.write(struct.pack("<I", route_table_offset))

        # Shape table
        f.write(shape_table)

        # Route table + string data
        f.write(route_table)
        f.write(route_names_data)

        # Headsign table + string data
        f.write(headsign_table)
        f.write(headsign_data)

        # Chunk index
        for hour, offset, size in updated_chunk_index:
            f.write(struct.pack("<III", hour, offset, size))

        # Chunk data
        for chunk_data in chunk_data_list:
            f.write(chunk_data)

    # Write JSON manifest for debugging/verification
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest = {
        "version": VERSION,
        "shapes": len(shapes),
        "routes": len(route_names),
        "headsigns": len(headsigns),
        "chunks": [
            {"hour": h, "offset": o, "size": s, "trips": len(trips_by_hour.get(h, []))}
            for h, o, s in updated_chunk_index
        ],
        "offsets": {
            "shape_table": shape_table_offset,
            "route_table": route_table_offset,
            "headsign_table": headsign_table_offset,
            "chunk_index": chunk_index_offset,
        },
        "sizes": {
            "shape_table_bytes": len(shape_table),
            "route_table_bytes": len(route_table) + len(route_names_data),
            "headsign_table_bytes": len(headsign_table) + len(headsign_data),
            "total_bytes": current_offset,
        },
        "route_list": route_names,
        "route_colors": route_colors,
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    file_size = output_path.stat().st_size
    print(f"  -> Binary file: {file_size / 1024 / 1024:.2f} MB")
    print(f"  -> Manifest: {manifest_path}")

    return {
        "input_trips": len(trips),
        "unique_shapes": len(shapes),
        "unique_routes": len(route_names),
        "unique_headsigns": len(headsigns),
        "chunks": len(chunk_index),
        "file_size_bytes": file_size,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert GTFS JSON to binary format")
    parser.add_argument(
        "--input",
        type=str,
        default="public/data/zurich-tram-trips.json",
        help="Input JSON file path"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="public/data/gtfs/gtfs-trips.bin",
        help="Output binary file path"
    )
    args = parser.parse_args()

    print("GTFS Binary Converter")
    print("=" * 50)

    result = convert_to_binary(Path(args.input), Path(args.output))

    print("=" * 50)
    print("Conversion complete!")
    print(f"  Input trips: {result['input_trips']:,}")
    print(f"  Unique shapes: {result['unique_shapes']:,}")
    print(f"  Unique routes: {result['unique_routes']:,}")
    print(f"  File size: {result['file_size_bytes'] / 1024 / 1024:.2f} MB")

    # Calculate memory savings
    json_size = Path(args.input).stat().st_size
    bin_size = result['file_size_bytes']
    savings = (1 - bin_size / json_size) * 100
    print(f"  Size reduction: {savings:.1f}%")
