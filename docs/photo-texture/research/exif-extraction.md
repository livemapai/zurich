# Research: EXIF Extraction

## Overview

EXIF (Exchangeable Image File Format) metadata embedded in photos can provide GPS coordinates and compass direction. This helps suggest which building a photo might be of.

## Relevant EXIF Tags

| Tag | Description | Example |
|-----|-------------|---------|
| GPSLatitude | Latitude in degrees/minutes/seconds | [47, 22, 30.5] |
| GPSLatitudeRef | N or S | "N" |
| GPSLongitude | Longitude in degrees/minutes/seconds | [8, 32, 15.2] |
| GPSLongitudeRef | E or W | "E" |
| GPSAltitude | Altitude in meters | 432.5 |
| GPSImgDirection | Compass direction camera was pointing | 135 (SE) |
| GPSImgDirectionRef | T (true north) or M (magnetic) | "T" |
| DateTimeOriginal | When photo was taken | "2024:01:15 14:30:00" |

## Using exifr Library

[exifr](https://github.com/MikeKovarik/exifr) is a modern, fast EXIF parser for browsers and Node.js.

### Installation

```bash
pnpm add exifr
```

### Basic Usage

```typescript
import exifr from 'exifr';

async function extractGPS(file: File) {
  try {
    const gps = await exifr.gps(file);

    if (gps) {
      return {
        latitude: gps.latitude,   // Already converted to decimal degrees
        longitude: gps.longitude,
        altitude: gps.altitude,   // May be undefined
      };
    }

    return null;
  } catch (error) {
    console.error('EXIF extraction failed:', error);
    return null;
  }
}
```

### Getting Direction

```typescript
import exifr from 'exifr';

async function extractPhotoMetadata(file: File) {
  // Parse specific tags for better performance
  const data = await exifr.parse(file, {
    gps: true,
    pick: [
      'GPSLatitude',
      'GPSLongitude',
      'GPSAltitude',
      'GPSImgDirection',
      'DateTimeOriginal',
    ],
  });

  if (!data) return null;

  return {
    position: data.latitude && data.longitude ? {
      lat: data.latitude,
      lng: data.longitude,
      altitude: data.GPSAltitude,
    } : null,

    direction: data.GPSImgDirection,  // 0-360 degrees from north
    timestamp: data.DateTimeOriginal,
  };
}
```

### Full Example with Building Suggestion

```typescript
import exifr from 'exifr';

interface PhotoLocation {
  lat: number;
  lng: number;
  altitude?: number;
  direction?: number;  // Compass bearing 0-360
  timestamp?: Date;
}

interface Building {
  id: string;
  centroid: [number, number];  // [lng, lat]
}

async function extractPhotoLocation(file: File): Promise<PhotoLocation | null> {
  try {
    const exif = await exifr.parse(file, {
      gps: true,
      pick: ['GPSImgDirection', 'DateTimeOriginal'],
    });

    if (!exif?.latitude || !exif?.longitude) {
      return null;
    }

    return {
      lat: exif.latitude,
      lng: exif.longitude,
      altitude: exif.GPSAltitude,
      direction: exif.GPSImgDirection,
      timestamp: exif.DateTimeOriginal ? new Date(exif.DateTimeOriginal) : undefined,
    };
  } catch (error) {
    console.error('EXIF extraction failed:', error);
    return null;
  }
}

function suggestBuilding(
  photoLocation: PhotoLocation,
  buildings: Building[]
): Building | null {
  // Filter buildings within reasonable distance (50m)
  const MAX_DISTANCE_METERS = 50;

  const candidates = buildings
    .map(building => ({
      building,
      distance: haversineDistance(
        photoLocation.lat,
        photoLocation.lng,
        building.centroid[1],
        building.centroid[0]
      ),
      bearing: calculateBearing(
        photoLocation.lat,
        photoLocation.lng,
        building.centroid[1],
        building.centroid[0]
      ),
    }))
    .filter(c => c.distance < MAX_DISTANCE_METERS);

  if (candidates.length === 0) return null;

  // If we have direction, prefer buildings in that direction
  if (photoLocation.direction !== undefined) {
    const DIRECTION_TOLERANCE = 45;  // degrees

    const directionMatch = candidates.find(c => {
      const diff = Math.abs(c.bearing - photoLocation.direction!);
      return diff < DIRECTION_TOLERANCE || diff > (360 - DIRECTION_TOLERANCE);
    });

    if (directionMatch) {
      return directionMatch.building;
    }
  }

  // Otherwise return closest building
  candidates.sort((a, b) => a.distance - b.distance);
  return candidates[0].building;
}

// Haversine formula for distance between two points
function haversineDistance(
  lat1: number, lon1: number,
  lat2: number, lon2: number
): number {
  const R = 6371000; // Earth's radius in meters
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δφ = (lat2 - lat1) * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;

  const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

  return R * c;
}

// Calculate bearing from point 1 to point 2
function calculateBearing(
  lat1: number, lon1: number,
  lat2: number, lon2: number
): number {
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;

  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) -
            Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);

  const θ = Math.atan2(y, x);

  return (θ * 180 / Math.PI + 360) % 360;
}
```

## Accuracy Limitations

### GPS Accuracy

| Scenario | Typical Accuracy |
|----------|-----------------|
| Outdoor, clear sky | 3-5 meters |
| Urban canyon | 10-30 meters |
| Indoor | Often unavailable |
| WiFi-assisted | 15-40 meters |

### Direction Accuracy

| Source | Accuracy |
|--------|----------|
| Phone compass | ±5-15 degrees |
| No calibration | ±30+ degrees |
| Magnetic interference | Unreliable |

### Implications

- GPS alone cannot reliably identify which building
- Direction is often missing or inaccurate
- Use as hint, not definitive answer
- Always allow manual building selection

## Handling Missing Data

```typescript
interface ExtractedMetadata {
  hasGPS: boolean;
  hasDirection: boolean;
  location?: PhotoLocation;
  confidence: 'high' | 'medium' | 'low' | 'none';
}

async function analyzePhoto(file: File): Promise<ExtractedMetadata> {
  const location = await extractPhotoLocation(file);

  if (!location) {
    return { hasGPS: false, hasDirection: false, confidence: 'none' };
  }

  const hasDirection = location.direction !== undefined;

  let confidence: 'high' | 'medium' | 'low';
  if (hasDirection && location.altitude) {
    confidence = 'high';
  } else if (hasDirection || location.altitude) {
    confidence = 'medium';
  } else {
    confidence = 'low';
  }

  return {
    hasGPS: true,
    hasDirection,
    location,
    confidence,
  };
}
```

## UI Integration

```typescript
// src/components/PhotoUpload/PhotoUpload.tsx

async function handleFileSelected(file: File) {
  // Extract metadata
  const metadata = await analyzePhoto(file);

  if (metadata.hasGPS && metadata.location) {
    // Suggest nearby building
    const suggested = suggestBuilding(metadata.location, buildings);

    if (suggested) {
      setMessage(`Photo taken near ${suggested.id}. Is this the building?`);
      highlightBuilding(suggested.id);
    } else {
      setMessage('Photo location found, but no nearby buildings. Please select manually.');
    }
  } else {
    setMessage('No GPS data in photo. Please select the building manually.');
  }
}
```

## Privacy Considerations

- EXIF data can reveal user's location
- Consider stripping EXIF before sharing/storing
- Inform users their location may be used

```typescript
// Strip EXIF for storage
async function stripExif(file: File): Promise<Blob> {
  // Canvas method strips all metadata
  const img = await createImageBitmap(file);
  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;

  const ctx = canvas.getContext('2d');
  ctx!.drawImage(img, 0, 0);

  return new Promise(resolve => {
    canvas.toBlob(blob => resolve(blob!), 'image/jpeg', 0.92);
  });
}
```

## Browser Support

exifr works in all modern browsers:

| Browser | Support |
|---------|---------|
| Chrome | ✅ |
| Firefox | ✅ |
| Safari | ✅ |
| Edge | ✅ |
| Mobile Safari | ✅ |
| Chrome Android | ✅ |

## References

- [exifr GitHub](https://github.com/MikeKovarik/exifr)
- [EXIF Standard](https://www.exif.org/)
- [GPS Tags in EXIF](https://exiftool.org/TagNames/GPS.html)
