import { useState, useCallback } from 'react';
import { ZurichViewer } from './components/ZurichViewer';
import { CONFIG } from './lib/config';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  const handleLoadProgress = useCallback((progress: number) => {
    setLoadProgress(progress);
    if (progress >= 100) {
      setIsLoading(false);
    }
  }, []);

  const handleError = useCallback((err: Error) => {
    console.error('Viewer error:', err);
    setError(err);
    setIsLoading(false);
  }, []);

  if (error) {
    return (
      <div className="viewport" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <h1 style={{ marginBottom: '1rem', color: '#ff6b6b' }}>Error</h1>
          <p style={{ marginBottom: '1rem' }}>{error.message}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1rem',
              background: '#4a9eff',
              border: 'none',
              borderRadius: '4px',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="viewport no-select">
      {/* Loading overlay */}
      {isLoading && (
        <div className="loading-overlay">
          <p className="loading-text">Loading Zurich 3D...</p>
          <div className="loading-progress">
            <div
              className="loading-progress-bar"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', opacity: 0.7 }}>
            {loadProgress.toFixed(0)}%
          </p>
        </div>
      )}

      {/* Main viewer */}
      <ZurichViewer
        onLoadProgress={handleLoadProgress}
        onError={handleError}
      />

      {/* Debug panel (dev only) */}
      {CONFIG.debug.showDebugPanel && !isLoading && (
        <div className="debug-panel">
          <p>Debug Mode</p>
        </div>
      )}
    </div>
  );
}

export default App;
