const BASE = '/api'

async function get(path, params) {
  const qs = params ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))}` : ''
  const res = await fetch(`${BASE}${path}${qs}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function put(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function del(path) {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

const enc = (s) => encodeURIComponent(s)

export const api = {
  createPersonalBest: (body) => post('/personal-bests', body),
  updatePersonalBest: (category, name, body) => put(`/personal-bests/${enc(category)}/${enc(name)}`, body),
  deletePersonalBest: (category, name) => del(`/personal-bests/${enc(category)}/${enc(name)}`),
  metricsSummary: () => get('/metrics/summary'),
  metric: (name, params) => get(`/metrics/${name}`, params),
  activities: (params) => get('/activities', params),
  weeklyLoad: (params) => get('/graphs/weekly-load', params),
  activeZoneMinutes: (days) => get('/metrics/active-zone-minutes', { days }),
  consistency: (days) => get('/metrics/consistency', { days }),
  dataRange: () => get('/metrics/range'),
  settings: () => get('/settings'),
  updateSettings: (body) => put('/settings', body),
  personalBests: () => get('/personal-bests'),
  syncStatus: () => get('/sync/status'),
  sync: () => post('/sync'),
  chat: (message, conversationId) => post('/assistant/chat', { message, conversation_id: conversationId }),
  assistantStatus: () => get('/assistant/status'),
  conversations: () => get('/assistant/conversations'),
  conversation: (id) => get(`/assistant/conversations/${enc(id)}`),
  deleteConversation: (id) => del(`/assistant/conversations/${enc(id)}`),
}
