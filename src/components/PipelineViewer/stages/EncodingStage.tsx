/**
 * EncodingStage - Stage 3: MVT Encoding
 *
 * Visualizes how geometry is efficiently encoded in MVT format:
 * - Protobuf binary serialization
 * - 4096×4096 tile extent coordinate system
 * - Geometry commands: MoveTo(1), LineTo(2), ClosePath(7)
 * - Delta encoding (differences, not absolute values)
 * - Zigzag encoding for signed integers
 * - Key/value deduplication
 */

import { useState, useMemo, useCallback } from 'react';
import type { StageProps, GeometryCommand } from '../types';

/** Sample geometry commands for a building polygon */
const SAMPLE_COMMANDS: GeometryCommand[] = [
  { type: 'MoveTo', x: 100, y: 100 },
  { type: 'LineTo', dx: 60, dy: 0 },
  { type: 'LineTo', dx: 0, dy: 40 },
  { type: 'LineTo', dx: -60, dy: 0 },
  { type: 'ClosePath' },
];

/** Format command for display */
function formatCommand(cmd: GeometryCommand): string {
  switch (cmd.type) {
    case 'MoveTo':
      return `MoveTo(${cmd.x}, ${cmd.y})`;
    case 'LineTo':
      return `LineTo(${cmd.dx! >= 0 ? '+' : ''}${cmd.dx}, ${cmd.dy! >= 0 ? '+' : ''}${cmd.dy})`;
    case 'ClosePath':
      return 'ClosePath()';
    default:
      return '';
  }
}

/** Zigzag encoding formula */
function zigzag(n: number): number {
  return (n << 1) ^ (n >> 31);
}

/** Geometry Visualizer Component */
function GeometryVisualizer({
  commands,
  currentStep,
}: {
  commands: GeometryCommand[];
  currentStep: number;
}) {
  // Build path up to current step
  const pathData = useMemo(() => {
    let path = '';
    let cursor = { x: 0, y: 0 };

    for (let i = 0; i <= currentStep && i < commands.length; i++) {
      const cmd = commands[i];
      if (!cmd) continue;
      if (cmd.type === 'MoveTo' && cmd.x !== undefined && cmd.y !== undefined) {
        cursor = { x: cmd.x, y: cmd.y };
        path += `M ${cursor.x} ${cursor.y} `;
      } else if (cmd.type === 'LineTo' && cmd.dx !== undefined && cmd.dy !== undefined) {
        cursor = { x: cursor.x + cmd.dx, y: cursor.y + cmd.dy };
        path += `L ${cursor.x} ${cursor.y} `;
      } else if (cmd.type === 'ClosePath') {
        path += 'Z ';
      }
    }

    return { path, cursor };
  }, [commands, currentStep]);

  return (
    <svg viewBox="0 0 256 200" className="geometry-svg">
      {/* Grid */}
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <rect width="20" height="20" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="256" height="200" fill="url(#grid)" />

      {/* Coordinate axes */}
      <line x1="0" y1="0" x2="256" y2="0" stroke="rgba(136,192,255,0.3)" strokeWidth="1" />
      <line x1="0" y1="0" x2="0" y2="200" stroke="rgba(136,192,255,0.3)" strokeWidth="1" />

      {/* Extent label */}
      <text x="248" y="12" fill="rgba(255,255,255,0.3)" fontSize="8" textAnchor="end">
        4096 extent
      </text>

      {/* Path */}
      <path
        d={pathData.path}
        fill="rgba(136, 192, 255, 0.2)"
        stroke="#88c0ff"
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* Cursor */}
      {currentStep < commands.length && (
        <circle
          cx={pathData.cursor.x}
          cy={pathData.cursor.y}
          r="5"
          fill="#ff8c00"
          className="pulse-animation"
        />
      )}

      {/* Scale indicator */}
      <g transform="translate(10, 180)">
        <line x1="0" y1="0" x2="40" y2="0" stroke="rgba(255,255,255,0.5)" strokeWidth="1" />
        <text x="20" y="12" fill="rgba(255,255,255,0.5)" fontSize="8" textAnchor="middle">
          ~10m
        </text>
      </g>
    </svg>
  );
}

/** Zigzag Encoding Demo - ENHANCED with deep explanations */
function ZigzagDemo() {
  const [inputValue, setInputValue] = useState(-20);
  const [showExplanation, setShowExplanation] = useState(true);

  const encoded = zigzag(inputValue);

  // Calculate binary representations for educational display
  const signedBinary = inputValue >= 0
    ? inputValue.toString(2).padStart(8, '0')
    : (inputValue >>> 0).toString(2).slice(-8);
  const unsignedBinary = encoded.toString(2).padStart(8, '0');

  return (
    <div className="zigzag-demo-enhanced">
      {/* Explanation Section */}
      <div className="explanation-section">
        <div
          className="explanation-header"
          onClick={() => setShowExplanation(!showExplanation)}
        >
          <h4>🤔 Why Zigzag Encoding?</h4>
          <span className="expand-toggle">{showExplanation ? '−' : '+'}</span>
        </div>

        {showExplanation && (
          <div className="explanation-content">
            <div className="problem-box">
              <h5>THE PROBLEM WITH NEGATIVE NUMBERS:</h5>
              <p>
                When you store coordinates, you often have small negative numbers:<br/>
                <code>Move left 5 units = -5</code>
              </p>
              <p>
                In normal binary (two's complement), <strong>-1</strong> is stored as:<br/>
                <code className="binary-bad">11111111 11111111 11111111 11111111</code><br/>
                <span className="problem-note">32 ones! This compresses TERRIBLY.</span>
              </p>
            </div>

            <div className="solution-box">
              <h5>ZIGZAG SOLUTION:</h5>
              <p>
                Interleave positive and negative values so small numbers stay small:
              </p>
              <div className="mapping-table">
                <div className="mapping-row header">
                  <span>Original</span>
                  <span>→</span>
                  <span>Zigzag</span>
                </div>
                <div className="mapping-row"><span>0</span><span>→</span><span>0</span></div>
                <div className="mapping-row negative"><span>-1</span><span>→</span><span>1</span></div>
                <div className="mapping-row"><span>1</span><span>→</span><span>2</span></div>
                <div className="mapping-row negative"><span>-2</span><span>→</span><span>3</span></div>
                <div className="mapping-row"><span>2</span><span>→</span><span>4</span></div>
                <div className="mapping-row negative"><span>-3</span><span>→</span><span>5</span></div>
              </div>
            </div>

            <div className="formula-box">
              <h5>THE FORMULA:</h5>
              <code className="formula">Encode: (n &lt;&lt; 1) ^ (n &gt;&gt; 31)</code>
              <code className="formula">Decode: (n &gt;&gt;&gt; 1) ^ -(n &amp; 1)</code>
            </div>

            <div className="savings-table">
              <h5>WHY THIS MATTERS:</h5>
              <div className="savings-row header">
                <span>Value</span>
                <span>Normal Binary</span>
                <span>Zigzag Binary</span>
                <span>Savings</span>
              </div>
              <div className="savings-row">
                <span>-1</span>
                <span className="binary-bad">11111111...</span>
                <span className="binary-good">00000001</span>
                <span className="savings">87%</span>
              </div>
              <div className="savings-row">
                <span>-5</span>
                <span className="binary-bad">11111011...</span>
                <span className="binary-good">00001001</span>
                <span className="savings">85%</span>
              </div>
              <div className="savings-row">
                <span>-100</span>
                <span className="binary-bad">10011100...</span>
                <span className="binary-good">11000111</span>
                <span className="savings">50%</span>
              </div>
            </div>

            <p className="key-insight">
              💡 Small numbers (common in delta-encoded coordinates) compress beautifully!
            </p>
          </div>
        )}
      </div>

      {/* Interactive Demo */}
      <div className="interactive-demo">
        <h4>Try it yourself:</h4>
        <div className="zigzag-input">
          <label>Signed integer:</label>
          <input
            type="range"
            min={-50}
            max={50}
            value={inputValue}
            onChange={(e) => setInputValue(parseInt(e.target.value, 10))}
          />
          <span className="zigzag-value">{inputValue}</span>
        </div>

        <div className="zigzag-conversion">
          <div className="conversion-step">
            <span className="step-label">Input (signed)</span>
            <span className="step-value signed">{inputValue}</span>
            <span className="step-binary">{signedBinary}</span>
          </div>
          <div className="conversion-arrow">↓ zigzag</div>
          <div className="conversion-step">
            <span className="step-label">Output (unsigned)</span>
            <span className="step-value unsigned">{encoded}</span>
            <span className="step-binary good">{unsignedBinary}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Protobuf Structure Visualization */
function ProtobufStructure() {
  const [expanded, setExpanded] = useState<string[]>(['tile']);

  const toggle = (id: string) => {
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div className="protobuf-tree">
      <div className="tree-node" onClick={() => toggle('tile')}>
        <span className="tree-toggle">{expanded.includes('tile') ? '▼' : '▶'}</span>
        <span className="tree-type">Tile</span>
      </div>

      {expanded.includes('tile') && (
        <div className="tree-children">
          <div className="tree-node" onClick={() => toggle('layer')}>
            <span className="tree-toggle">{expanded.includes('layer') ? '▼' : '▶'}</span>
            <span className="tree-type">Layer[]</span>
            <span className="tree-field">layers</span>
          </div>

          {expanded.includes('layer') && (
            <div className="tree-children">
              <div className="tree-leaf">
                <span className="tree-type">string</span>
                <span className="tree-field">name</span>
                <span className="tree-value">"building"</span>
              </div>
              <div className="tree-node" onClick={() => toggle('features')}>
                <span className="tree-toggle">{expanded.includes('features') ? '▼' : '▶'}</span>
                <span className="tree-type">Feature[]</span>
                <span className="tree-field">features</span>
              </div>

              {expanded.includes('features') && (
                <div className="tree-children">
                  <div className="tree-leaf">
                    <span className="tree-type">uint64</span>
                    <span className="tree-field">id</span>
                    <span className="tree-value">12345</span>
                  </div>
                  <div className="tree-leaf">
                    <span className="tree-type">uint32[]</span>
                    <span className="tree-field">tags</span>
                    <span className="tree-value">[0, 0, 1, 1]</span>
                  </div>
                  <div className="tree-leaf">
                    <span className="tree-type">GeomType</span>
                    <span className="tree-field">type</span>
                    <span className="tree-value">POLYGON</span>
                  </div>
                  <div className="tree-leaf">
                    <span className="tree-type">uint32[]</span>
                    <span className="tree-field">geometry</span>
                    <span className="tree-value">[9, 200, 200, ...]</span>
                  </div>
                </div>
              )}

              <div className="tree-leaf">
                <span className="tree-type">string[]</span>
                <span className="tree-field">keys</span>
                <span className="tree-value">["height", "name"]</span>
              </div>
              <div className="tree-leaf">
                <span className="tree-type">Value[]</span>
                <span className="tree-field">values</span>
                <span className="tree-value">[25, "Station"]</span>
              </div>
              <div className="tree-leaf">
                <span className="tree-type">uint32</span>
                <span className="tree-field">extent</span>
                <span className="tree-value">4096</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Geometry Commands Explanation Component */
function GeometryExplanation() {
  const [showExplanation, setShowExplanation] = useState(true);

  return (
    <div className="explanation-section geometry-explanation">
      <div
        className="explanation-header"
        onClick={() => setShowExplanation(!showExplanation)}
      >
        <h4>🖊️ What are Geometry Commands?</h4>
        <span className="expand-toggle">{showExplanation ? '−' : '+'}</span>
      </div>

      {showExplanation && (
        <div className="explanation-content">
          <p className="intro-text">
            Imagine you're giving directions to draw a shape. Instead of listing every coordinate,
            you give <strong>step-by-step drawing instructions</strong>:
          </p>

          <div className="directions-demo">
            <div className="direction-row">
              <span className="human-dir">"Put your pen at (10, 20)"</span>
              <span className="arrow">→</span>
              <code className="mvt-cmd">MoveTo(10, 20)</code>
            </div>
            <div className="direction-row">
              <span className="human-dir">"Draw a line to (30, 20)"</span>
              <span className="arrow">→</span>
              <code className="mvt-cmd">LineTo(30, 20)</code>
            </div>
            <div className="direction-row">
              <span className="human-dir">"Draw a line to (30, 40)"</span>
              <span className="arrow">→</span>
              <code className="mvt-cmd">LineTo(30, 40)</code>
            </div>
            <div className="direction-row">
              <span className="human-dir">"Connect back to start"</span>
              <span className="arrow">→</span>
              <code className="mvt-cmd">ClosePath</code>
            </div>
          </div>

          <div className="analogy-box">
            <span className="analogy-icon">🗺️</span>
            <p>
              It's like <strong>GPS turn-by-turn directions</strong> vs a full route map.
              "Turn right, go 500m, turn left" is more compact than listing every coordinate!
            </p>
          </div>

          <div className="commands-table">
            <h5>THE THREE COMMANDS:</h5>
            <div className="command-table-row header">
              <span>Command</span>
              <span>ID</span>
              <span>What it does</span>
            </div>
            <div className="command-table-row">
              <code>MoveTo</code>
              <span className="cmd-id">1</span>
              <span>Jump to position (don't draw)</span>
            </div>
            <div className="command-table-row">
              <code>LineTo</code>
              <span className="cmd-id">2</span>
              <span>Draw line from current pos to new pos</span>
            </div>
            <div className="command-table-row">
              <code>ClosePath</code>
              <span className="cmd-id">7</span>
              <span>Connect back to starting point</span>
            </div>
          </div>

          <div className="delta-encoding-note">
            <h5>DELTA ENCODING BONUS:</h5>
            <p>
              After MoveTo, coordinates are stored as <strong>deltas (changes)</strong> from the previous position.
              <br/>
              <code>LineTo(+20, 0)</code> means "move 20 units right" — small numbers compress better!
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/** Protobuf Explanation Component */
function ProtobufExplanation() {
  const [showExplanation, setShowExplanation] = useState(true);

  return (
    <div className="explanation-section protobuf-explanation">
      <div
        className="explanation-header"
        onClick={() => setShowExplanation(!showExplanation)}
      >
        <h4>📦 What is Protobuf?</h4>
        <span className="expand-toggle">{showExplanation ? '−' : '+'}</span>
      </div>

      {showExplanation && (
        <div className="explanation-content">
          <p className="intro-text">
            <strong>Protocol Buffers (Protobuf)</strong> is Google's way to pack data into a tiny binary format.
            Think of it like <strong>ZIP for data structures</strong>.
          </p>

          <div className="comparison-box">
            <h5>JSON vs PROTOBUF:</h5>
            <div className="comparison-columns">
              <div className="comparison-col json">
                <span className="col-header">JSON (human-readable)</span>
                <pre>{`{
  "name": "building",
  "height": 25,
  "type": "residential"
}`}</pre>
                <span className="col-size">~85 bytes</span>
              </div>
              <div className="comparison-col vs">
                <span className="vs-text">vs</span>
              </div>
              <div className="comparison-col protobuf">
                <span className="col-header">Protobuf (binary)</span>
                <pre className="binary-hex">0A 0B 62 75 69
6C 64 69 6E 67
12 03 08 19 10
2D</pre>
                <span className="col-size">~25 bytes</span>
                <span className="col-savings">70% smaller!</span>
              </div>
            </div>
          </div>

          <div className="why-binary-box">
            <h5>WHY USE BINARY FORMAT?</h5>
            <ol className="benefits-list">
              <li><strong>Size:</strong> 3-10× smaller than JSON</li>
              <li><strong>Speed:</strong> Faster to parse (no string scanning)</li>
              <li><strong>Streaming:</strong> Can read partial data (tiles load progressively)</li>
            </ol>
          </div>

          <div className="mvt-structure-overview">
            <h5>THE MVT PROTOBUF STRUCTURE:</h5>
            <div className="structure-tree-visual">
              <div className="tree-line">📦 <strong>TILE</strong></div>
              <div className="tree-line indent-1">└── 📁 <strong>layers[]</strong> (array of named data buckets)</div>
              <div className="tree-line indent-2">├── name: "building"</div>
              <div className="tree-line indent-2">├── keys[]: ["height", "type", "name"] <span className="note">(unique attribute names)</span></div>
              <div className="tree-line indent-2">├── values[]: [25, "residential", "Tower A"] <span className="note">(unique values)</span></div>
              <div className="tree-line indent-2">├── extent: 4096 <span className="note">(coordinate space size)</span></div>
              <div className="tree-line indent-2">└── 📋 <strong>features[]</strong> (the actual shapes)</div>
              <div className="tree-line indent-3">├── id: 12345</div>
              <div className="tree-line indent-3">├── tags: [0, 0, 1, 1] <span className="note">(pairs: key_idx, value_idx)</span></div>
              <div className="tree-line indent-3">├── type: POLYGON</div>
              <div className="tree-line indent-3">└── geometry: [9, 20, 40, ...] <span className="note">(encoded commands)</span></div>
            </div>
          </div>

          <p className="key-insight">
            💡 Key/value deduplication: "residential" appears once in values[], referenced by index.
            Same string used 100 times = stored once!
          </p>
        </div>
      )}
    </div>
  );
}

export function EncodingStage({ isActive }: StageProps) {
  const [step, setStep] = useState(0);
  const [activeTab, setActiveTab] = useState<'geometry' | 'protobuf' | 'zigzag'>('geometry');

  const nextStep = useCallback(() => {
    setStep((s) => Math.min(s + 1, SAMPLE_COMMANDS.length - 1));
  }, []);

  const prevStep = useCallback(() => {
    setStep((s) => Math.max(s - 1, 0));
  }, []);

  if (!isActive) return null;

  return (
    <div className="encoding-stage">
      {/* Tab Navigation */}
      <div className="encoding-tabs">
        <button
          className={`encoding-tab ${activeTab === 'geometry' ? 'active' : ''}`}
          onClick={() => setActiveTab('geometry')}
        >
          Geometry Commands
        </button>
        <button
          className={`encoding-tab ${activeTab === 'protobuf' ? 'active' : ''}`}
          onClick={() => setActiveTab('protobuf')}
        >
          Protobuf Structure
        </button>
        <button
          className={`encoding-tab ${activeTab === 'zigzag' ? 'active' : ''}`}
          onClick={() => setActiveTab('zigzag')}
        >
          Zigzag Encoding
        </button>
      </div>

      {/* Content */}
      <div className="encoding-content">
        {activeTab === 'geometry' && (
          <div className="geometry-section">
            {/* Educational Explanation */}
            <GeometryExplanation />

            {/* Interactive Visualizer */}
            <h4 className="section-subtitle">Try it yourself:</h4>
            <div className="geometry-visualizer">
              <GeometryVisualizer commands={SAMPLE_COMMANDS} currentStep={step} />
            </div>

            <div className="step-controls">
              <button className="step-btn" onClick={prevStep} disabled={step === 0}>
                ◀
              </button>
              <span className="step-label">
                Step {step + 1} / {SAMPLE_COMMANDS.length}
              </span>
              <button
                className="step-btn"
                onClick={nextStep}
                disabled={step === SAMPLE_COMMANDS.length - 1}
              >
                ▶
              </button>
            </div>

            <div className="current-command">
              <code>{SAMPLE_COMMANDS[step] ? formatCommand(SAMPLE_COMMANDS[step]) : ''}</code>
            </div>

            <div className="command-list">
              {SAMPLE_COMMANDS.map((cmd, i) => (
                <div
                  key={i}
                  className={`command-item ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
                  onClick={() => setStep(i)}
                >
                  <span className="command-index">{i + 1}</span>
                  <code>{formatCommand(cmd)}</code>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'protobuf' && (
          <div className="protobuf-section">
            {/* Educational Explanation */}
            <ProtobufExplanation />

            {/* Interactive Tree */}
            <h4 className="section-subtitle">Explore the structure:</h4>
            <ProtobufStructure />
          </div>
        )}

        {activeTab === 'zigzag' && (
          <div className="zigzag-section">
            <ZigzagDemo />
          </div>
        )}
      </div>

      <style>{`
        .encoding-stage {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 1.5rem;
          width: 100%;
          height: 100%;
          overflow-y: auto;
        }

        .encoding-tabs {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1.5rem;
        }

        .encoding-tab {
          padding: 0.5rem 1rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          color: rgba(255, 255, 255, 0.7);
          font-size: 0.875rem;
          cursor: pointer;
          transition: all 0.2s;
        }

        .encoding-tab:hover {
          background: rgba(255, 255, 255, 0.06);
        }

        .encoding-tab.active {
          background: rgba(136, 192, 255, 0.15);
          border-color: rgba(136, 192, 255, 0.4);
          color: #88c0ff;
        }

        .encoding-content {
          width: 100%;
          max-width: 500px;
        }

        .geometry-section {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .geometry-svg {
          width: 100%;
          max-width: 320px;
          background: rgba(0, 0, 0, 0.2);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          margin-bottom: 1rem;
        }

        .command-list {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
          width: 100%;
          margin-top: 1rem;
        }

        .command-item {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid transparent;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .command-item:hover {
          background: rgba(255, 255, 255, 0.05);
        }

        .command-item.active {
          background: rgba(136, 192, 255, 0.1);
          border-color: rgba(136, 192, 255, 0.3);
        }

        .command-item.done {
          opacity: 0.5;
        }

        .command-index {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 50%;
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .command-item.active .command-index {
          background: #88c0ff;
          color: #0a0a12;
        }

        .command-item code {
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
        }

        /* Protobuf Tree */
        .protobuf-section {
          padding: 1rem;
        }

        .protobuf-tree {
          font-family: 'SF Mono', Monaco, monospace;
          font-size: 0.8125rem;
        }

        .tree-node {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.375rem 0;
          cursor: pointer;
        }

        .tree-node:hover {
          background: rgba(255, 255, 255, 0.03);
        }

        .tree-children {
          margin-left: 1.25rem;
          border-left: 1px solid rgba(255, 255, 255, 0.1);
          padding-left: 0.75rem;
        }

        .tree-leaf {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.375rem 0;
        }

        .tree-toggle {
          color: rgba(255, 255, 255, 0.4);
          font-size: 0.625rem;
        }

        .tree-type {
          color: #c792ea;
        }

        .tree-field {
          color: #82aaff;
        }

        .tree-value {
          color: #c3e88d;
          margin-left: auto;
        }

        /* Zigzag Demo */
        .zigzag-section {
          display: flex;
          justify-content: center;
        }

        .zigzag-demo {
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          text-align: center;
          max-width: 300px;
        }

        .zigzag-demo h4 {
          margin: 0 0 0.75rem;
          color: #fff;
        }

        .zigzag-formula {
          margin: 0 0 1rem;
          font-size: 0.875rem;
        }

        .zigzag-formula code {
          padding: 0.25rem 0.5rem;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 4px;
          color: #88c0ff;
        }

        .zigzag-input {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }

        .zigzag-input label {
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .zigzag-input input[type="range"] {
          width: 100px;
        }

        .zigzag-value {
          font-size: 1.25rem;
          font-weight: 600;
          color: #ff8c00;
          min-width: 40px;
        }

        .zigzag-output {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }

        .zigzag-arrow {
          color: rgba(255, 255, 255, 0.4);
        }

        .zigzag-result {
          font-size: 1.5rem;
          font-weight: 600;
          color: #4ade80;
        }

        .zigzag-label {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .zigzag-explanation {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          line-height: 1.5;
          margin: 0;
        }

        /* ========================================
           Educational Explanation Components
           ======================================== */

        .explanation-section {
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 10px;
          margin-bottom: 1.5rem;
          overflow: hidden;
        }

        .explanation-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.875rem 1rem;
          cursor: pointer;
          transition: background 0.2s;
        }

        .explanation-header:hover {
          background: rgba(255, 255, 255, 0.03);
        }

        .explanation-header h4 {
          margin: 0;
          font-size: 0.9375rem;
          font-weight: 600;
          color: #fff;
        }

        .expand-toggle {
          color: rgba(255, 255, 255, 0.4);
          font-size: 1.25rem;
          font-weight: 300;
        }

        .explanation-content {
          padding: 0 1rem 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .intro-text {
          margin: 1rem 0;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.8);
          line-height: 1.6;
        }

        .section-subtitle {
          margin: 1rem 0 0.75rem;
          font-size: 0.8125rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
        }

        .key-insight {
          padding: 0.75rem;
          background: rgba(136, 192, 255, 0.08);
          border-radius: 6px;
          font-size: 0.8125rem;
          color: #88c0ff;
          margin-top: 1rem;
        }

        /* Geometry Commands Explanation */
        .directions-demo {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          padding: 1rem;
          margin: 1rem 0;
        }

        .direction-row {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.5rem 0;
          font-size: 0.8125rem;
        }

        .human-dir {
          flex: 1;
          color: rgba(255, 255, 255, 0.7);
        }

        .direction-row .arrow {
          color: rgba(255, 255, 255, 0.3);
        }

        .mvt-cmd {
          background: rgba(136, 192, 255, 0.15);
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          color: #88c0ff;
          font-size: 0.75rem;
        }

        .analogy-box {
          display: flex;
          gap: 0.75rem;
          padding: 1rem;
          background: rgba(255, 140, 0, 0.08);
          border: 1px solid rgba(255, 140, 0, 0.2);
          border-radius: 8px;
          margin: 1rem 0;
        }

        .analogy-icon {
          font-size: 1.5rem;
        }

        .analogy-box p {
          margin: 0;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
          line-height: 1.5;
        }

        .commands-table {
          margin: 1rem 0;
        }

        .commands-table h5,
        .delta-encoding-note h5,
        .why-binary-box h5,
        .comparison-box h5,
        .mvt-structure-overview h5,
        .problem-box h5,
        .solution-box h5,
        .formula-box h5,
        .savings-table h5 {
          margin: 0 0 0.5rem;
          font-size: 0.6875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: rgba(255, 255, 255, 0.5);
        }

        .command-table-row {
          display: grid;
          grid-template-columns: 100px 40px 1fr;
          gap: 0.5rem;
          padding: 0.5rem 0.75rem;
          font-size: 0.8125rem;
          align-items: center;
        }

        .command-table-row.header {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px 6px 0 0;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
        }

        .command-table-row code {
          color: #88c0ff;
        }

        .cmd-id {
          color: #c792ea;
          font-family: 'SF Mono', Monaco, monospace;
        }

        .delta-encoding-note {
          padding: 1rem;
          background: rgba(74, 222, 128, 0.08);
          border: 1px solid rgba(74, 222, 128, 0.2);
          border-radius: 8px;
          margin-top: 1rem;
        }

        .delta-encoding-note p {
          margin: 0;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
          line-height: 1.5;
        }

        .delta-encoding-note code {
          background: rgba(0, 0, 0, 0.2);
          padding: 0.125rem 0.375rem;
          border-radius: 3px;
          color: #4ade80;
        }

        /* Protobuf Explanation */
        .comparison-box {
          margin: 1rem 0;
        }

        .comparison-columns {
          display: flex;
          gap: 1rem;
          align-items: stretch;
        }

        .comparison-col {
          flex: 1;
          padding: 1rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          display: flex;
          flex-direction: column;
        }

        .comparison-col.vs {
          flex: 0;
          justify-content: center;
          align-items: center;
          background: transparent;
          padding: 0;
        }

        .vs-text {
          color: rgba(255, 255, 255, 0.3);
          font-weight: 600;
        }

        .col-header {
          font-size: 0.75rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
          margin-bottom: 0.5rem;
        }

        .comparison-col pre {
          flex: 1;
          margin: 0;
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.8);
          line-height: 1.4;
          overflow-x: auto;
        }

        .comparison-col.protobuf pre {
          color: #c792ea;
          letter-spacing: 0.1em;
        }

        .col-size {
          margin-top: 0.5rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .col-savings {
          font-size: 0.75rem;
          color: #4ade80;
          font-weight: 600;
        }

        .why-binary-box {
          padding: 1rem;
          background: rgba(136, 192, 255, 0.05);
          border-radius: 8px;
          margin: 1rem 0;
        }

        .benefits-list {
          margin: 0;
          padding-left: 1.25rem;
        }

        .benefits-list li {
          margin: 0.375rem 0;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
        }

        .mvt-structure-overview {
          margin: 1rem 0;
        }

        .structure-tree-visual {
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
          padding: 1rem;
          font-family: 'SF Mono', Monaco, monospace;
          font-size: 0.75rem;
        }

        .tree-line {
          padding: 0.25rem 0;
          color: rgba(255, 255, 255, 0.8);
        }

        .tree-line.indent-1 { padding-left: 1rem; }
        .tree-line.indent-2 { padding-left: 2rem; }
        .tree-line.indent-3 { padding-left: 3rem; }

        .tree-line .note {
          color: rgba(255, 255, 255, 0.4);
          font-size: 0.6875rem;
        }

        /* Zigzag Enhanced Demo */
        .zigzag-demo-enhanced {
          width: 100%;
        }

        .problem-box {
          padding: 1rem;
          background: rgba(239, 68, 68, 0.08);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: 8px;
          margin: 1rem 0;
        }

        .problem-box p {
          margin: 0.5rem 0;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
        }

        .binary-bad {
          background: rgba(239, 68, 68, 0.15);
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          color: #fca5a5;
          font-size: 0.6875rem;
          letter-spacing: 0.05em;
        }

        .binary-good {
          background: rgba(74, 222, 128, 0.15);
          color: #4ade80;
        }

        .problem-note {
          display: block;
          margin-top: 0.25rem;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
        }

        .solution-box {
          padding: 1rem;
          background: rgba(74, 222, 128, 0.08);
          border: 1px solid rgba(74, 222, 128, 0.2);
          border-radius: 8px;
          margin: 1rem 0;
        }

        .solution-box p {
          margin: 0 0 0.75rem;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
        }

        .mapping-table {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .mapping-row {
          display: grid;
          grid-template-columns: 50px 30px 50px;
          gap: 0.5rem;
          padding: 0.25rem 0.5rem;
          font-size: 0.8125rem;
          color: rgba(255, 255, 255, 0.8);
          font-family: 'SF Mono', Monaco, monospace;
        }

        .mapping-row.header {
          font-weight: 600;
          color: rgba(255, 255, 255, 0.5);
          font-family: inherit;
        }

        .mapping-row.negative {
          color: #fca5a5;
        }

        .formula-box {
          padding: 1rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          margin: 1rem 0;
        }

        .formula {
          display: block;
          margin: 0.25rem 0;
          font-size: 0.75rem;
          color: #88c0ff;
        }

        .savings-table {
          margin: 1rem 0;
        }

        .savings-row {
          display: grid;
          grid-template-columns: 50px 100px 80px 60px;
          gap: 0.5rem;
          padding: 0.5rem 0.75rem;
          font-size: 0.75rem;
          align-items: center;
        }

        .savings-row.header {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px 6px 0 0;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.6);
        }

        .savings {
          color: #4ade80;
          font-weight: 600;
        }

        /* Interactive Demo */
        .interactive-demo {
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 10px;
        }

        .interactive-demo h4 {
          margin: 0 0 1rem;
          font-size: 0.875rem;
          font-weight: 600;
          color: rgba(255, 255, 255, 0.8);
        }

        .zigzag-conversion {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.5rem;
          margin-top: 1rem;
        }

        .conversion-step {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 8px;
          width: 100%;
          max-width: 300px;
        }

        .step-label {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.5);
          min-width: 80px;
        }

        .step-value {
          font-size: 1.25rem;
          font-weight: 700;
          min-width: 50px;
          text-align: center;
        }

        .step-value.signed {
          color: #ff8c00;
        }

        .step-value.unsigned {
          color: #4ade80;
        }

        .step-binary {
          font-family: 'SF Mono', Monaco, monospace;
          font-size: 0.6875rem;
          color: rgba(255, 255, 255, 0.5);
          letter-spacing: 0.05em;
        }

        .step-binary.good {
          color: #4ade80;
        }

        .conversion-arrow {
          color: rgba(255, 255, 255, 0.3);
          font-size: 0.875rem;
        }

        @media (max-width: 600px) {
          .comparison-columns {
            flex-direction: column;
          }

          .comparison-col.vs {
            padding: 0.5rem 0;
          }

          .vs-text {
            transform: rotate(90deg);
          }
        }
      `}</style>
    </div>
  );
}
