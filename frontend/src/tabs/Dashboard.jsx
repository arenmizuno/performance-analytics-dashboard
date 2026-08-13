import { useEffect, useState } from 'react'
import { api } from '../api'
import { BarChart, LineChart, ProgressRing, SleepStagesChart } from '../components/charts'
import Consistency from '../components/Consistency'
import PersonalBests from '../components/PersonalBests'
import RangeBar, { RANGES, startDateFor } from '../components/RangeBar'

const TILES = [
  { key: 'weight_lb', label: 'Weight', unit: 'lb', form: 'line', digits: 1, betterWhen: 'down' },
  { key: 'steps', label: 'Steps', unit: '', form: 'bar', digits: 0, betterWhen: 'up' },
  { key: 'readiness', label: 'Readiness', unit: '', form: 'line', digits: 0, betterWhen: 'up', zeroBased: true },
  { key: 'sleep_minutes', label: 'Sleep', unit: '', form: 'sleep', digits: 0, betterWhen: 'up' },
]

function formatValue(key, value, digits) {
  if (value == null) return '--'
  if (key === 'sleep_minutes') {
    const h = Math.floor(value / 60)
    const m = Math.round(value % 60)
    return `${h}h ${m}m`
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function Delta({ change, betterWhen, unit }) {
  if (change == null || change === 0) return <span className="delta flat">no change</span>
  const good = betterWhen === 'up' ? change > 0 : change < 0
  return (
    <span className={`delta ${good ? 'up' : 'down'}`}>
      {change > 0 ? '↑' : '↓'} {Math.abs(change).toLocaleString(undefined, { maximumFractionDigits: 1 })}{unit}
    </span>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [azm, setAzm] = useState(null)
  const [bests, setBests] = useState(null)
  const [consistency, setConsistency] = useState(null)
  const [range, setRange] = useState(null)
  const [open, setOpen] = useState(null)
  const [chartRange, setChartRange] = useState('90d')
  const [series, setSeries] = useState({})
  const [error, setError] = useState(null)
  const [editingGoal, setEditingGoal] = useState(false)
  const [goalDraft, setGoalDraft] = useState('')

  useEffect(() => {
    Promise.all([
      api.metricsSummary(),
      api.activeZoneMinutes(7),
      api.personalBests(),
      api.consistency(112),
      api.dataRange(),
    ])
      .then(([s, a, p, c, r]) => {
        setSummary(s.metrics); setAzm(a); setBests(p); setConsistency(c); setRange(r)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!open) return
    const key = `${open}:${chartRange}`
    if (series[key]) return

    const r = RANGES.find((x) => x.id === chartRange)
    api.metric(open, { start_date: startDateFor(r, range?.start_date) })
      .then((res) => setSeries((prev) => ({ ...prev, [key]: res })))
      .catch((e) => setError(e.message))
  }, [open, chartRange, series, range])

  if (error) return <div className="notice">Could not reach the API: {error}. Is the backend running on port 8000?</div>
  if (!summary) return <div className="empty">Loading...</div>

  const openTile = TILES.find((t) => t.key === open)
  const loaded = open ? series[`${open}:${chartRange}`] : null
  const points = loaded?.points
  const stats = loaded?.stats

  return (
    <>
      <div className="card section">
        <h2>Active zone minutes &mdash; this week</h2>
        <div className="ring-row">
          <ProgressRing value={azm?.total || 0} target={azm?.goal || 300} unit="AZM" />
          <div>
            <div className="ring-figure">
              {Math.round(azm?.total || 0).toLocaleString()}
              <span style={{ fontSize: 17, color: 'var(--text-secondary)', fontWeight: 400 }}>
                {' '}/ {azm?.goal} AZM
              </span>
            </div>
            <p className="ring-caption">
              Minutes in the moderate heart-rate zone count once; vigorous and peak count double.
              Measured by your watch, so it credits intensity rather than time on feet.
            </p>

            {editingGoal ? (
              <div className="goal-edit">
                <label className="visually-hidden" htmlFor="goal">Weekly AZM goal</label>
                <input id="goal" type="number" min="1" max="5000" value={goalDraft}
                       onChange={(e) => setGoalDraft(e.target.value)} autoFocus />
                <button className="btn small" onClick={async () => {
                  const n = parseInt(goalDraft, 10)
                  if (!Number.isFinite(n) || n < 1) return
                  await api.updateSettings({ weekly_azm_goal: n })
                  const fresh = await api.activeZoneMinutes(7)
                  setAzm(fresh)
                  setEditingGoal(false)
                }}>Save</button>
                <button className="btn small secondary" onClick={() => setEditingGoal(false)}>Cancel</button>
              </div>
            ) : (
              <button className="btn small secondary" onClick={() => {
                setGoalDraft(String(azm?.goal ?? 300)); setEditingGoal(true)
              }}>Change goal</button>
            )}
          </div>
        </div>
      </div>

      <div className="grid-tiles">
        {TILES.map((tile) => {
          const m = summary[tile.key]
          return (
            <button
              key={tile.key}
              className="card tile"
              disabled={!m}
              aria-expanded={open === tile.key}
              onClick={() => setOpen(open === tile.key ? null : tile.key)}
            >
              <span className="label">{tile.label}</span>
              <span className="value">
                {formatValue(tile.key, m?.value, tile.digits)}
                {tile.unit && m && <span className="unit">{tile.unit}</span>}
              </span>
              <span className="meta">
                {m ? (
                  <>
                    <Delta change={m.change} betterWhen={tile.betterWhen}
                           unit={tile.key === 'sleep_minutes' ? 'm' : tile.unit} />
                    <span>&middot; {m.date}</span>
                  </>
                ) : 'Not connected'}
              </span>
            </button>
          )
        })}
      </div>

      {openTile && (
        <div className="card section">
          <h2>{openTile.label}</h2>
          <RangeBar value={chartRange} onChange={setChartRange} />
          {!points ? <p className="empty">Loading...</p> : (
            openTile.form === 'sleep' ? <SleepStagesChart points={points} />
            : openTile.form === 'bar' ? <BarChart points={points} />
            : <LineChart points={points} zeroBased={openTile.zeroBased}
                         format={openTile.key === 'weight_lb' ? (v) => v.toFixed(1) : undefined} />
          )}
          {stats && (
            <div className="stat-row">
              <div className="strip-stat">
                <span className="n">{formatValue(open, stats.average, openTile.digits)}</span>
                <span className="k">average{openTile.unit ? ` ${openTile.unit}` : ''}</span>
              </div>
              <div className="strip-stat">
                <span className="n">{formatValue(open, stats.min, openTile.digits)}</span>
                <span className="k">lowest</span>
              </div>
              <div className="strip-stat">
                <span className="n">{formatValue(open, stats.max, openTile.digits)}</span>
                <span className="k">highest</span>
              </div>
              <div className="strip-stat">
                <span className="n">{stats.days}</span>
                <span className="k">days with data</span>
              </div>
            </div>
          )}

          {stats?.stage_averages && (
            <p className="ring-caption">
              Average night: {Object.entries(stats.stage_averages)
                .map(([k, v]) => `${k.toLowerCase()} ${Math.round(v)}m`).join(' · ')}
            </p>
          )}

          {open === 'readiness' && (
            <p className="ring-caption" style={{ marginTop: 'var(--space-md)' }}>
              Derived score: 60% last night&rsquo;s sleep against an 8 hour target, 40% acute-to-chronic
              training load. No connected provider reports readiness directly.
            </p>
          )}
        </div>
      )}

      <div className="card section">
        <h2>Consistency &mdash; last 16 weeks</h2>
        <Consistency data={consistency} />
      </div>

      <PersonalBests data={bests} onChanged={() => api.personalBests().then(setBests)} />

      {range?.start_date && (
        <p className="ring-caption">
          {range.activities.toLocaleString()} activities on record from {range.start_date} to {range.end_date}.
        </p>
      )}
    </>
  )
}
