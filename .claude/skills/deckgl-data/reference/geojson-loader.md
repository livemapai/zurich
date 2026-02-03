# GeoJSON Loader Reference

## Standard Loading

```typescript
export async function loadGeoJSON<T extends GeoJSON.FeatureCollection>(
  url: string,
  options?: {
    onProgress?: (progress: number) => void;
  }
): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to load GeoJSON: ${response.statusText}`);
  }

  const data = await response.json();

  // Validate structure
  if (data.type !== 'FeatureCollection') {
    throw new Error('Expected GeoJSON FeatureCollection');
  }

  return data as T;
}
```

## With Progress Tracking

```typescript
export async function loadGeoJSONWithProgress<T>(
  url: string,
  onProgress?: (progress: number) => void
): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const contentLength = response.headers.get('Content-Length');
  const total = contentLength ? parseInt(contentLength, 10) : 0;

  if (!response.body) {
    return response.json();
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    chunks.push(value);
    received += value.length;

    if (total && onProgress) {
      onProgress((received / total) * 100);
    }
  }

  const text = new TextDecoder().decode(
    new Uint8Array(chunks.flatMap((c) => [...c]))
  );

  return JSON.parse(text) as T;
}
```

## React Hook Pattern

```typescript
import { useState, useEffect } from 'react';
import type { LoadingState } from '@/types';

export function useGeoJSONData<T>(url: string | null): LoadingState<T> {
  const [state, setState] = useState<LoadingState<T>>({
    data: null,
    isLoading: false,
    error: null,
    progress: 0,
  });

  useEffect(() => {
    if (!url) return;

    const controller = new AbortController();

    setState((s) => ({ ...s, isLoading: true, error: null, progress: 0 }));

    loadGeoJSONWithProgress<T>(url, (progress) => {
      setState((s) => ({ ...s, progress }));
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, isLoading: false, error: null, progress: 100 });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setState((s) => ({ ...s, isLoading: false, error, progress: 0 }));
        }
      });

    return () => controller.abort();
  }, [url]);

  return state;
}
```
