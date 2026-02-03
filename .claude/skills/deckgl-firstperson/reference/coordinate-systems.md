# Coordinate Systems Reference

This document explains the coordinate systems used in the Zurich 3D Walkthrough project.

## Overview

| System | Format | Units | Usage |
|--------|--------|-------|-------|
| WGS84 | [longitude, latitude] | degrees | deck.gl, GPS, web maps |
| LV95 | [Easting, Northing] | meters | Swiss source data |
| View State | { longitude, latitude, position } | degrees + meters | deck.gl FirstPersonView |

## WGS84 (World Geodetic System 1984)

Standard geographic coordinate system used by GPS and web maps.

```typescript
// [longitude, latitude] - ALWAYS in this order for deck.gl
const zurichCenter: [number, number] = [8.5437, 47.3739];
```

**Key points:**
- Longitude first, then latitude (opposite of Google Maps text)
- Degrees, not meters
- Range: -180 to +180 longitude, -90 to +90 latitude

## Swiss LV95 (Landesvermessung 1995)

Swiss national coordinate system used in source data.

```typescript
// [Easting, Northing] in meters
const zurichLV95: [number, number] = [2683000, 1248000];
```

**Key points:**
- Used in data from data.stadt-zuerich.ch
- Must be converted to WGS84 for deck.gl
- Conversion done in Python data pipeline

## Meters per Degree at Zurich (~47°N)

At Zurich's latitude, 1 degree of longitude/latitude equals:

```typescript
// From src/lib/constants.ts
const METERS_PER_DEGREE = {
  lng: 75500,  // 1° longitude ≈ 75,500 meters at 47°N
  lat: 111320, // 1° latitude ≈ 111,320 meters (nearly constant)
};
```

**Why different values?**
- Latitude: Lines converge at poles, but distance between degrees is nearly constant (~111km)
- Longitude: Lines converge toward poles; at 47°N they're closer than at equator

### Calculation

```typescript
// Longitude varies with latitude
const metersPerDegreeLng = 111320 * Math.cos(latitude * Math.PI / 180);
// At 47°N: 111320 * cos(47°) ≈ 75,500 meters

// Latitude is nearly constant
const metersPerDegreeLat = 111320;
```

## deck.gl FirstPersonView Dual-Anchor System

deck.gl uses a **dual-anchor system** for high floating-point precision:

```typescript
interface FirstPersonViewState {
  // Geographic anchor (WGS84 degrees)
  longitude: number;
  latitude: number;

  // Meter offset from anchor [east, north, altitude]
  position: [number, number, number];

  bearing: number;  // degrees, 0=North, clockwise
  pitch: number;    // degrees, negative=up
}
```

### Why Dual-Anchor?

At street level, small movements (0.1m) require very small degree changes:
```
0.1 meter / 75500 m/deg ≈ 0.0000013 degrees
```

These tiny values can cause floating-point precision issues. The dual-anchor system:
1. Keeps a geographic anchor in degrees (longitude/latitude)
2. Uses meter offsets for high-precision local movement

### Movement Strategy in This Project

We update longitude/latitude directly (Strategy A):

```typescript
// Calculate delta in degrees
const dLng = velocityX * deltaTime / METERS_PER_DEGREE.lng;
const dLat = velocityY * deltaTime / METERS_PER_DEGREE.lat;

// Update geographic anchor
newViewState = {
  ...viewState,
  longitude: viewState.longitude + dLng,
  latitude: viewState.latitude + dLat,
  position: [0, 0, altitude], // Horizontal offset stays at 0
};
```

**Key point:** `position[0]` and `position[1]` are METERS, not degrees!

## Altitude

Altitude is always in meters above sea level:

```typescript
// Zurich base elevation
const ZURICH_BASE_ELEVATION = 408; // meters above sea level

// Eye height
const eyeHeight = 1.7; // meters

// Initial camera altitude
const altitude = ZURICH_BASE_ELEVATION + eyeHeight; // 409.7m
```

## Conversion Examples

### Meters to Degrees

```typescript
// Move 4 meters East
const dLng = 4 / METERS_PER_DEGREE.lng;
// = 4 / 75500 ≈ 0.000053 degrees

// Move 4 meters North
const dLat = 4 / METERS_PER_DEGREE.lat;
// = 4 / 111320 ≈ 0.000036 degrees
```

### Degrees to Meters

```typescript
// How far in meters is 0.001 degrees longitude?
const metersLng = 0.001 * METERS_PER_DEGREE.lng;
// = 0.001 * 75500 = 75.5 meters

// How far in meters is 0.001 degrees latitude?
const metersLat = 0.001 * METERS_PER_DEGREE.lat;
// = 0.001 * 111320 = 111.32 meters
```

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| `position: [8.54, 47.37, 400]` | Using degrees in position | Use meters: `[0, 0, 400]` |
| `75000` for lng conversion | Wrong constant | Use `75500` from constants |
| `111000` for lat conversion | Inaccurate constant | Use `111320` from constants |
| Forgetting to convert | Movement in wrong units | Always convert m/s to deg/s |

## Project Constants

All coordinate constants are centralized in:

```typescript
// src/types/index.ts
export const ZURICH_CENTER: LngLat = [8.5437, 47.3739];
export const ZURICH_BASE_ELEVATION = 408;
export const METERS_PER_DEGREE = {
  lng: 75500,
  lat: 111320,
} as const;
```

Always import from here to ensure consistency.
