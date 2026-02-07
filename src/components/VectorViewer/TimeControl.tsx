/**
 * TimeControl Component
 *
 * Slider control for adjusting time of day, which affects
 * shadow direction and intensity in the VectorViewer.
 */

import { useCallback, useMemo } from 'react';
import type { SunPosition } from '@/hooks/useSunPosition';
import { formatTime } from '@/utils/sunPosition';

export interface TimeControlProps {
  /** Current time in minutes from midnight */
  timeOfDay: number;
  /** Callback when time changes */
  onTimeChange: (time: number) => void;
  /** Sun position data for display */
  sunPosition?: SunPosition;
  /** Whether the control is disabled */
  disabled?: boolean;
}

// Time presets for quick selection
const TIME_PRESETS = [
  { label: 'Dawn', time: 6 * 60, icon: '🌅' },
  { label: 'Morning', time: 9 * 60, icon: '☀️' },
  { label: 'Noon', time: 12 * 60, icon: '🔆' },
  { label: 'Afternoon', time: 15 * 60, icon: '⛅' },
  { label: 'Sunset', time: 19 * 60, icon: '🌇' },
  { label: 'Dusk', time: 21 * 60, icon: '🌆' },
] as const;

/**
 * Format sun altitude for display
 */
function formatAltitude(degrees: number): string {
  return `${Math.round(degrees)}°`;
}

/**
 * Format sun azimuth as compass direction
 */
function formatAzimuth(degrees: number): string {
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(degrees / 45) % 8;
  return `${directions[index]} (${Math.round(degrees)}°)`;
}

/**
 * TimeControl - Slider for adjusting shadow time of day
 */
export function TimeControl({
  timeOfDay,
  onTimeChange,
  sunPosition,
  disabled = false,
}: TimeControlProps) {
  // Handle slider change
  const handleSliderChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onTimeChange(Number(event.target.value));
    },
    [onTimeChange]
  );

  // Handle preset button click
  const handlePresetClick = useCallback(
    (time: number) => {
      onTimeChange(time);
    },
    [onTimeChange]
  );

  // Calculate slider background gradient for visual feedback
  const sliderBackground = useMemo(() => {
    // Create a gradient that shows day/night cycle
    return `linear-gradient(to right,
      #1a1a2e 0%,   /* night */
      #ff6b35 15%,  /* dawn */
      #ffd93d 25%,  /* morning */
      #6bcb77 40%,  /* midday */
      #4d96ff 60%,  /* afternoon */
      #ff6b35 85%,  /* sunset */
      #1a1a2e 100%  /* night */
    )`;
  }, []);

  return (
    <div className="time-control">
      <div className="time-control-header">
        <h4>🌞 Time of Day</h4>
        <span className="time-display">{formatTime(timeOfDay)}</span>
      </div>

      {/* Time slider */}
      <div className="time-slider-container">
        <input
          type="range"
          className="time-slider"
          min={5 * 60}   /* 5:00 AM */
          max={22 * 60}  /* 10:00 PM */
          value={timeOfDay}
          onChange={handleSliderChange}
          disabled={disabled}
          style={{
            background: sliderBackground,
          }}
        />
        <div className="time-labels">
          <span>5:00</span>
          <span>12:00</span>
          <span>22:00</span>
        </div>
      </div>

      {/* Time presets */}
      <div className="time-presets">
        {TIME_PRESETS.map((preset) => (
          <button
            key={preset.label}
            className={`time-preset ${Math.abs(timeOfDay - preset.time) < 30 ? 'active' : ''}`}
            onClick={() => handlePresetClick(preset.time)}
            disabled={disabled}
            title={`${preset.label} (${formatTime(preset.time)})`}
          >
            <span className="preset-icon">{preset.icon}</span>
            <span className="preset-label">{preset.label}</span>
          </button>
        ))}
      </div>

      {/* Sun position info */}
      {sunPosition && (
        <div className="sun-info">
          <div className="sun-stat">
            <span className="stat-label">Altitude:</span>
            <span className="stat-value">{formatAltitude(sunPosition.altitude)}</span>
          </div>
          <div className="sun-stat">
            <span className="stat-label">Direction:</span>
            <span className="stat-value">{formatAzimuth(sunPosition.azimuth)}</span>
          </div>
          <div className="sun-stat">
            <span className="stat-label">Shadow:</span>
            <span className="stat-value">
              {sunPosition.isDaytime ? formatAzimuth(sunPosition.shadowAzimuth) : 'N/A'}
            </span>
          </div>
        </div>
      )}

      <style>{`
        .time-control {
          padding: 12px;
          background: rgba(255, 255, 255, 0.95);
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .time-control-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .time-control-header h4 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
          color: #333;
        }

        .time-display {
          font-family: 'SF Mono', 'Monaco', monospace;
          font-size: 18px;
          font-weight: 700;
          color: #2c3e50;
          background: #f0f4f8;
          padding: 4px 12px;
          border-radius: 4px;
        }

        .time-slider-container {
          margin-bottom: 12px;
        }

        .time-slider {
          width: 100%;
          height: 8px;
          border-radius: 4px;
          outline: none;
          -webkit-appearance: none;
          appearance: none;
          cursor: pointer;
        }

        .time-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #fff;
          border: 3px solid #2c3e50;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          cursor: grab;
        }

        .time-slider::-webkit-slider-thumb:active {
          cursor: grabbing;
        }

        .time-slider:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .time-labels {
          display: flex;
          justify-content: space-between;
          font-size: 10px;
          color: #666;
          margin-top: 4px;
        }

        .time-presets {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
          margin-bottom: 12px;
        }

        .time-preset {
          flex: 1;
          min-width: 60px;
          padding: 6px 4px;
          border: 1px solid #ddd;
          border-radius: 4px;
          background: #fff;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
        }

        .time-preset:hover:not(:disabled) {
          border-color: #4a90d9;
          background: #f0f7ff;
        }

        .time-preset.active {
          border-color: #4a90d9;
          background: #e3f2fd;
        }

        .time-preset:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .preset-icon {
          font-size: 16px;
        }

        .preset-label {
          font-size: 9px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .sun-info {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          padding-top: 12px;
          border-top: 1px solid #eee;
        }

        .sun-stat {
          text-align: center;
        }

        .stat-label {
          display: block;
          font-size: 10px;
          color: #888;
          margin-bottom: 2px;
        }

        .stat-value {
          font-size: 12px;
          font-weight: 600;
          color: #2c3e50;
        }
      `}</style>
    </div>
  );
}
