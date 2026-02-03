import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { ZurichViewer } from './ZurichViewer';

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
  createTerrainLayer: vi.fn().mockReturnValue({}),
  createMinimapLayers: vi.fn().mockReturnValue([]),
}));

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
