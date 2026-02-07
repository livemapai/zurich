#!/usr/bin/env python3
"""
Core utilities for tile stitching experiments.

Provides image manipulation, API calls, and grid management shared by all approaches.
"""

import base64
import io
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

# Gemini API configuration
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "models/gemini-2.5-flash-image"

# Tile dimensions
TILE_SIZE = 512
HORIZONTAL_SIZE = (1024, 512)   # 2 tiles side-by-side
VERTICAL_SIZE = (512, 1024)     # 2 tiles stacked
GRID_2X2_SIZE = (1024, 1024)    # 2×2 tiles
GRID_3X3_SIZE = (1536, 1536)    # 3×3 tiles
GRID_4X3_SIZE = (2048, 1536)    # 4×3 tiles (full grid)
ROW_4_SIZE = (2048, 512)        # 4 tiles in a row


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TileGrid:
    """Represents a 2D grid of tiles with labels A-L."""
    tiles: dict[str, Image.Image] = field(default_factory=dict)
    rows: int = 3
    cols: int = 4

    # Grid layout (4×3):
    #   A B C D
    #   E F G H
    #   I J K L
    LAYOUT = [
        ['A', 'B', 'C', 'D'],
        ['E', 'F', 'G', 'H'],
        ['I', 'J', 'K', 'L'],
    ]

    def get(self, label: str) -> Optional[Image.Image]:
        """Get tile by label (A-L)."""
        return self.tiles.get(label)

    def set(self, label: str, img: Image.Image):
        """Set tile by label."""
        self.tiles[label] = img

    def get_row(self, row_idx: int) -> list[Image.Image]:
        """Get all tiles in a row (0-indexed)."""
        labels = self.LAYOUT[row_idx]
        return [self.tiles[l] for l in labels if l in self.tiles]

    def get_col(self, col_idx: int) -> list[Image.Image]:
        """Get all tiles in a column (0-indexed)."""
        labels = [self.LAYOUT[r][col_idx] for r in range(self.rows)]
        return [self.tiles[l] for l in labels if l in self.tiles]

    def get_2x2(self, top_left_label: str) -> list[Image.Image]:
        """Get 2×2 block starting from top-left label."""
        # Find position
        for r, row in enumerate(self.LAYOUT):
            for c, label in enumerate(row):
                if label == top_left_label:
                    if r + 1 < self.rows and c + 1 < self.cols:
                        labels = [
                            self.LAYOUT[r][c],
                            self.LAYOUT[r][c + 1],
                            self.LAYOUT[r + 1][c],
                            self.LAYOUT[r + 1][c + 1],
                        ]
                        return [self.tiles[l] for l in labels if l in self.tiles]
        return []

    def get_neighbors(self, label: str) -> dict[str, Optional[Image.Image]]:
        """Get neighboring tiles (above, below, left, right)."""
        for r, row in enumerate(self.LAYOUT):
            for c, l in enumerate(row):
                if l == label:
                    return {
                        'above': self.tiles.get(self.LAYOUT[r - 1][c]) if r > 0 else None,
                        'below': self.tiles.get(self.LAYOUT[r + 1][c]) if r + 1 < self.rows else None,
                        'left': self.tiles.get(self.LAYOUT[r][c - 1]) if c > 0 else None,
                        'right': self.tiles.get(self.LAYOUT[r][c + 1]) if c + 1 < self.cols else None,
                    }
        return {'above': None, 'below': None, 'left': None, 'right': None}

    @property
    def labels(self) -> list[str]:
        """Get all available tile labels."""
        return list(self.tiles.keys())

    def __len__(self) -> int:
        return len(self.tiles)


@dataclass
class ExperimentResult:
    """Result from running a single experiment approach."""
    approach_id: int
    approach_name: str
    tiles: TileGrid
    elapsed_seconds: float
    api_calls: int
    seam_score: float = 0.0
    notes: str = ""


# =============================================================================
# IMAGE MANIPULATION
# =============================================================================

def load_image(path: Path) -> Image.Image:
    """Load an image file and convert to RGB."""
    with Image.open(path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        return img.copy()


def save_image(img: Image.Image, path: Path, format: str = "PNG"):
    """Save an image to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format)


def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


def image_to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    return base64.b64encode(image_to_bytes(img)).decode("utf-8")


def bytes_to_image(data: bytes) -> Image.Image:
    """Convert bytes to PIL Image."""
    return Image.open(io.BytesIO(data))


# =============================================================================
# STITCHING FUNCTIONS
# =============================================================================

def stitch_horizontal(img_a: Image.Image, img_b: Image.Image) -> Image.Image:
    """Combine 2 tiles side-by-side → 1024×512."""
    result = Image.new("RGB", HORIZONTAL_SIZE)
    result.paste(img_a.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(img_b.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, 0))
    return result


def stitch_vertical(img_a: Image.Image, img_b: Image.Image) -> Image.Image:
    """Combine 2 tiles vertically → 512×1024."""
    result = Image.new("RGB", VERTICAL_SIZE)
    result.paste(img_a.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(img_b.resize((TILE_SIZE, TILE_SIZE)), (0, TILE_SIZE))
    return result


def stitch_2x2(
    top_left: Image.Image,
    top_right: Image.Image,
    bottom_left: Image.Image,
    bottom_right: Image.Image,
) -> Image.Image:
    """Combine 4 tiles in 2×2 grid → 1024×1024."""
    result = Image.new("RGB", GRID_2X2_SIZE)
    result.paste(top_left.resize((TILE_SIZE, TILE_SIZE)), (0, 0))
    result.paste(top_right.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, 0))
    result.paste(bottom_left.resize((TILE_SIZE, TILE_SIZE)), (0, TILE_SIZE))
    result.paste(bottom_right.resize((TILE_SIZE, TILE_SIZE)), (TILE_SIZE, TILE_SIZE))
    return result


def stitch_3x3(tiles: list[Image.Image]) -> Image.Image:
    """Combine 9 tiles in 3×3 grid → 1536×1536."""
    if len(tiles) != 9:
        raise ValueError(f"Expected 9 tiles, got {len(tiles)}")
    result = Image.new("RGB", GRID_3X3_SIZE)
    for i, tile in enumerate(tiles):
        x = (i % 3) * TILE_SIZE
        y = (i // 3) * TILE_SIZE
        result.paste(tile.resize((TILE_SIZE, TILE_SIZE)), (x, y))
    return result


def stitch_row(tiles: list[Image.Image]) -> Image.Image:
    """Combine tiles in a horizontal row."""
    width = len(tiles) * TILE_SIZE
    result = Image.new("RGB", (width, TILE_SIZE))
    for i, tile in enumerate(tiles):
        result.paste(tile.resize((TILE_SIZE, TILE_SIZE)), (i * TILE_SIZE, 0))
    return result


def stitch_full_grid(grid: TileGrid) -> Image.Image:
    """Stitch all tiles in grid to single image (4×3 = 2048×1536)."""
    result = Image.new("RGB", GRID_4X3_SIZE)
    for r, row_labels in enumerate(TileGrid.LAYOUT):
        for c, label in enumerate(row_labels):
            tile = grid.get(label)
            if tile:
                x = c * TILE_SIZE
                y = r * TILE_SIZE
                result.paste(tile.resize((TILE_SIZE, TILE_SIZE)), (x, y))
    return result


# =============================================================================
# CUTTING FUNCTIONS
# =============================================================================

def cut_horizontal(img: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Split 1024×512 → 2 tiles (left, right)."""
    if img.size != HORIZONTAL_SIZE:
        img = img.resize(HORIZONTAL_SIZE, Image.LANCZOS)
    left = img.crop((0, 0, TILE_SIZE, TILE_SIZE))
    right = img.crop((TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE))
    return left, right


def cut_vertical(img: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Split 512×1024 → 2 tiles (top, bottom)."""
    if img.size != VERTICAL_SIZE:
        img = img.resize(VERTICAL_SIZE, Image.LANCZOS)
    top = img.crop((0, 0, TILE_SIZE, TILE_SIZE))
    bottom = img.crop((0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2))
    return top, bottom


def cut_2x2(img: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    """Split 1024×1024 → 4 tiles (top_left, top_right, bottom_left, bottom_right)."""
    if img.size != GRID_2X2_SIZE:
        img = img.resize(GRID_2X2_SIZE, Image.LANCZOS)
    top_left = img.crop((0, 0, TILE_SIZE, TILE_SIZE))
    top_right = img.crop((TILE_SIZE, 0, TILE_SIZE * 2, TILE_SIZE))
    bottom_left = img.crop((0, TILE_SIZE, TILE_SIZE, TILE_SIZE * 2))
    bottom_right = img.crop((TILE_SIZE, TILE_SIZE, TILE_SIZE * 2, TILE_SIZE * 2))
    return top_left, top_right, bottom_left, bottom_right


def cut_3x3(img: Image.Image) -> list[Image.Image]:
    """Split 1536×1536 → 9 tiles."""
    if img.size != GRID_3X3_SIZE:
        img = img.resize(GRID_3X3_SIZE, Image.LANCZOS)
    tiles = []
    for row in range(3):
        for col in range(3):
            x = col * TILE_SIZE
            y = row * TILE_SIZE
            tile = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            tiles.append(tile)
    return tiles


def cut_row(img: Image.Image, num_tiles: int) -> list[Image.Image]:
    """Split a row image into individual tiles."""
    expected_width = num_tiles * TILE_SIZE
    if img.size != (expected_width, TILE_SIZE):
        img = img.resize((expected_width, TILE_SIZE), Image.LANCZOS)
    tiles = []
    for i in range(num_tiles):
        x = i * TILE_SIZE
        tile = img.crop((x, 0, x + TILE_SIZE, TILE_SIZE))
        tiles.append(tile)
    return tiles


def cut_full_grid(img: Image.Image, rows: int = 3, cols: int = 4) -> TileGrid:
    """Split full grid image back to TileGrid."""
    expected_size = (cols * TILE_SIZE, rows * TILE_SIZE)
    if img.size != expected_size:
        img = img.resize(expected_size, Image.LANCZOS)

    grid = TileGrid()
    for r, row_labels in enumerate(TileGrid.LAYOUT[:rows]):
        for c, label in enumerate(row_labels[:cols]):
            x = c * TILE_SIZE
            y = r * TILE_SIZE
            tile = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            grid.set(label, tile)
    return grid


# =============================================================================
# API CALLS
# =============================================================================

def call_gemini(
    image: Image.Image,
    prompt: str,
    expected_size: tuple[int, int],
    temperature: float = 0.3,
    api_key: Optional[str] = None,
) -> Image.Image:
    """Call Gemini API with image and prompt, return styled image."""
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key required. Set GOOGLE_API_KEY environment variable.")

    img_b64 = image_to_base64(image)

    url = f"{API_BASE}/{MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "responseModalities": ["image", "text"],
            "temperature": temperature,
        },
    }

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )

    if response.status_code != 200:
        error_detail = response.text[:500] if response.text else "No details"
        raise ValueError(f"Gemini API error {response.status_code}: {error_detail}")

    result = response.json()

    if "candidates" in result:
        for candidate in result["candidates"]:
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "inlineData" in part:
                        img_bytes = base64.b64decode(part["inlineData"]["data"])
                        img = Image.open(io.BytesIO(img_bytes))
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        if img.size != expected_size:
                            img = img.resize(expected_size, Image.LANCZOS)
                        return img

    raise ValueError("Gemini did not return an image in the response")


# =============================================================================
# GRID LOADING
# =============================================================================

def load_tile_grid(source_dir: Path) -> TileGrid:
    """
    Load tiles A-L from a directory into a TileGrid.

    Supports two formats:
    1. Flat directory with tile_A.png, tile_B.png, etc.
    2. Nested webp tiles: 16/x/y.webp (auto-maps to A-L grid)
    """
    grid = TileGrid()
    source_dir = Path(source_dir)

    # First, try flat directory with named tiles
    for label in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']:
        for pattern in [f"tile_{label}.png", f"tile_{label}.webp", f"{label}.png", f"{label}.webp"]:
            path = source_dir / pattern
            if path.exists():
                grid.set(label, load_image(path))
                break

    # If we found tiles, return
    if len(grid) > 0:
        return grid

    # Try nested webp format: 16/x/y.webp
    webp_files = list(source_dir.rglob("*.webp"))
    if not webp_files:
        return grid

    # Parse coordinates from webp files
    coords = []
    for webp_file in webp_files:
        if "_backup" in webp_file.name:
            continue
        try:
            parts = webp_file.parts
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) <= 2:  # zoom level
                    x = int(parts[i + 1])
                    y = int(parts[i + 2].replace(".webp", ""))
                    coords.append((x, y, webp_file))
                    break
        except (IndexError, ValueError):
            continue

    if not coords:
        return grid

    # Find grid bounds
    xs = sorted(set(c[0] for c in coords))
    ys = sorted(set(c[1] for c in coords))

    # Map to A-L labels (4 columns x 3 rows)
    # Grid layout:
    #   A B C D  (row 0)
    #   E F G H  (row 1)
    #   I J K L  (row 2)
    label_grid = [
        ['A', 'B', 'C', 'D'],
        ['E', 'F', 'G', 'H'],
        ['I', 'J', 'K', 'L'],
    ]

    for x, y, path in coords:
        col = xs.index(x) if x in xs else -1
        row = ys.index(y) if y in ys else -1

        if 0 <= row < len(label_grid) and 0 <= col < len(label_grid[0]):
            label = label_grid[row][col]
            grid.set(label, load_image(path))

    return grid


def save_tile_grid(grid: TileGrid, output_dir: Path, format: str = "PNG"):
    """Save all tiles in a grid to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = format.lower()

    for label, tile in grid.tiles.items():
        path = output_dir / f"tile_{label}.{ext}"
        tile.save(path, format)


# =============================================================================
# EDGE BLENDING
# =============================================================================

def blend_edges(
    tile1: Image.Image,
    tile2: Image.Image,
    direction: str,
    blend_width: int = 32,
) -> tuple[Image.Image, Image.Image]:
    """
    Blend edges between two adjacent tiles.

    Args:
        tile1: First tile
        tile2: Second tile
        direction: 'horizontal' (tile1 left of tile2) or 'vertical' (tile1 above tile2)
        blend_width: Number of pixels to blend at each edge

    Returns:
        Tuple of (modified_tile1, modified_tile2)
    """
    import numpy as np

    arr1 = np.array(tile1, dtype=np.float32)
    arr2 = np.array(tile2, dtype=np.float32)

    if direction == 'horizontal':
        # Blend right edge of tile1 with left edge of tile2
        edge1 = arr1[:, -blend_width:]
        edge2 = arr2[:, :blend_width]

        # Create gradient weights
        weights = np.linspace(0, 1, blend_width)[np.newaxis, :, np.newaxis]

        blended = edge1 * (1 - weights) + edge2 * weights

        arr1[:, -blend_width:] = blended
        arr2[:, :blend_width] = blended

    elif direction == 'vertical':
        # Blend bottom edge of tile1 with top edge of tile2
        edge1 = arr1[-blend_width:, :]
        edge2 = arr2[:blend_width, :]

        weights = np.linspace(0, 1, blend_width)[:, np.newaxis, np.newaxis]

        blended = edge1 * (1 - weights) + edge2 * weights

        arr1[-blend_width:, :] = blended
        arr2[:blend_width, :] = blended

    return Image.fromarray(arr1.astype(np.uint8)), Image.fromarray(arr2.astype(np.uint8))
