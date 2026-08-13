/* Time-range control. "All" reaches back to the first day on record, so the
   charts are not capped at a fixed window. */

export const RANGES = [
  { id: '7d', label: '7D', days: 7 },
  { id: '30d', label: '30D', days: 30 },
  { id: '90d', label: '90D', days: 90 },
  { id: '1y', label: '1Y', days: 365 },
  { id: 'all', label: 'All', days: null },
]

export function startDateFor(range, earliest) {
  if (range.days == null) return earliest || undefined
  return new Date(Date.now() - range.days * 864e5).toISOString().slice(0, 10)
}

export default function RangeBar({ value, onChange, label = 'Time range' }) {
  return (
    <div className="range-bar" role="group" aria-label={label}>
      {RANGES.map((r) => (
        <button
          key={r.id}
          aria-pressed={value === r.id}
          onClick={() => onChange(r.id)}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
