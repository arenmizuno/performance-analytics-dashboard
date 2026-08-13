import { useState } from 'react'
import { api } from '../api'

const KNOWN_ORDER = ['running', 'triathlon', 'swim', 'strength']

function sortCategories(categories, known) {
  const rest = Object.keys(categories).filter((c) => !KNOWN_ORDER.includes(c)).sort()
  return [...KNOWN_ORDER.filter((c) => categories[c]), ...rest]
}

function PbEditor({ pb, onSave, onCancel, onDelete, onReset }) {
  const [value, setValue] = useState(pb.display_value || '')
  const [date, setDate] = useState(pb.date_achieved || '')
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    // Keep a numeric value alongside the display string where one can be parsed,
    // so the improvement comparison still works on the server.
    const numeric = parseTimeOrNumber(value)
    await onSave({
      display_value: value || null,
      value: numeric,
      unit: pb.unit || (value.includes(':') ? 'time' : null),
      date_achieved: date || null,
    })
    setBusy(false)
  }

  return (
    <div className="pb-edit">
      <label className="visually-hidden" htmlFor={`v-${pb.name}`}>Value for {pb.name}</label>
      <input
        id={`v-${pb.name}`}
        type="text"
        value={value}
        placeholder="e.g. 1:29:44 or 185 lb"
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      <label className="visually-hidden" htmlFor={`d-${pb.name}`}>Date for {pb.name}</label>
      <input id={`d-${pb.name}`} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <div className="pb-actions">
        <button className="btn small" onClick={save} disabled={busy}>Save</button>
        <button className="btn small secondary" onClick={onCancel}>Cancel</button>
        {pb.source === 'manual' && (
          <button className="btn small secondary" onClick={onReset} title="Hand back to automatic derivation">
            Use auto
          </button>
        )}
        <button className="btn small danger" onClick={onDelete}>Delete</button>
      </div>
    </div>
  )
}

function parseTimeOrNumber(text) {
  if (!text) return null
  const t = text.trim()
  if (/^\d+(:\d{1,2}){1,2}$/.test(t)) {
    const parts = t.split(':').map(Number)
    const secs = parts.length === 3
      ? parts[0] * 3600 + parts[1] * 60 + parts[2]
      : parts[0] * 60 + parts[1]
    return Number((secs / 60).toFixed(2)) // minutes, matching derived running bests
  }
  const num = parseFloat(t.replace(/[^\d.]/g, ''))
  return Number.isFinite(num) ? num : null
}

function AddForm({ categories, onAdd, onClose }) {
  const [category, setCategory] = useState(categories[0] || 'running')
  const [custom, setCustom] = useState('')
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [date, setDate] = useState('')

  const target = category === '__new__' ? custom.trim().toLowerCase() : category
  const canSave = target && name.trim()

  return (
    <div className="card pb-add">
      <h2>Add an entry</h2>
      <div className="filters">
        <label className="visually-hidden" htmlFor="cat">Category</label>
        <select id="cat" value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          <option value="__new__">New category...</option>
        </select>

        {category === '__new__' && (
          <input type="text" placeholder="Category name" value={custom}
                 onChange={(e) => setCustom(e.target.value)} />
        )}

        <input type="text" placeholder="Event or lift name" value={name}
               onChange={(e) => setName(e.target.value)} />
        <input type="text" placeholder="Result (optional)" value={value}
               onChange={(e) => setValue(e.target.value)} />
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />

        <button className="btn" disabled={!canSave} onClick={() => onAdd({
          category: target,
          name: name.trim(),
          display_value: value || null,
          value: parseTimeOrNumber(value),
          unit: value.includes(':') ? 'time' : null,
          date_achieved: date || null,
        })}>Add</button>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}

export default function PersonalBests({ data, onChanged }) {
  const [editing, setEditing] = useState(null)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState(null)

  if (!data) return null

  const categories = sortCategories(data.categories, data.known_categories)

  async function run(fn) {
    try {
      await fn()
      setEditing(null)
      setAdding(false)
      setError(null)
      onChanged()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="section">
      <div className="section-head">
        <h2>Personal bests</h2>
        <button className="btn secondary" onClick={() => setAdding(!adding)}>
          {adding ? 'Close' : 'Add entry'}
        </button>
      </div>

      {error && <div className="notice" style={{ marginBottom: 'var(--space-md)' }}>{error}</div>}

      {adding && (
        <AddForm
          categories={data.known_categories}
          onClose={() => setAdding(false)}
          onAdd={(body) => run(() => api.createPersonalBest(body))}
        />
      )}

      {categories.map((category) => (
        <div key={category} className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <h2>{category}</h2>
          <div className="pb-grid">
            {data.categories[category].map((pb) => {
              const key = `${category}/${pb.name}`
              if (editing === key) {
                return (
                  <div className="pb editing" key={pb.name}>
                    <div className="pb-name">{pb.name}</div>
                    <PbEditor
                      pb={pb}
                      onCancel={() => setEditing(null)}
                      onSave={(body) => run(() => api.updatePersonalBest(category, pb.name, body))}
                      onReset={() => run(() => api.updatePersonalBest(category, pb.name, {
                        display_value: null, value: null, unit: null, date_achieved: null,
                      }))}
                      onDelete={() => run(() => api.deletePersonalBest(category, pb.name))}
                    />
                  </div>
                )
              }

              return (
                <button className="pb pb-button" key={pb.name} onClick={() => setEditing(key)}>
                  <div className="pb-name">{pb.name}</div>
                  <div className={`pb-val${pb.display_value ? '' : ' empty'}`}>
                    {pb.display_value || 'Not set'}
                  </div>
                  <div className="pb-date">
                    {pb.date_achieved || 'tap to add'}
                    {pb.source && <span className={`pb-src ${pb.source}`}>{pb.source === 'manual' ? 'manual' : 'auto'}</span>}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
