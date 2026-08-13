import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

const SUGGESTIONS = [
  'How is my sleep trending vs last month?',
  'What did I lift this week?',
  'Show my running volume over the last 30 days',
]

const LAST_THREAD_KEY = 'assistant.conversation_id'

function relativeTime(seconds) {
  const mins = Math.round((Date.now() / 1000 - seconds) / 60)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`
  return `${Math.round(mins / 1440)}d ago`
}

export default function Assistant() {
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const scroller = useRef(null)

  useEffect(() => {
    api.assistantStatus().then(setStatus).catch(() => setStatus({ configured: false }))
    refreshConversations()

    const last = localStorage.getItem(LAST_THREAD_KEY)
    if (last) openConversation(last, { quiet: true })
  }, [])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  function refreshConversations() {
    api.conversations().then((r) => setConversations(r.conversations)).catch(() => {})
  }

  async function openConversation(id, { quiet = false } = {}) {
    try {
      const r = await api.conversation(id)
      setMessages(r.messages)
      setConversationId(id)
      localStorage.setItem(LAST_THREAD_KEY, id)
    } catch (e) {
      // A thread deleted elsewhere should not wedge the tab.
      localStorage.removeItem(LAST_THREAD_KEY)
      if (!quiet) setError(e.message)
    }
  }

  function newConversation() {
    setMessages([])
    setConversationId(null)
    localStorage.removeItem(LAST_THREAD_KEY)
    setError(null)
  }

  async function removeConversation(id) {
    await api.deleteConversation(id)
    if (id === conversationId) newConversation()
    refreshConversations()
  }

  async function send(text) {
    const content = (text ?? draft).trim()
    if (!content || busy) return

    setMessages([...messages, { role: 'user', content }])
    setDraft('')
    setBusy(true)

    try {
      const res = await api.chat(content, conversationId)
      setConversationId(res.conversation_id)
      localStorage.setItem(LAST_THREAD_KEY, res.conversation_id)
      // Reload from the server so what is shown matches what is stored.
      const r = await api.conversation(res.conversation_id)
      setMessages(r.messages)
      setError(null)
      refreshConversations()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {conversations.length > 0 && (
        <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <div className="section-head" style={{ marginBottom: 'var(--space-sm)' }}>
            <h2 style={{ margin: 0 }}>Conversations</h2>
            <button className="btn small secondary" onClick={newConversation}>New chat</button>
          </div>
          <div className="thread-list">
            {conversations.map((c) => (
              <div key={c.id} className={`thread${c.id === conversationId ? ' active' : ''}`}>
                <button className="thread-open" onClick={() => openConversation(c.id)}>
                  <span className="thread-title">{c.title || 'Untitled'}</span>
                  <span className="thread-meta">
                    {c.message_count} messages &middot; {relativeTime(c.updated_at)}
                  </span>
                </button>
                <button className="thread-delete" aria-label={`Delete ${c.title || 'conversation'}`}
                        onClick={() => removeConversation(c.id)}>&times;</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-head" style={{ marginBottom: 'var(--space-md)' }}>
          <h2 style={{ margin: 0 }}>Assistant</h2>
          {status?.model && <span className="badge">{status.model}</span>}
        </div>

        {status && !status.configured && (
          <div className="notice" style={{ marginBottom: 'var(--space-md)' }}>
            The assistant needs a model API key. Add <code>ASSISTANT_API_KEY</code> to
            your <code>.env</code> (a free key from console.groq.com works) and restart the
            server. Everything else is wired up and waiting.
          </div>
        )}

        {error && <div className="notice" style={{ marginBottom: 'var(--space-md)' }}>{error}</div>}

        <div className="chat" ref={scroller}>
          {!messages.length && (
            <div>
              <p className="empty" style={{ paddingTop: 0 }}>
                Ask about your training, sleep, weight or personal bests.
              </p>
              <div className="filters">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="btn secondary" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.content}
              {m.tools?.length > 0 && (
                <div className="msg-tools">
                  looked up: {[...new Set(m.tools.map((t) => t.name))].join(', ')}
                </div>
              )}
            </div>
          ))}

          {busy && <div className="msg assistant">Thinking...</div>}
        </div>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
          <label className="visually-hidden" htmlFor="msg">Message</label>
          <input id="msg" type="text" value={draft} placeholder="Ask a question"
                 onChange={(e) => setDraft(e.target.value)} />
          <button className="btn" type="submit"
                  disabled={busy || !draft.trim() || (status && !status.configured)}>Send</button>
        </form>
      </div>
    </>
  )
}
