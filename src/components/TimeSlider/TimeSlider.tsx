import { useCallback } from 'react';
import { formatTime, TIME_PRESETS } from '@/utils';

/**
 * Speed options for time auto-play
 * multiplier: how many simulation seconds pass per real second
 */
const SPEED_OPTIONS = [
  { label: '1x', multiplier: 1 },      // Real-time: 1 sec = 1 sec
  { label: '60x', multiplier: 60 },    // 1 real sec = 1 sim minute
  { label: '600x', multiplier: 600 },  // 1 real sec = 10 sim minutes
  { label: '3600x', multiplier: 3600 }, // 1 real sec = 1 sim hour
] as const;

/**
 * Props for TimeSlider component
 */
export interface TimeSliderProps {
  /** Current time in minutes from midnight (300-1320) */
  value: number;
  /** Callback when time changes */
  onChange: (time: number) => void;
  /** Whether the slider is visible */
  visible?: boolean;
  /** Whether time is auto-playing */
  isPlaying?: boolean;
  /** Callback for play/pause toggle */
  onPlayPause?: () => void;
  /** Current speed multiplier (1, 60, 600, 3600) */
  speed?: number;
  /** Callback for speed change */
  onSpeedChange?: (speed: number) => void;
}

/**
 * Time presets with display labels
 */
const PRESETS = [
  { label: 'Dawn', time: TIME_PRESETS.dawn },
  { label: 'Morning', time: TIME_PRESETS.morning },
  { label: 'Noon', time: TIME_PRESETS.noon },
  { label: 'Golden', time: TIME_PRESETS.golden },
] as const;

/**
 * TimeSlider - Controls time of day for scene lighting
 *
 * Renders a slider and preset buttons at the bottom of the viewport.
 * Time range: 5:00 - 22:00 with 15-minute increments.
 *
 * @example
 * ```tsx
 * const [timeOfDay, setTimeOfDay] = useState(12 * 60);
 *
 * <TimeSlider
 *   value={timeOfDay}
 *   onChange={setTimeOfDay}
 *   visible={showTimeSlider}
 * />
 * ```
 */
export function TimeSlider({
  value,
  onChange,
  visible = true,
  isPlaying = false,
  onPlayPause,
  speed = 600,
  onSpeedChange,
}: TimeSliderProps) {
  // Handle slider change (converts string value to number)
  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange(parseInt(e.target.value, 10));
    },
    [onChange]
  );

  // Handle preset button click
  const handlePresetClick = useCallback(
    (time: number) => {
      onChange(time);
    },
    [onChange]
  );

  if (!visible) return null;

  return (
    <div
      className="time-slider"
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="time-slider-header">
        <span className="time-slider-label">Time of Day</span>
        <span className="time-slider-value">{formatTime(value)}</span>
      </div>

      <div className="time-slider-controls">
        <button
          className="time-slider-play"
          onClick={onPlayPause}
          type="button"
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <select
          className="time-slider-speed"
          value={speed}
          onChange={(e) => onSpeedChange?.(Number(e.target.value))}
          aria-label="Playback speed"
        >
          {SPEED_OPTIONS.map((opt) => (
            <option key={opt.multiplier} value={opt.multiplier}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="time-slider-track-container">
        <span className="time-slider-bound">5:00</span>
        <input
          type="range"
          className="time-slider-input"
          min={5 * 60}
          max={22 * 60}
          step={15}
          value={value}
          onChange={handleSliderChange}
          aria-label="Time of day"
        />
        <span className="time-slider-bound">22:00</span>
      </div>

      <div className="time-slider-presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            className={`time-slider-preset ${value === preset.time ? 'active' : ''}`}
            onClick={() => handlePresetClick(preset.time)}
            type="button"
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="time-slider-hint">
        Press <kbd>T</kbd> to toggle
      </div>
    </div>
  );
}
