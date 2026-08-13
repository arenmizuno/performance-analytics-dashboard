import { useRef, useState } from 'react'

/* One cell per day, seven rows tall, weeks running left to right.
   Colour is a sequential green ramp keyed to minutes trained - magnitude,
   so one hue dark to bright rather than categorical colours. */

const STEPS = [
  { min: 1, cls: 'var(--cell-1)', label: 'under 30 min' },
  { min: 30, cls: 'var(--cell-2)', label: '30-60 min' },
  { min: 60, cls: 'var(--cell-3)', label: '60-90 min' },
  { min: 90, cls: 'var(--cell-4)', label: '90 min or more' },
]

function colorFor(minutes) {
  if (!minutes) return 'var(--cell-0)'
  let out = STEPS[0].cls
  for (const s of STEPS) if (minutes >= s.min) out = s.cls
  return out
}

function fmtDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

export default function Consistency({ data }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(null)

  if (!data) return <p className="empty">Loading...</p>

  return (
    <div className="chart-wrap" ref={ref}>
      <div className="strip-stats">
        <div className="strip-stat">
          <span className="n">{data.rate}%</span>
          <span className="k">of days active</span>
        </div>
        <div className="strip-stat">
          <span className="n">{data.active_days}</span>
          <span className="k">active days in {data.days}</span>
        </div>
        <div className="strip-stat">
          <span className="n">{data.streak}</span>
          <span className="k">day streak</span>
        </div>
      </div>

      <div className="strip">
        {data.points.map((p) => (
          <div
            key={p.date}
            className="cell"
            style={{ background: colorFor(p.minutes) }}
            onMouseEnter={(e) => {
              const box = ref.current.getBoundingClientRect()
              const cell = e.currentTarget.getBoundingClientRect()
              setHover({ p, px: cell.left - box.left + cell.width / 2, py: cell.top - box.top })
            }}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </div>

      {hover && (
        <div className="tooltip" style={{ left: hover.px, top: hover.py }}>
          <div className="t-date">{fmtDate(hover.p.date)}</div>
          {hover.p.count ? (
            <>
              <div className="t-row">
                <span>{hover.p.count} {hover.p.count === 1 ? 'activity' : 'activities'}</span>
                <span className="t-val">{Math.round(hover.p.minutes)} min</span>
              </div>
              <div className="t-date">{hover.p.types.join(', ')}</div>
            </>
          ) : <div className="t-row"><span>Rest day</span></div>}
        </div>
      )}

      <div className="legend">
        <span><span className="swatch" style={{ background: 'var(--cell-0)' }} />Rest</span>
        {STEPS.map((s) => (
          <span key={s.min}><span className="swatch" style={{ background: s.cls }} />{s.label}</span>
        ))}
      </div>
    </div>
  )
}
