import { useEffect, useState } from 'react'
import { api } from '../api'
import { BarChart, LineChart, Ring, SleepStagesChart } from '../components/charts'
import Consistency from '../components/Consistency'
import PersonalBests from '../components/PersonalBests'
import RangeBar, { RANGES, startDateFor } from '../components/RangeBar'

const SLEEP_TARGET_MIN = 8 * 60

const TILES = [
  { key: 'readiness', label: 'Recovery', unit: '', form: 'line', digits: 0, betterWhen: 'up', zeroBased: true, accent: 'var(--recovery-high)' },
  { key: 'sleep_minutes', label: 'Sleep', unit: '', form: 'sleep', digits: 0, betterWhen: 'up', accent: 'var(--sleep)' },
  { key: 'steps', label: 'Steps', unit: '', form: 'bar', digits: 0, betterWhen: 'up', accent: 'var(--exertion)' },
  { key: 'weight_lb', label: 'Weight', unit: 'lb', form: 'line', digits: 1, betterWhen: 'down', accent: 'var(--text-faint)' },
]

/* Recovery banding follows the traffic-light convention the reference product
   uses: green means go hard, yellow means moderate, red means back off. */
function recoveryColor(value) {
  if (value == null) return 'var(--text-faint)'
  if (value >= 67) return 'var(--recovery-high)'
  if (value >= 34) return 'var(--recovery-mid)'
  return 'var(--recovery-low)'
}

function recoveryVerdict(value) {
  if (value == null) return 'No sleep or load data for today yet.'
  if (value >= 67) return 'Primed. Your body is ready for a hard session.'
  if (value >= 34) return 'Moderate. Hold intensity steady rather than pushing.'
  return 'Low. Prioritise sleep and keep today easy.'
}

function hoursMinutes(minutes) {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return `${h}:${String(m).padStart(2, '0')}`
}

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

  const recovery = summary.readiness?.value ?? null
  const recoveryHue = recoveryColor(recovery)

  const exertion = azm?.total || 0
  const exertionGoal = azm?.goal || 300

  const sleep = summary.sleep_minutes?.value ?? null

  return (
    <>
      <div className="overview">
        <section className="ring-card" style={{ '--ring-color': recoveryHue }}>
          <span className="eyebrow">Recovery</span>
          <Ring
            pct={recovery == null ? 0 : recovery / 100}
            color={recoveryHue}
            label={recovery == null ? 'Recovery unavailable' : `Recovery ${Math.round(recovery)} percent`}
          >
            <span className="ring-value" style={{ color: recoveryHue }}>
              {recovery == null ? '--' : Math.round(recovery)}
              {recovery != null && <span className="ring-suffix">%</span>}
            </span>
            <span className="ring-sub">{summary.readiness?.date || 'no data'}</span>
          </Ring>
          <p className="ring-note">{recoveryVerdict(recovery)}</p>
        </section>

        <section className="ring-card" style={{ '--ring-color': 'var(--exertion)' }}>
          <span className="eyebrow">Exertion</span>
          <Ring
            pct={exertionGoal > 0 ? exertion / exertionGoal : 0}
            color="var(--exertion)"
            label={`${Math.round(exertion)} of ${exertionGoal} active zone minutes this week`}
          >
            <span className="ring-value" style={{ color: 'var(--exertion)' }}>
              {Math.round(exertion).toLocaleString()}
            </span>
            <span className="ring-sub">of {exertionGoal} azm</span>
          </Ring>
          <p className="ring-note">
            Weekly active zone minutes. Moderate heart-rate minutes count once, vigorous and peak count double.
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
        </section>

        <section className="ring-card" style={{ '--ring-color': 'var(--sleep)' }}>
          <span className="eyebrow">Sleep</span>
          <Ring
            pct={sleep == null ? 0 : sleep / SLEEP_TARGET_MIN}
            color="var(--sleep)"
            label={sleep == null ? 'Sleep unavailable' : `${hoursMinutes(sleep)} of 8 hours`}
          >
            <span className="ring-value" style={{ color: 'var(--sleep)' }}>
              {sleep == null ? '--' : hoursMinutes(sleep)}
            </span>
            <span className="ring-sub">
              {sleep == null ? 'no data' : `${Math.round((sleep / SLEEP_TARGET_MIN) * 100)}% of 8 h`}
            </span>
          </Ring>
          <p className="ring-note">
            Last night against an eight hour target. Open the sleep tile below for the stage breakdown.
          </p>
        </section>
      </div>

      <div className="grid-tiles">
        {TILES.map((tile) => {
          const m = summary[tile.key]
          return (
            <button
              key={tile.key}
              className="tile"
              style={{ '--tile-accent': tile.accent }}
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
            : openTile.form === 'bar' ? <BarChart points={points} color={openTile.accent} />
            : <LineChart points={points} color={openTile.accent} zeroBased={openTile.zeroBased}
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
            <p className="ring-note" style={{ marginTop: 'var(--space-md)', maxWidth: '62ch' }}>
              Average night: {Object.entries(stats.stage_averages)
                .map(([k, v]) => `${k.toLowerCase()} ${Math.round(v)}m`).join(' · ')}
            </p>
          )}

          {open === 'readiness' && (
            <p className="ring-note" style={{ marginTop: 'var(--space-md)', maxWidth: '62ch' }}>
              Derived score: 60% last night&rsquo;s sleep against an 8 hour target, 40% acute-to-chronic
              training load. No connected provider reports recovery directly.
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
        <p className="ring-note" style={{ maxWidth: '62ch' }}>
          {range.activities.toLocaleString()} activities on record from {range.start_date} to {range.end_date}.
        </p>
      )}
    </>
  )
}
