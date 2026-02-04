/**
 * StylePanel - Sidebar for AI Style Selection
 *
 * Displays available AI tile styles with generation status,
 * tile counts, and color previews.
 */

import type { StylePanelProps, StyleInfo, SatelliteConfig, GeneratorType } from './types';

/** Get indicator status based on tile completion */
function getIndicatorStatus(style: StyleInfo): 'complete' | 'partial' | 'empty' {
  if (style.tiles === 0) return 'empty';
  if (style.tiles >= style.totalTiles) return 'complete';
  return 'partial';
}

/** Format tile count display */
function formatTileCount(style: StyleInfo): string {
  return `${style.tiles}/${style.totalTiles}`;
}

/** Get generator badge label */
function getGeneratorBadge(generator: GeneratorType | undefined): { label: string; className: string } {
  if (generator === 'controlnet') {
    return { label: 'SD', className: 'generator-badge controlnet' };
  }
  return { label: 'Gemini', className: 'generator-badge gemini' };
}

/** Individual style card component */
function StyleCard({
  style,
  isActive,
  onClick,
}: {
  style: StyleInfo | (SatelliteConfig & { isSatellite: true });
  isActive: boolean;
  onClick: () => void;
}) {
  const isSatellite = 'isSatellite' in style;
  const indicatorStatus = isSatellite ? 'satellite' : getIndicatorStatus(style as StyleInfo);
  const isUnavailable = !isSatellite && (style as StyleInfo).tiles === 0;
  const generator = !isSatellite ? (style as StyleInfo).generator : undefined;
  const generatorBadge = !isSatellite ? getGeneratorBadge(generator) : null;

  return (
    <div
      className={`style-card ${isActive ? 'active' : ''} ${isUnavailable ? 'unavailable' : ''}`}
      onClick={isUnavailable ? undefined : onClick}
      role="button"
      tabIndex={isUnavailable ? -1 : 0}
      onKeyDown={(e) => {
        if (!isUnavailable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="style-card-header">
        <div className="style-card-title">
          <div className={`style-indicator ${indicatorStatus}`} />
          <span className="style-card-name">{style.displayName}</span>
        </div>
        <div className="style-card-badges">
          {isSatellite ? (
            <span className="satellite-badge">Live</span>
          ) : (
            <>
              {generatorBadge && (
                <span className={generatorBadge.className}>{generatorBadge.label}</span>
              )}
              <span className="style-card-count">{formatTileCount(style as StyleInfo)}</span>
            </>
          )}
        </div>
      </div>

      <div className="style-card-description">{style.description}</div>

      <div className="style-colors">
        {style.colors.map((color, i) => (
          <div
            key={i}
            className="style-color-swatch"
            style={{ backgroundColor: color }}
            title={color}
          />
        ))}
      </div>

      {!isSatellite && (style as StyleInfo).tiles > 0 && (style as StyleInfo).tiles < (style as StyleInfo).totalTiles && (
        <div className="style-generating">
          <span className="style-generating-dot" />
          <span>Generating...</span>
        </div>
      )}
    </div>
  );
}

export function StylePanel({ manifest, selectedStyle, onStyleSelect, isLoading }: StylePanelProps) {
  if (isLoading) {
    return (
      <div className="styles-panel">
        <div className="styles-panel-header">
          <h2>AI Styles</h2>
          <p>Loading styles...</p>
        </div>
        <div className="styles-loading">Loading...</div>
      </div>
    );
  }

  if (!manifest) {
    return (
      <div className="styles-panel">
        <div className="styles-panel-header">
          <h2>AI Styles</h2>
          <p>No styles available</p>
        </div>
      </div>
    );
  }

  // Calculate stats
  const totalStyles = manifest.styles.length;
  const completeStyles = manifest.styles.filter((s) => s.tiles >= s.totalTiles).length;
  const totalTiles = manifest.styles.reduce((sum, s) => sum + s.tiles, 0);

  return (
    <div className="styles-panel">
      <div className="styles-panel-header">
        <h2>AI Styles</h2>
        <p>AI-generated map visualizations</p>
      </div>

      <div className="styles-list">
        {/* Satellite option first */}
        <StyleCard
          style={{ ...manifest.satellite, isSatellite: true }}
          isActive={selectedStyle === 'satellite'}
          onClick={() => onStyleSelect('satellite')}
        />

        {/* AI styles */}
        {manifest.styles.map((style) => (
          <StyleCard
            key={style.name}
            style={style}
            isActive={selectedStyle === style.name}
            onClick={() => onStyleSelect(style.name)}
          />
        ))}
      </div>

      <div className="styles-panel-footer">
        <div className="styles-stats">
          <div className="styles-stat">
            <span className="styles-stat-label">Styles</span>
            <span className="styles-stat-value">
              {completeStyles}/{totalStyles} complete
            </span>
          </div>
          <div className="styles-stat">
            <span className="styles-stat-label">Total Tiles</span>
            <span className="styles-stat-value">{totalTiles}</span>
          </div>
          <div className="styles-stat">
            <span className="styles-stat-label">Zoom Level</span>
            <span className="styles-stat-value">{manifest.defaultZoom}</span>
          </div>
          <div className="styles-stat">
            <span className="styles-stat-label">Coverage</span>
            <span className="styles-stat-value">City Center</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default StylePanel;
