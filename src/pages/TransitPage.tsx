/**
 * TransitPage - Public Transit Visualization
 *
 * A focused view of Zurich's public transit network with animated trails.
 * Inspired by the deck.gl trips example aesthetic with dark theme.
 *
 * Route: /transit
 */

import { useState, useCallback } from 'react';
import { TransitViewer } from '@/components/TransitViewer';

export function TransitPage() {
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
    console.error('Transit viewer error:', err);
    setError(err);
    setIsLoading(false);
  }, []);

  if (error) {
    return (
      <div
        className="transit-page"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <h1 style={{ marginBottom: '1rem', color: '#ff6b6b' }}>Error</h1>
          <p style={{ marginBottom: '1rem' }}>{error.message}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1rem',
              background: '#00d4ff',
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
    <div className="transit-page no-select">
      {/* Loading overlay */}
      {isLoading && (
        <div className="transit-loading-overlay">
          <p className="transit-loading-text">Loading Transit Network...</p>
          <div className="transit-loading-progress">
            <div
              className="transit-loading-progress-bar"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', opacity: 0.7 }}>
            {loadProgress.toFixed(0)}%
          </p>
        </div>
      )}

      {/* Main transit viewer */}
      <TransitViewer
        onLoadProgress={handleLoadProgress}
        onError={handleError}
      />
    </div>
  );
}

export default TransitPage;
