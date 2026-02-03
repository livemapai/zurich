import { useCallback } from 'react';
import { formatTime, TIME_PRESETS } from '@/utils';

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
export function TimeSlider({ value, onChange, visible = true }: TimeSliderProps) {
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
    <div className="time-slider">
      <div className="time-slider-header">
        <span className="time-slider-label">Time of Day</span>
        <span className="time-slider-value">{formatTime(value)}</span>
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
