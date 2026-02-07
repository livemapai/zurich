/**
 * PipelineViewer - Main Container Component
 *
 * Interactive educational visualization explaining how the MapLibre
 * vector tile pipeline works - from raw geodata to rendered map.
 *
 * The pipeline has 6 stages:
 * 1. Data Sources - Where raw geodata comes from
 * 2. Tile Pyramid - How the world is divided into tiles
 * 3. MVT Encoding - Binary encoding with protobuf
 * 4. Schema Layers - Named feature tables
 * 5. Style Spec - MapLibre style definition
 * 6. WebGL Render - GPU triangle rendering
 */

import { useCallback, useEffect } from 'react';
import { usePipelineState, STAGES } from './hooks/usePipelineState';
import { StageNavigation } from './shared/StageNavigation';
import { InfoPanel } from './shared/InfoPanel';
import { DataSourcesStage } from './stages/DataSourcesStage';
import { TilingStage } from './stages/TilingStage';
import { EncodingStage } from './stages/EncodingStage';
import { SchemaStage } from './stages/SchemaStage';
import { StyleStage } from './stages/StyleStage';
import { RenderStage } from './stages/RenderStage';
import '@/styles/pipeline-page.css';

/** Map icon for header */
function MapIcon() {
  return (
    <svg
      className="pipeline-title-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

/** Stage component renderer */
function StageContent({
  stageIndex,
  isActive,
}: {
  stageIndex: number;
  isActive: boolean;
}) {
  const stageId = STAGES[stageIndex]?.id;

  switch (stageId) {
    case 'data-sources':
      return <DataSourcesStage isActive={isActive} />;
    case 'tiling':
      return <TilingStage isActive={isActive} />;
    case 'encoding':
      return <EncodingStage isActive={isActive} />;
    case 'schema':
      return <SchemaStage isActive={isActive} />;
    case 'style':
      return <StyleStage isActive={isActive} />;
    case 'render':
      return <RenderStage isActive={isActive} />;
    default:
      return null;
  }
}

export function PipelineViewer() {
  const {
    state,
    stages,
    currentStageConfig,
    goToStage,
    nextStage,
    prevStage,
    canGoNext,
    canGoPrev,
  } = usePipelineState();

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' && canGoNext) {
        nextStage();
      } else if (e.key === 'ArrowLeft' && canGoPrev) {
        prevStage();
      } else if (e.key >= '1' && e.key <= '6') {
        const index = parseInt(e.key, 10) - 1;
        goToStage(index);
      }
    },
    [canGoNext, canGoPrev, nextStage, prevStage, goToStage]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="pipeline-page">
      {/* Header */}
      <header className="pipeline-header">
        <div className="pipeline-title">
          <MapIcon />
          <h1>MapLibre Pipeline Explorer</h1>
        </div>
        <button
          className="pipeline-help-btn"
          title="Keyboard shortcuts: ← → to navigate, 1-6 to jump"
        >
          ?
        </button>
      </header>

      {/* Stage Navigation */}
      <StageNavigation
        stages={stages}
        currentStage={state.currentStage}
        visitedStages={state.stages.map((s) => s.visited)}
        onStageClick={goToStage}
      />

      {/* Main Content */}
      <main className="pipeline-content">
        {/* Visualization Area */}
        <div className="pipeline-visualization">
          <div className="visualization-container stage-enter" key={state.currentStage}>
            <StageContent
              stageIndex={state.currentStage}
              isActive={true}
            />
          </div>
        </div>

        {/* Info Panel */}
        {currentStageConfig && (
          <InfoPanel
            stageNumber={currentStageConfig.number}
            title={currentStageConfig.title}
            description={currentStageConfig.description}
            insight={currentStageConfig.insight}
            stageId={currentStageConfig.id}
          />
        )}
      </main>

      {/* Footer Navigation */}
      <footer className="pipeline-footer">
        <button
          className="nav-button"
          onClick={prevStage}
          disabled={!canGoPrev}
        >
          <span>←</span>
          <span>Previous</span>
        </button>

        <div className="stage-indicator">
          Stage <strong>{state.currentStage + 1}</strong> of{' '}
          <strong>{stages.length}</strong>
        </div>

        <button
          className="nav-button primary"
          onClick={nextStage}
          disabled={!canGoNext}
        >
          <span>Next</span>
          <span>→</span>
        </button>
      </footer>
    </div>
  );
}

export default PipelineViewer;
