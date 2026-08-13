import { useMemo, useRef, useState } from 'react'

/* Shared geometry. Marks follow the dataviz specs: 2px lines, >=8px markers,
   4px rounded data-ends anchored to the baseline, 2px gaps between fills,
   recessive grid, crosshair + tooltip on every plotted form. */

const PAD = { top: 16, right: 16, bottom: 28, left: 44 }

function useScales(points, width, height, { zeroBased = false } = {}) {
  return useMemo(() => {
    const values = points.map((p) => p.value)
    const rawMin = Math.min(...values)
    const rawMax = Math.max(...values)
    const min = zeroBased ? 0 : rawMin - (rawMax - rawMin || 1) * 0.12
    const max = rawMax + (rawMax - rawMin || 1) * 0.12

    const innerW = width - PAD.left - PAD.right
    const innerH = height - PAD.top - PAD.bottom

    const x = (i) => PAD.left + (points.length <= 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
    const y = (v) => PAD.top + innerH - ((v - min) / (max - min || 1)) * innerH

    return { x, y, min, max, innerW, innerH }
  }, [points, width, height, zeroBased])
}

function niceTicks(min, max, count = 4) {
  const span = max - min || 1
  const step = Math.pow(10, Math.floor(Math.log10(span / count)))
  const err = (span / count) / step
  const mult = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1
  const nice = step * mult
  const out = []
  for (let v = Math.ceil(min / nice) * nice; v <= max; v += nice) out.push(Number(v.toFixed(6)))
  return out
}

function fmtDate(iso) {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function Tooltip({ hover, width, children }) {
  if (!hover) return null
  const left = Math.min(Math.max(hover.px, 70), width - 70)
  return (
    <div className="tooltip" style={{ left, top: hover.py }}>
      {children}
    </div>
  )
}

/* ---------------------------------------------------------------- */

export function LineChart({ points, color = 'var(--series-1)', unit = '', height = 220, zeroBased = false, format }) {
  const width = 640
  const ref = useRef(null)
  const [hover, setHover] = useState(null)
  const { x, y, min, max } = useScales(points, width, height, { zeroBased })

  if (!points.length) return <p className="empty">No data recorded yet.</p>

  const fmt = format || ((v) => `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })}${unit}`)
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.value)}`).join(' ')
  const ticks = niceTicks(min, max)

  function onMove(e) {
    const rect = ref.current.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * width
    let best = 0
    points.forEach((_, i) => { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i })
    setHover({ i: best, px: (x(best) / width) * rect.width, py: (y(points[best].value) / height) * rect.height })
  }

  return (
    <div className="chart-wrap" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img"
           onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
            <text className="tick tabular" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">{fmt(t)}</text>
          </g>
        ))}

        <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {hover && (
          <>
            <line x1={x(hover.i)} x2={x(hover.i)} y1={PAD.top} y2={height - PAD.bottom}
                  stroke="var(--axis)" strokeWidth="1" />
            <circle cx={x(hover.i)} cy={y(points[hover.i].value)} r="5"
                    fill={color} stroke="var(--bg-primary)" strokeWidth="2" />
          </>
        )}

        <text className="tick" x={PAD.left} y={height - 8}>{fmtDate(points[0].date)}</text>
        <text className="tick" x={width - PAD.right} y={height - 8} textAnchor="end">
          {fmtDate(points[points.length - 1].date)}
        </text>
      </svg>

      <Tooltip hover={hover} width={ref.current?.clientWidth || width}>
        {hover && (
          <>
            <div className="t-date">{fmtDate(points[hover.i].date)}</div>
            <div className="t-row">
              <span className="swatch" style={{ background: color }} />
              <span className="t-val">{fmt(points[hover.i].value)}</span>
            </div>
          </>
        )}
      </Tooltip>
    </div>
  )
}

/* ---------------------------------------------------------------- */

export function BarChart({ points, color = 'var(--series-1)', unit = '', height = 220, format }) {
  const width = 640
  const ref = useRef(null)
  const [hover, setHover] = useState(null)
  const { y, min, max, innerW } = useScales(points, width, height, { zeroBased: true })

  if (!points.length) return <p className="empty">No data recorded yet.</p>

  const fmt = format || ((v) => `${Math.round(v).toLocaleString()}${unit}`)
  const slot = innerW / points.length
  const barW = Math.max(2, slot - 2) // 2px surface gap between adjacent bars
  const ticks = niceTicks(min, max)
  const base = y(0)

  return (
    <div className="chart-wrap" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth="1" />
            <text className="tick tabular" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">{fmt(t)}</text>
          </g>
        ))}

        {points.map((p, i) => {
          const bx = PAD.left + i * slot + (slot - barW) / 2
          const top = y(p.value)
          const h = Math.max(0, base - top)
          return (
            <g key={p.date}>
              <rect x={bx} y={top} width={barW} height={h} rx={Math.min(4, barW / 2)} fill={color}
                    opacity={hover && hover.i !== i ? 0.45 : 1} />
              <rect x={PAD.left + i * slot} y={PAD.top} width={slot} height={height - PAD.top - PAD.bottom}
                    fill="transparent"
                    onMouseEnter={() => setHover({
                      i,
                      px: ((bx + barW / 2) / width) * (ref.current?.clientWidth || width),
                      py: (top / height) * (ref.current?.clientHeight || height),
                    })} />
            </g>
          )
        })}

        <line x1={PAD.left} x2={width - PAD.right} y1={base} y2={base} stroke="var(--axis)" strokeWidth="1" />
        <text className="tick" x={PAD.left} y={height - 8}>{fmtDate(points[0].date)}</text>
        <text className="tick" x={width - PAD.right} y={height - 8} textAnchor="end">
          {fmtDate(points[points.length - 1].date)}
        </text>
      </svg>

      <Tooltip hover={hover} width={ref.current?.clientWidth || width}>
        {hover && (
          <>
            <div className="t-date">{fmtDate(points[hover.i].date)}</div>
            <div className="t-row">
              <span className="swatch" style={{ background: color }} />
              <span className="t-val">{fmt(points[hover.i].value)}</span>
            </div>
          </>
        )}
      </Tooltip>
    </div>
  )
}

/* ---------------------------------------------------------------- */

const STAGES = [
  { key: 'DEEP', label: 'Deep', color: 'var(--stage-deep)' },
  { key: 'REM', label: 'REM', color: 'var(--stage-rem)' },
  { key: 'LIGHT', label: 'Light', color: 'var(--stage-light)' },
  { key: 'AWAKE', label: 'Awake', color: 'var(--stage-awake)' },
]

export function SleepStagesChart({ points, height = 220 }) {
  const width = 640
  const ref = useRef(null)
  const [hover, setHover] = useState(null)

  if (!points.length) return <p className="empty">No sleep recorded yet.</p>

  const totals = points.map((p) =>
    STAGES.reduce((sum, s) => sum + ((p.extra?.stages?.[s.key]) || 0), 0))
  const max = Math.max(...totals, 1)

  const innerW = width - PAD.left - PAD.right
  const innerH = height - PAD.top - PAD.bottom
  const slot = innerW / points.length
  const barW = Math.max(2, slot - 2)
  const yOf = (v) => PAD.top + innerH - (v / max) * innerH

  const hourTicks = []
  for (let h = 0; h <= max / 60; h += 2) hourTicks.push(h * 60)

  return (
    <div className="chart-wrap" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" onMouseLeave={() => setHover(null)}>
        {hourTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={yOf(t)} y2={yOf(t)} stroke="var(--grid)" strokeWidth="1" />
            <text className="tick tabular" x={PAD.left - 8} y={yOf(t) + 4} textAnchor="end">{t / 60}h</text>
          </g>
        ))}

        {points.map((p, i) => {
          const bx = PAD.left + i * slot + (slot - barW) / 2
          let cursor = 0
          return (
            <g key={p.date} opacity={hover && hover.i !== i ? 0.45 : 1}>
              {STAGES.map((s) => {
                const v = (p.extra?.stages?.[s.key]) || 0
                if (!v) return null
                const top = yOf(cursor + v)
                const h = Math.max(0, yOf(cursor) - yOf(cursor + v) - 2) // 2px gap between segments
                cursor += v
                return <rect key={s.key} x={bx} y={top} width={barW} height={h} rx="2" fill={s.color} />
              })}
              <rect x={PAD.left + i * slot} y={PAD.top} width={slot} height={innerH} fill="transparent"
                    onMouseEnter={() => setHover({
                      i,
                      px: ((bx + barW / 2) / width) * (ref.current?.clientWidth || width),
                      py: (yOf(totals[i]) / height) * (ref.current?.clientHeight || height),
                    })} />
            </g>
          )
        })}

        <line x1={PAD.left} x2={width - PAD.right} y1={yOf(0)} y2={yOf(0)} stroke="var(--axis)" strokeWidth="1" />
        <text className="tick" x={PAD.left} y={height - 8}>{fmtDate(points[0].date)}</text>
        <text className="tick" x={width - PAD.right} y={height - 8} textAnchor="end">
          {fmtDate(points[points.length - 1].date)}
        </text>
      </svg>

      <Tooltip hover={hover} width={ref.current?.clientWidth || width}>
        {hover && (
          <>
            <div className="t-date">{fmtDate(points[hover.i].date)}</div>
            {STAGES.map((s) => {
              const v = (points[hover.i].extra?.stages?.[s.key]) || 0
              if (!v) return null
              return (
                <div className="t-row" key={s.key}>
                  <span className="swatch" style={{ background: s.color }} />
                  <span>{s.label}</span>
                  <span className="t-val">{Math.round(v)}m</span>
                </div>
              )
            })}
          </>
        )}
      </Tooltip>

      {/* Legend is always present for >= 2 series, so identity is never color alone */}
      <div className="legend">
        {STAGES.map((s) => (
          <span key={s.key}><span className="swatch" style={{ background: s.color }} />{s.label}</span>
        ))}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- */

export function ProgressRing({ value, target, unit = 'min', size = 148 }) {
  const stroke = 14
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = target > 0 ? Math.min(value / target, 1) : 0
  const over = target > 0 && value > target

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
         aria-label={`${Math.round(value)} of ${target} ${unit}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--grid)" strokeWidth={stroke} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={over ? 'var(--good)' : 'var(--series-1)'}
        strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 0.6s var(--ease)' }}
      />
      <text x="50%" y="50%" textAnchor="middle" dy="0.36em"
            style={{ font: '600 26px/1 inherit', fill: 'var(--text-primary)' }}>
        {Math.round(pct * 100)}%
      </text>
    </svg>
  )
}
