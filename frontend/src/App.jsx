import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './tabs/Dashboard'
import Activities from './tabs/Activities'
import Assistant from './tabs/Assistant'

const TABS = [
  { id: 'dashboard', label: 'Overview', Component: Dashboard },
  { id: 'activities', label: 'Activities', Component: Activities },
  { id: 'assistant', label: 'Coach', Component: Assistant },
]

function syncState(sync) {
  const times = Object.values(sync || {})
    .map((s) => s.last_synced_at)
    .filter(Boolean)
  if (!times.length) return { tone: 'off', label: 'Never synced' }

  const mins = Math.round((Date.now() / 1000 - Math.max(...times)) / 60)
  if (mins < 1) return { tone: 'live', label: 'Synced just now' }
  if (mins < 60) return { tone: 'live', label: `Synced ${mins} min ago` }

  const hours = Math.round(mins / 60)
  return { tone: hours > 24 ? 'stale' : 'live', label: `Synced ${hours} h ago` }
}

export default function App() {
  const [active, setActive] = useState('dashboard')
  const [sync, setSync] = useState(null)

  useEffect(() => { api.syncStatus().then((r) => setSync(r.sync)).catch(() => {}) }, [])

  const Active = TABS.find((t) => t.id === active).Component
  const state = syncState(sync)

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">P</span>
          <h1>Performance</h1>
        </div>
        <span className="sync-pill">
          <span className={`sync-dot ${state.tone === 'live' ? '' : state.tone}`} aria-hidden="true" />
          {state.label}
        </span>
      </header>

      <div className="tabs" role="tablist" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={active === t.id}
            onClick={() => setActive(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <main role="tabpanel">
        <Active />
      </main>
    </div>
  )
}
