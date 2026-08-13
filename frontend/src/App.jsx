import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './tabs/Dashboard'
import Activities from './tabs/Activities'
import Assistant from './tabs/Assistant'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', Component: Dashboard },
  { id: 'activities', label: 'Activities', Component: Activities },
  { id: 'assistant', label: 'Assistant', Component: Assistant },
]

function lastSyncedLabel(sync) {
  const times = Object.values(sync || {})
    .map((s) => s.last_synced_at)
    .filter(Boolean)
  if (!times.length) return 'Never synced'

  const mins = Math.round((Date.now() / 1000 - Math.max(...times)) / 60)
  if (mins < 1) return 'Synced just now'
  if (mins < 60) return `Synced ${mins} min ago`
  return `Synced ${Math.round(mins / 60)} h ago`
}

export default function App() {
  const [active, setActive] = useState('dashboard')
  const [sync, setSync] = useState(null)

  useEffect(() => { api.syncStatus().then((r) => setSync(r.sync)).catch(() => {}) }, [])

  const Active = TABS.find((t) => t.id === active).Component

  return (
    <div className="shell">
      <header className="masthead">
        <h1>Performance</h1>
        <span className="sub">{lastSyncedLabel(sync)}</span>
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
