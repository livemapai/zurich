/**
 * RenderStage - Stage 6: WebGL Rendering Pipeline
 *
 * Visualizes how vector data becomes pixels via WebGL:
 * - Tessellation: Polygons → triangles
 * - Vertex buffers: Upload to GPU memory
 * - Shaders: GPU programs for vertex/fragment processing
 * - Draw calls: Per-layer rendering
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { StageProps, RenderStats } from '../types';

/** Simulated render stats */
const SIMULATED_STATS: RenderStats = {
  drawCalls: 42,
  triangles: 84500,
  frameTime: 8.3,
  tilesLoaded: 16,
};

/** Pipeline stages */
const PIPELINE_STAGES = [
  {
    id: 'decode',
    name: 'Decode',
    location: 'Web Worker',
    description: 'MVT protobuf → geometry',
    color: '#88c0ff',
  },
  {
    id: 'tessellate',
    name: 'Tessellate',
    location: 'CPU',
    description: 'Polygons → triangles',
    color: '#c792ea',
  },
  {
    id: 'upload',
    name: 'Upload',
    location: 'GPU',
    description: 'Vertices → buffers',
    color: '#ff8c00',
  },
  {
    id: 'draw',
    name: 'Draw',
    location: 'GPU',
    description: 'Shaders → pixels',
    color: '#4ade80',
  },
];

/** Render order layers */
const RENDER_ORDER = [
  { name: 'Background', type: 'fill', color: '#1a1a2e' },
  { name: 'Water', type: 'fill', color: '#5b9bd5' },
  { name: 'Landuse', type: 'fill', color: '#3d5a3d' },
  { name: 'Buildings', type: 'fill', color: '#8b7355' },
  { name: 'Roads', type: 'line', color: '#e0e0e0' },
  { name: 'Labels', type: 'symbol', color: '#ffffff' },
];

/** Format large numbers */
function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

/** Render Stats Display */
function RenderStatsPanel({ stats }: { stats: RenderStats }) {
  const getFrameStatus = (time: number) => {
    if (time < 16) return 'healthy';
    if (time < 33) return 'warning';
    return 'danger';
  };

  return (
    <div className="render-stats-panel">
      <h4>Real-time Metrics</h4>
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Draw Calls</span>
          <span className={`stat-value ${stats.drawCalls > 100 ? 'warning' : ''}`}>
            {stats.drawCalls}
          </span>
          <span className="stat-threshold">&lt; 50 optimal</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Triangles</span>
          <span className={`stat-value ${stats.triangles > 200000 ? 'warning' : ''}`}>
            {formatNumber(stats.triangles)}
          </span>
          <span className="stat-threshold">&lt; 100K optimal</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Frame Time</span>
          <span className={`stat-value ${getFrameStatus(stats.frameTime)}`}>
            {stats.frameTime.toFixed(1)}ms
          </span>
          <span className="stat-threshold">&lt; 16ms for 60fps</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Tiles Loaded</span>
          <span className="stat-value">{stats.tilesLoaded}</span>
          <span className="stat-threshold">in viewport</span>
        </div>
      </div>
    </div>
  );
}

/** Pipeline Diagram */
function PipelineDiagram({
  activeStage,
  onStageClick,
}: {
  activeStage: string | null;
  onStageClick: (id: string) => void;
}) {
  return (
    <div className="pipeline-diagram">
      {PIPELINE_STAGES.map((stage, index) => (
        <div key={stage.id} className="pipeline-item">
          <button
            className={`pipeline-node ${activeStage === stage.id ? 'active' : ''}`}
            onClick={() => onStageClick(stage.id)}
            style={{ borderColor: stage.color }}
          >
            <span className="node-name">{stage.name}</span>
            <span className="node-location">{stage.location}</span>
          </button>
          {index < PIPELINE_STAGES.length - 1 && (
            <div className="pipeline-arrow">→</div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Wireframe Toggle Visualization */
function WireframeDemo({ showWireframe }: { showWireframe: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Draw sample building with/without wireframe
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, width, height);

    // Sample building polygon (tessellated into triangles)
    const building: [number, number][] = [
      [60, 140], [140, 140], [140, 60], [60, 60],
    ];

    // Triangles from tessellation
    const triangles: [number, number][][] = [
      [[60, 140], [140, 140], [140, 60]],
      [[60, 140], [140, 60], [60, 60]],
    ];

    if (showWireframe) {
      // Draw triangles with wireframe
      triangles.forEach((tri, i) => {
        const p0 = tri[0]!;
        const p1 = tri[1]!;
        const p2 = tri[2]!;
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.closePath();
        ctx.fillStyle = i === 0 ? 'rgba(136, 192, 255, 0.2)' : 'rgba(199, 146, 234, 0.2)';
        ctx.fill();
        ctx.strokeStyle = i === 0 ? '#88c0ff' : '#c792ea';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      // Draw vertices
      triangles.flat().forEach((point) => {
        ctx.beginPath();
        ctx.arc(point[0], point[1], 4, 0, Math.PI * 2);
        ctx.fillStyle = '#ff8c00';
        ctx.fill();
      });

      // Labels
      ctx.font = '10px SF Mono, monospace';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.fillText('Triangle 1', 80, 110);
      ctx.fillText('Triangle 2', 80, 90);
    } else {
      // Draw solid building
      const start = building[0]!;
      ctx.beginPath();
      ctx.moveTo(start[0], start[1]);
      building.forEach((point) => ctx.lineTo(point[0], point[1]));
      ctx.closePath();
      ctx.fillStyle = '#8b7355';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Second building (more complex)
    const building2: [number, number][] = [
      [180, 150], [260, 150], [260, 100], [220, 80], [180, 100],
    ];

    const triangles2: [number, number][][] = [
      [[180, 150], [260, 150], [260, 100]],
      [[180, 150], [260, 100], [220, 80]],
      [[180, 150], [220, 80], [180, 100]],
    ];

    if (showWireframe) {
      triangles2.forEach((tri, i) => {
        const p0 = tri[0]!;
        const p1 = tri[1]!;
        const p2 = tri[2]!;
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.closePath();
        ctx.fillStyle = `rgba(${74 + i * 30}, ${222 - i * 40}, ${128 + i * 40}, 0.2)`;
        ctx.fill();
        ctx.strokeStyle = `hsl(${160 + i * 30}, 70%, 60%)`;
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      triangles2.flat().forEach((point) => {
        ctx.beginPath();
        ctx.arc(point[0], point[1], 4, 0, Math.PI * 2);
        ctx.fillStyle = '#ff8c00';
        ctx.fill();
      });
    } else {
      const start2 = building2[0]!;
      ctx.beginPath();
      ctx.moveTo(start2[0], start2[1]);
      building2.forEach((point) => ctx.lineTo(point[0], point[1]));
      ctx.closePath();
      ctx.fillStyle = '#6b8e6b';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.stroke();
    }
  }, [showWireframe]);

  return (
    <canvas
      ref={canvasRef}
      width={320}
      height={200}
      className="wireframe-canvas"
    />
  );
}

/** Layer Render Order */
function RenderOrderDemo({
  activeLayer,
  onLayerClick,
}: {
  activeLayer: number;
  onLayerClick: (index: number) => void;
}) {
  return (
    <div className="render-order-demo">
      <h4>Layer Render Order</h4>
      <p className="render-hint">
        Layers render bottom-to-top. Click to highlight:
      </p>
      <div className="render-stack">
        {RENDER_ORDER.map((layer, index) => (
          <button
            key={layer.name}
            className={`render-layer ${index <= activeLayer ? 'rendered' : ''} ${
              index === activeLayer ? 'active' : ''
            }`}
            onClick={() => onLayerClick(index)}
            style={{
              '--layer-color': layer.color,
              transform: `translateY(${(RENDER_ORDER.length - 1 - index) * 4}px)`,
            } as React.CSSProperties}
          >
            <span className="layer-index">{index + 1}</span>
            <span className="layer-name">{layer.name}</span>
            <span className="layer-type">{layer.type}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function RenderStage({ isActive }: StageProps) {
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [showWireframe, setShowWireframe] = useState(false);
  const [activeRenderLayer, setActiveRenderLayer] = useState(5);
  const [stats, setStats] = useState(SIMULATED_STATS);

  // Simulate fluctuating stats
  useEffect(() => {
    if (!isActive) return;

    const interval = setInterval(() => {
      setStats((prev) => ({
        ...prev,
        frameTime: 7 + Math.random() * 4,
        triangles: 80000 + Math.floor(Math.random() * 10000),
      }));
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive]);

  const handleStageClick = useCallback((id: string) => {
    setActiveStage((prev) => (prev === id ? null : id));
  }, []);

  if (!isActive) return null;

  const activeStageInfo = PIPELINE_STAGES.find((s) => s.id === activeStage);

  return (
    <div className="render-stage">
      <div className="render-content">
        {/* Pipeline Diagram */}
        <div className="render-section">
          <h3>GPU Rendering Pipeline</h3>
          <PipelineDiagram
            activeStage={activeStage}
            onStageClick={handleStageClick}
          />
          {activeStageInfo && (
            <div
              className="stage-detail"
              style={{ borderColor: activeStageInfo.color }}
            >
              <strong>{activeStageInfo.name}</strong>
              <span className="stage-location">({activeStageInfo.location})</span>
              <p>{activeStageInfo.description}</p>
            </div>
          )}
        </div>

        {/* Wireframe Toggle */}
        <div className="render-section">
          <div className="section-header">
            <h3>Tessellation</h3>
            <button
              className={`wireframe-toggle ${showWireframe ? 'active' : ''}`}
              onClick={() => setShowWireframe(!showWireframe)}
            >
              {showWireframe ? 'Show Filled' : 'Show Wireframe'}
            </button>
          </div>
          <WireframeDemo showWireframe={showWireframe} />
          <p className="render-hint">
            {showWireframe
              ? 'Polygons must be split into triangles - GPU only draws triangles.'
              : 'Click "Show Wireframe" to see the underlying triangle mesh.'}
          </p>
        </div>

        {/* Render Stats */}
        <RenderStatsPanel stats={stats} />

        {/* Layer Render Order */}
        <RenderOrderDemo
          activeLayer={activeRenderLayer}
          onLayerClick={setActiveRenderLayer}
        />
      </div>

      <style>{`
        .render-stage {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          width: 100%;
          height: 100%;
          overflow-y: auto;
        }

        .render-content {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1.5rem;
          width: 100%;
          max-width: 900px;
        }

        .render-section {
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
        }

        .render-section h3 {
          margin: 0 0 1rem;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 1rem;
        }

        .section-header h3 {
          margin: 0;
        }

        /* Pipeline Diagram */
        .pipeline-diagram {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.25rem;
          flex-wrap: wrap;
        }

        .pipeline-item {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }

        .pipeline-node {
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.03);
          border: 2px solid;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
          text-align: center;
        }

        .pipeline-node:hover {
          background: rgba(255, 255, 255, 0.06);
        }

        .pipeline-node.active {
          background: rgba(136, 192, 255, 0.1);
        }

        .node-name {
          display: block;
          font-weight: 600;
          color: #fff;
          font-size: 0.8125rem;
        }

        .node-location {
          display: block;
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .pipeline-arrow {
          color: rgba(255, 255, 255, 0.3);
        }

        .stage-detail {
          margin-top: 1rem;
          padding: 0.75rem;
          background: rgba(0, 0, 0, 0.2);
          border-left: 3px solid;
          border-radius: 0 6px 6px 0;
        }

        .stage-detail strong {
          color: #fff;
        }

        .stage-location {
          color: rgba(255, 255, 255, 0.5);
          font-size: 0.8125rem;
          margin-left: 0.5rem;
        }

        .stage-detail p {
          margin: 0.5rem 0 0;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.7);
        }

        /* Wireframe */
        .wireframe-toggle {
          padding: 0.375rem 0.75rem;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          color: rgba(255, 255, 255, 0.7);
          font-size: 0.75rem;
          cursor: pointer;
          transition: all 0.2s;
        }

        .wireframe-toggle:hover,
        .wireframe-toggle.active {
          background: rgba(136, 192, 255, 0.15);
          border-color: rgba(136, 192, 255, 0.3);
          color: #88c0ff;
        }

        .wireframe-canvas {
          width: 100%;
          max-width: 320px;
          display: block;
          margin: 0 auto;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
        }

        .render-hint {
          margin: 0.75rem 0 0;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          text-align: center;
        }

        /* Stats Panel */
        .render-stats-panel {
          grid-column: 1 / -1;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
        }

        .render-stats-panel h4 {
          margin: 0 0 1rem;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 1rem;
        }

        .stat-card {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
        }

        .stat-label {
          font-size: 0.6875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
          margin-bottom: 0.375rem;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 600;
          color: #4ade80;
        }

        .stat-value.warning {
          color: #fbbf24;
        }

        .stat-value.danger {
          color: #f87171;
        }

        .stat-value.healthy {
          color: #4ade80;
        }

        .stat-threshold {
          font-size: 0.625rem;
          color: rgba(255, 255, 255, 0.4);
          margin-top: 0.25rem;
        }

        /* Render Order */
        .render-order-demo {
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
        }

        .render-order-demo h4 {
          margin: 0 0 0.5rem;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .render-stack {
          display: flex;
          flex-direction: column-reverse;
          gap: 0.375rem;
          perspective: 500px;
        }

        .render-layer {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.3s;
          opacity: 0.4;
        }

        .render-layer.rendered {
          opacity: 0.7;
          background: rgba(var(--layer-color-rgb, 136, 192, 255), 0.05);
        }

        .render-layer.active {
          opacity: 1;
          border-color: var(--layer-color);
          box-shadow: 0 0 12px color-mix(in srgb, var(--layer-color) 30%, transparent);
        }

        .render-layer .layer-index {
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--layer-color);
          color: #0a0a12;
          border-radius: 50%;
          font-size: 0.6875rem;
          font-weight: 600;
        }

        .render-layer .layer-name {
          flex: 1;
          color: #fff;
          font-size: 0.8125rem;
        }

        .render-layer .layer-type {
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.5);
        }

        @media (max-width: 768px) {
          .render-content {
            grid-template-columns: 1fr;
          }

          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      `}</style>
    </div>
  );
}
