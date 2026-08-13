import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

// Withings is body metrics only, so it never appears in the activity feed.
const SOURCE_LABEL = {
  strava: 'Strava',
  hevy: 'Hevy',
  google_health: 'Google Health',
}

const SOURCE_LINK = {
  strava: (id) => `https://www.strava.com/activities/${id}`,
}

function KeyMetric({ activity: a }) {
  if (a.distance_miles) {
    return (
      <>
        {a.distance_miles} mi
        {a.avg_mph ? <> &middot; {a.avg_mph} mph</> : null}
      </>
    )
  }
  return <>{a.duration_minutes ? `${Math.round(a.duration_minutes)} min` : '--'}</>
}

function fmtClock(ts) {
  if (!ts) return null
  return new Date(ts * 1000).toLocaleString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })
}

function pace(a) {
  if (!a.distance_miles || !a.duration_minutes) return null
  const secs = (a.duration_minutes * 60) / a.distance_miles
  const m = Math.floor(secs / 60)
  const s = Math.round(secs % 60)
  return `${m}:${String(s).padStart(2, '0')} /mi`
}

function Detail({ activity: a, onClose }) {
  const rows = [
    ['When', fmtClock(a.start_ts) || a.date],
    ['Type', a.activity_type],
    ['Source', SOURCE_LABEL[a.source] || a.source],
    ['Duration', a.duration_minutes ? `${Math.round(a.duration_minutes)} min` : null],
    ['Distance', a.distance_miles ? `${a.distance_miles} mi` : null],
    ['Pace', pace(a)],
    ['Average speed', a.avg_mph ? `${a.avg_mph} mph` : null],
    ['Elevation gain', a.elevation_gain_ft ? `${Math.round(a.elevation_gain_ft)} ft` : null],
    ['Calories', a.calories ? `${Math.round(a.calories)} kcal` : null],
    ['Active zone minutes', a.active_zone_minutes ? `${a.active_zone_minutes} AZM` : null],
    ['Training load', a.load_score ? a.load_score.toFixed(1) : null],
  ].filter(([, v]) => v)

  const link = SOURCE_LINK[a.source]?.(a.id)

  return (
    <div className="drawer" role="dialog" aria-label={a.name}>
      <div className="drawer-head">
        <div>
          <div className="drawer-title">{a.name || a.activity_type}</div>
          <div className="feed-sub"><span className="badge">{SOURCE_LABEL[a.source] || a.source}</span></div>
        </div>
        <button className="btn secondary small" onClick={onClose}>Close</button>
      </div>

      <dl className="detail-grid">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>

      {link && (
        <a className="btn secondary small" href={link} target="_blank" rel="noreferrer">
          Open in Strava
        </a>
      )}
    </div>
  )
}

export default function Activities() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [source, setSource] = useState('')
  const [type, setType] = useState('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)
  const [limit, setLimit] = useState(100)

  useEffect(() => {
    api.activities({ source: source || null, activity_type: type || null })
      .then((r) => { setData(r); setLimit(100) })
      .catch((e) => setError(e.message))
  }, [source, type])

  const types = useMemo(() => {
    if (!data) return []
    return [...new Set(data.activities.map((a) => a.activity_type))].sort()
  }, [data])

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    if (!q) return data.activities
    return data.activities.filter((a) =>
      (a.name || '').toLowerCase().includes(q) ||
      (a.activity_type || '').toLowerCase().includes(q) ||
      (a.date || '').includes(q)
    )
  }, [data, query])

  if (error) return <div className="notice">Could not reach the API: {error}</div>

  return (
    <>
      <div className="filters">
        <label className="visually-hidden" htmlFor="q">Search activities</label>
        <input id="q" type="text" placeholder="Search by name, type or date"
               value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />

        <label className="visually-hidden" htmlFor="src">Source</label>
        <select id="src" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {Object.entries(SOURCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        <label className="visually-hidden" htmlFor="type">Activity type</label>
        <select id="type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {selected && <Detail activity={selected} onClose={() => setSelected(null)} />}

      <div className="card">
        <h2>
          {data
            ? `${filtered.length} ${query ? 'matching ' : ''}${filtered.length === 1 ? 'activity' : 'activities'}`
            : 'Loading...'}
          {query && data ? ` of ${data.count}` : ''}
        </h2>

        <div className="feed">
          {filtered.slice(0, limit).map((a) => (
            <button
              className={`feed-row feed-button${selected && selected.source === a.source && selected.id === a.id ? ' active' : ''}`}
              key={`${a.source}-${a.id}`}
              onClick={() => setSelected(a)}
            >
              <div>
                <div className="feed-title">{a.name || a.activity_type}</div>
                <div className="feed-sub">
                  <span className="badge">{SOURCE_LABEL[a.source] || a.source}</span>
                  <span>{a.activity_type}</span>
                  <span>{a.date}</span>
                </div>
              </div>
              <div className="feed-metric"><KeyMetric activity={a} /></div>
            </button>
          ))}

          {data && !filtered.length && <p className="empty">Nothing matches these filters.</p>}
        </div>

        {filtered.length > limit && (
          <button className="btn secondary" style={{ marginTop: 'var(--space-md)' }}
                  onClick={() => setLimit(limit + 200)}>
            Show more ({filtered.length - limit} remaining)
          </button>
        )}
      </div>
    </>
  )
}
