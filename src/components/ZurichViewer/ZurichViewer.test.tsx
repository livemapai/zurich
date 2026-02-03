import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { ZurichViewer } from './ZurichViewer';

// Mock maplibre-gl to avoid browser API requirements in tests
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      on: vi.fn(),
      off: vi.fn(),
      remove: vi.fn(),
      getSource: vi.fn().mockReturnValue({}),
      triggerRepaint: vi.fn(),
      queryTerrainElevation: vi.fn().mockReturnValue(408),
    })),
    LngLatBounds: vi.fn().mockImplementation(() => ({})),
  },
  Map: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    off: vi.fn(),
    remove: vi.fn(),
    getSource: vi.fn().mockReturnValue({}),
    triggerRepaint: vi.fn(),
    queryTerrainElevation: vi.fn().mockReturnValue(408),
  })),
  LngLatBounds: vi.fn().mockImplementation(() => ({})),
}));

// Mock deck.gl modules
vi.mock('@deck.gl/react', () => ({
  default: ({ children, onWebGLInitialized }: { children?: React.ReactNode; onWebGLInitialized?: () => void }) => {
    // Simulate WebGL initialization
    if (onWebGLInitialized) {
      setTimeout(onWebGLInitialized, 0);
    }
    return <div data-testid="deckgl-mock">{children}</div>;
  },
}));

vi.mock('@deck.gl/core', () => ({
  FirstPersonView: vi.fn().mockImplementation(() => ({
    id: 'first-person',
  })),
  OrthographicView: vi.fn().mockImplementation(() => ({
    id: 'orthographic',
  })),
  LightingEffect: vi.fn().mockImplementation(() => ({})),
  AmbientLight: vi.fn().mockImplementation(() => ({})),
  DirectionalLight: vi.fn().mockImplementation(() => ({})),
}));

// Mock layers module
vi.mock('@/layers', () => ({
  createBuildingsLayer: vi.fn().mockReturnValue({}),
  createMapTileLayer: vi.fn().mockReturnValue({}),
  createMapterhornTerrainLayer: vi.fn().mockReturnValue({}),
  createTreesLayer: vi.fn().mockReturnValue({}),
  createLightsLayer: vi.fn().mockReturnValue({}),
  createMinimapLayers: vi.fn().mockReturnValue([]),
  createTramTracksLayer: vi.fn().mockReturnValue({}),
  createOverheadPolesLayer: vi.fn().mockReturnValue({}),
  TEXTURE_PROVIDERS: {
    osm: { name: 'OpenStreetMap', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png' },
    satellite: { name: 'Satellite (Esri)', url: 'https://server.arcgisonline.com/test/{z}/{y}/{x}' },
    swissimage: { name: 'Swiss Satellite', url: 'https://wmts.geo.admin.ch/test/{z}/{x}/{y}.jpeg' },
    cartoDark: { name: 'Dark (Carto)', url: 'https://a.basemaps.cartocdn.com/test/{z}/{x}/{y}.png' },
  },
  SWISS_ZOOM_THRESHOLD: 12,
}));

// Mock utils for zoom calculation
vi.mock('@/utils', async () => {
  const actual = await vi.importActual('@/utils');
  return {
    ...actual,
    // Return high zoom (>12) so swissimage stays swissimage in tests
    calculateEffectiveZoom: vi.fn().mockReturnValue(16),
  };
});

// Mock Minimap component
vi.mock('@/components/Minimap', () => ({
  Minimap: () => <div data-testid="minimap-mock" />,
}));

describe('ZurichViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render without crashing', () => {
    const { container } = render(<ZurichViewer />);
    expect(container).toBeDefined();
  });

  it('should call onLoadProgress with increasing values', async () => {
    const onLoadProgress = vi.fn();
    render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      expect(onLoadProgress).toHaveBeenCalled();
    }, { timeout: 2000 });

    // Should receive progress updates
    const calls = onLoadProgress.mock.calls;
    expect(calls.length).toBeGreaterThan(0);

    // Progress values should increase
    const progressValues = calls.map(call => call[0] as number);
    for (let i = 1; i < progressValues.length; i++) {
      expect(progressValues[i]).toBeGreaterThanOrEqual(progressValues[i - 1]!);
    }
  });

  it('should call onLoadProgress with 100 when loading completes', async () => {
    const onLoadProgress = vi.fn();
    render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      const calls = onLoadProgress.mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall?.[0]).toBe(100);
    }, { timeout: 2000 });
  });

  it('should not show crosshair when pointer is not locked', async () => {
    const onLoadProgress = vi.fn();
    const { container } = render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    // Wait for component to be ready
    await waitFor(() => {
      expect(onLoadProgress).toHaveBeenCalledWith(100);
    }, { timeout: 2000 });

    // Crosshair should NOT be visible when pointer is not locked
    const crosshair = container.querySelector('.crosshair');
    expect(crosshair).not.toBeInTheDocument();
  });

  it('should show controls hint when ready', async () => {
    const onLoadProgress = vi.fn();
    const { container } = render(<ZurichViewer onLoadProgress={onLoadProgress} />);

    await waitFor(() => {
      const hint = container.querySelector('.controls-hint');
      expect(hint).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('should render DeckGL component', () => {
    const { getByTestId } = render(<ZurichViewer />);
    expect(getByTestId('deckgl-mock')).toBeInTheDocument();
  });
});
