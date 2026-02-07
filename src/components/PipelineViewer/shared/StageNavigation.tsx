/**
 * StageNavigation - Step Indicator & Navigation
 *
 * Displays clickable stage indicators with connection lines.
 * Shows current stage, visited stages, and allows direct navigation.
 */

import type { StageConfig } from '../types';

interface StageNavigationProps {
  stages: StageConfig[];
  currentStage: number;
  visitedStages: boolean[];
  onStageClick: (index: number) => void;
}

export function StageNavigation({
  stages,
  currentStage,
  visitedStages,
  onStageClick,
}: StageNavigationProps) {
  return (
    <nav className="stage-navigation" aria-label="Pipeline stages">
      {stages.map((stage, index) => {
        const isActive = index === currentStage;
        const isVisited = visitedStages[index];
        const showConnector = index < stages.length - 1;

        return (
          <div key={stage.id} style={{ display: 'flex', alignItems: 'center' }}>
            <button
              className={`stage-nav-item ${isActive ? 'active' : ''} ${
                isVisited ? 'visited' : ''
              }`}
              onClick={() => onStageClick(index)}
              aria-current={isActive ? 'step' : undefined}
              title={`Stage ${stage.number}: ${stage.title}`}
            >
              <span className="stage-nav-number">{stage.number}</span>
              <span className="stage-nav-label">{stage.shortTitle}</span>
            </button>

            {showConnector && (
              <div
                className={`stage-nav-connector ${
                  visitedStages[index + 1] ? 'visited' : ''
                }`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
