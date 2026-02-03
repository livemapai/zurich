# Photo-to-Building Texture Feature

## Vision

Enable crowdsourced building textures for the Zurich 3D walkthrough. Users photograph building facades and map them onto the 3D model, creating an increasingly realistic city experience over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Workflow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   [Photo]  →  [Upload]  →  [Select Building]  →  [Select Face]  │
│                                      │                          │
│                                      ↓                          │
│                            [Perspective Fix]  →  [Apply]        │
│                                      │                          │
│                                      ↓                          │
│                               [Save/Export]                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| 3D Rendering | deck.gl BitmapLayer | Display textures on facades |
| Image Processing | Canvas 2D | Homography transformation |
| Metadata | exifr | Extract GPS from photos |
| Persistence | localStorage | Save texture mappings |
| UI | React | Upload interface, editors |

## Pipeline

```
Photo (JPEG)
    │
    ├─→ EXIF extraction (GPS, direction)
    │       │
    │       ↓
    │   Auto-suggest nearby building
    │
    ↓
Manual building selection
    │
    ↓
Facade selection (click edge)
    │
    ↓
Perspective correction (4-point homography)
    │
    ↓
BitmapLayer rendering
    │
    ↓
localStorage persistence
```

## Implementation Steps

| Step | File | Goal |
|------|------|------|
| 1 | [01-hardcoded-texture.md](./01-hardcoded-texture.md) | Prove BitmapLayer works on a building face |
| 2 | [02-building-selection.md](./02-building-selection.md) | Click to select a building |
| 3 | [03-facade-selection.md](./03-facade-selection.md) | Click edge to select specific facade |
| 4 | [04-photo-upload.md](./04-photo-upload.md) | Upload photo and stretch to facade |
| 5 | [05-homography.md](./05-homography.md) | Fix perspective distortion |
| 6 | [06-persistence.md](./06-persistence.md) | Save/load textures between sessions |

## Research Documents

- [deck-gl-bitmap-layer.md](./research/deck-gl-bitmap-layer.md) - BitmapLayer positioning and 3D placement
- [homography-math.md](./research/homography-math.md) - 4-point perspective transform math
- [exif-extraction.md](./research/exif-extraction.md) - GPS extraction from photo metadata

## How to Use

Each step document is self-contained. To implement:

1. Start a new Claude Code session
2. Say: "Read `docs/photo-texture/01-hardcoded-texture.md` and implement it"
3. Implement together, verify it works
4. Move to next step in a new session

## Key Design Decisions

### Why BitmapLayer?
- Native deck.gl support
- GPU-accelerated rendering
- Handles texture positioning in 3D space

### Why localStorage?
- No backend required
- Instant save/load
- Easy export as JSON for sharing

### Why manual building selection?
- EXIF GPS accuracy is ~5-10m
- Building direction rarely available
- User knows which building they photographed

## Future Enhancements

- Cloud storage for shared textures
- AI-assisted building matching
- Texture blending for panoramic facades
- Night/day texture variants
- Seasonal variations
