/**
 * usePipelineState Hook
 *
 * Manages the state for the pipeline visualization including:
 * - Current stage tracking
 * - Stage visit history
 * - Per-stage custom data
 */

import { useState, useCallback, useEffect } from 'react';
import type { PipelineState, StageId, StageConfig } from '../types';

/** All 6 stages of the pipeline */
export const STAGES: StageConfig[] = [
  {
    id: 'data-sources',
    number: 1,
    title: 'Data Sources',
    shortTitle: 'Data',
    description:
      'Raw geodata comes from various sources: OpenStreetMap, GeoJSON files, Shapefiles, or PostGIS databases. Each format has trade-offs between size, editability, and query capabilities.',
    insight:
      'All formats ultimately describe the same thing: geometry (points/lines/polygons) + attributes (key-value properties).',
  },
  {
    id: 'tiling',
    number: 2,
    title: 'Tile Pyramid',
    shortTitle: 'Tile',
    description:
      'The world is divided into a pyramid of square tiles. At zoom 0, the entire world fits in one tile. Each zoom level quadruples the tile count, enabling progressive detail loading.',
    insight:
      'Zoom 16 is the sweet spot for city maps – enough detail for buildings, but only ~17,000 tiles for a city like Zurich.',
  },
  {
    id: 'encoding',
    number: 3,
    title: 'MVT Encoding',
    shortTitle: 'MVT',
    description:
      'Mapbox Vector Tiles (MVT) use Protocol Buffers for efficient binary encoding. Geometry is encoded as commands (MoveTo, LineTo, ClosePath) with delta and zigzag encoding for compression.',
    insight:
      'A building polygon with 4 corners + 5 attributes might be 200 bytes in GeoJSON but only 40 bytes in MVT – 5× smaller!',
  },
  {
    id: 'schema',
    number: 4,
    title: 'Schema Layers',
    shortTitle: 'Schema',
    description:
      'Each tile contains named layers (building, road, water). TileJSON metadata describes available layers and their fields. The same source layer can be styled as multiple visual layers.',
    insight:
      'The same "road" source-layer can become "highway" (thick, orange), "street" (thin, white), and "path" (dashed, gray).',
  },
  {
    id: 'style',
    number: 5,
    title: 'Style Specification',
    shortTitle: 'Style',
    description:
      'The MapLibre Style Spec defines sources, layers, and how to render features. Paint properties control appearance; expressions enable data-driven styling.',
    insight:
      'The style spec is the "brain" of the map – same tiles, different style = completely different map!',
  },
  {
    id: 'render',
    number: 6,
    title: 'WebGL Rendering',
    shortTitle: 'Render',
    description:
      'Vector data becomes pixels via WebGL. Polygons are tessellated into triangles, uploaded to GPU memory, and drawn with shaders. MapLibre handles tile management and layer ordering.',
    insight:
      'MapLibre renders ~100+ tiles per second with millions of triangles because the GPU does the heavy lifting.',
  },
];

/** Initial state factory */
function createInitialState(): PipelineState {
  return {
    currentStage: 0,
    stages: STAGES.map((s) => ({
      id: s.id,
      visited: false,
      data: {},
    })),
  };
}

/** Parse URL hash for initial stage */
function getStageFromHash(): number {
  if (typeof window === 'undefined') return 0;
  const hash = window.location.hash.replace('#', '');
  const stageIndex = STAGES.findIndex((s) => s.id === hash);
  return stageIndex >= 0 ? stageIndex : 0;
}

export function usePipelineState() {
  const [state, setState] = useState<PipelineState>(() => {
    const initial = createInitialState();
    const hashStage = getStageFromHash();
    return {
      ...initial,
      currentStage: hashStage,
      stages: initial.stages.map((s, i) =>
        i === hashStage ? { ...s, visited: true } : s
      ),
    };
  });

  // Sync URL hash with current stage
  useEffect(() => {
    const stageId = STAGES[state.currentStage]?.id;
    if (stageId && typeof window !== 'undefined') {
      window.history.replaceState(null, '', `#${stageId}`);
    }
  }, [state.currentStage]);

  // Handle browser back/forward
  useEffect(() => {
    function handleHashChange() {
      const newStage = getStageFromHash();
      setState((prev) => ({
        ...prev,
        currentStage: newStage,
        stages: prev.stages.map((s, i) =>
          i === newStage ? { ...s, visited: true } : s
        ),
      }));
    }

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  /** Navigate to a specific stage by index */
  const goToStage = useCallback((index: number) => {
    if (index < 0 || index >= STAGES.length) return;

    setState((prev) => ({
      ...prev,
      currentStage: index,
      stages: prev.stages.map((s, i) =>
        i === index ? { ...s, visited: true } : s
      ),
    }));
  }, []);

  /** Navigate to next stage */
  const nextStage = useCallback(() => {
    setState((prev) => {
      const next = Math.min(prev.currentStage + 1, STAGES.length - 1);
      return {
        ...prev,
        currentStage: next,
        stages: prev.stages.map((s, i) =>
          i === next ? { ...s, visited: true } : s
        ),
      };
    });
  }, []);

  /** Navigate to previous stage */
  const prevStage = useCallback(() => {
    setState((prev) => ({
      ...prev,
      currentStage: Math.max(prev.currentStage - 1, 0),
    }));
  }, []);

  /** Update data for a specific stage */
  const updateStageData = useCallback(
    (stageId: StageId, data: Record<string, unknown>) => {
      setState((prev) => ({
        ...prev,
        stages: prev.stages.map((s) =>
          s.id === stageId ? { ...s, data: { ...s.data, ...data } } : s
        ),
      }));
    },
    []
  );

  /** Get current stage config */
  const currentStageConfig = STAGES[state.currentStage];

  /** Check if we can navigate */
  const canGoNext = state.currentStage < STAGES.length - 1;
  const canGoPrev = state.currentStage > 0;

  return {
    state,
    stages: STAGES,
    currentStageConfig,
    goToStage,
    nextStage,
    prevStage,
    updateStageData,
    canGoNext,
    canGoPrev,
  };
}
