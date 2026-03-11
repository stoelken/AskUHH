import { useState, useRef, useEffect } from 'react'
import { Send, StopCircle, AlertCircle, Trash2, Menu, X } from 'lucide-react'
import Sidebar from './components/ui/Sidebar'
import { useStatus } from './hooks/useStatus'
import { api } from './api/client'
import { Button } from './components/ui/button'
import { MessageItem } from './components/ui/message-item'

// Anzahl der gespeicherten Nachrichten (änderbar)
const MAX_STORED_MESSAGES = 6
const STORAGE_KEY = 'askuhh_chat_history'

export default function App() {
  const { status, loading: statusLoading, error: statusError, refresh } = useStatus()
  const [messages, setMessages] = useState(() => {
    // Lade gespeicherte Nachrichten beim ersten Render
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? JSON.parse(stored) : []
    } catch (e) {
      console.error('Failed to load chat history:', e)
      return []
    }
  })
  const [input, setInput] = useState('')
  const [querying, setQuerying] = useState(false)
  const [queryError, setQueryError] = useState(null)
  const [animating, setAnimating] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const abortRef = useRef(null)
  const hasStarted = messages.length > 0

  function handleAbort() {
    abortRef.current?.abort()
    abortRef.current = null
    setQuerying(false)
    setAnimating(false)
  }

  function handleClearRecent() {
    if (querying) {
      handleAbort()
    }
    setQueryError(null)
    setMessages((m) => m.slice(0, Math.max(0, m.length - 6)))
  }

  // Speichere die letzten N Nachrichten bei Änderungen
  useEffect(() => {
    if (messages.length === 0) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    try {
      const toStore = messages.slice(-MAX_STORED_MESSAGES).map((msg) => ({
        role: msg.role,
        content: msg.content,
        sources: msg.sources || [],
        // streaming-Flag nicht speichern
      }))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore))
    } catch (e) {
      console.error('Failed to save chat history:', e)
    }
  }, [messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, querying])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [input])

  async function handleSend() {
    const q = input.trim()
    if (!q || querying || animating) return

    setAnimating(true)
    setTimeout(async () => {
      setAnimating(false)
      setInput('')
      setQueryError(null)

      setMessages((m) => [...m, { role: 'user', content: q }])
      setMessages((m) => [...m, { role: 'assistant', content: '', sources: [], streaming: true }])
      setQuerying(true)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        await api.queryStream(
          q,
          {
            onSources(sources) {
              setMessages((m) => {
                const updated = [...m]
                const last = updated[updated.length - 1]
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, sources }
                }
                return updated
              })
            },
            onToken(token) {
              setMessages((m) => {
                const updated = [...m]
                const last = updated[updated.length - 1]
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, content: last.content + token }
                }
                return updated
              })
            },
            onDone() {
              setMessages((m) => {
                const updated = [...m]
                const last = updated[updated.length - 1]
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, streaming: false }
                }
                return updated
              })
            },
            onError(err) {
              setQueryError(err.message)
              setMessages((m) => {
                const updated = [...m]
                const last = updated[updated.length - 1]
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, streaming: false }
                }
                return updated
              })
            },
          },
          controller.signal
        )
      } catch (e) {
        if (e.name !== 'AbortError') {
          setQueryError(e.message)
        }
        setMessages((m) => {
          const updated = [...m]
          const last = updated[updated.length - 1]
          if (last?.role === 'assistant') {
            updated[updated.length - 1] = { ...last, streaming: false }
          }
          return updated
        })
      } finally {
        abortRef.current = null
        setQuerying(false)
      }
    }, 380)
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const notIndexed = !statusLoading && status?.chunk_count === 0

  const inputBox = (centered) => (
    <div className={centered ? 'input-row input-row--centered' : 'input-row'}>
      <textarea
        ref={textareaRef}
        className={`chat-textarea${animating ? ' chat-textarea--vanishing' : ''}${!centered ? ' chat-textarea--followup' : ''}`}
        placeholder={centered ? 'Ask about university regulations…' : 'Follow-up question…'}
        value={input}
        onChange={(e) => !animating && setInput(e.target.value)}
        onKeyDown={handleKey}
        disabled={notIndexed}
        rows={1}
        aria-label={centered ? 'Ask a question' : 'Follow-up question'}
        aria-disabled={notIndexed}
        aria-busy={querying}
      />
      <div className="input-actions">
        {querying ? (
          <Button
            onClick={handleAbort}
            size="icon"
            variant="ghost"
            className="shrink-0 text-err hover:text-err"
            title="Stop generation"
          >
            <StopCircle size={18} />
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={!input.trim() || animating || notIndexed}
            size="icon"
            className="shrink-0"
            title="Send"
          >
            <Send size={18} />
          </Button>
        )}
      </div>
    </div>
  )

  return (
    <div className="layout">
      <button
        type="button"
        className="sidebar-toggle-btn"
        onClick={() => setSidebarOpen((v) => !v)}
        aria-label={sidebarOpen ? 'Dev sidebar schliessen' : 'Dev sidebar oeffnen'}
      >
        {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
      </button>

      <Sidebar status={status} onStatusRefresh={refresh} isOpen={sidebarOpen} />

      <main className="main" role="main" aria-label="Chat interface">
        {statusError && (
          <div className="banner banner-err" style={{ margin: '16px 28px 0' }}>
            <AlertCircle size={15} />
            Backend unreachable: {statusError}
          </div>
        )}
        {notIndexed && !statusError && (
          <div className="banner banner-info" style={{ margin: '16px 28px 0' }}>
            No documents indexed yet. Add PDFs to <code>backend/data/docs/</code> and click{' '}
            <strong>Index / Re-index</strong> in the sidebar.
          </div>
        )}

        {!hasStarted ? (
          <div className="centered-input-wrap">
            <p className="centered-hint">What do you want to know?</p>
            {inputBox(true)}
          </div>
        ) : (
          <div className="chat-wrapper">
            <button
              type="button"
              className="chat-clear-btn"
              onClick={handleClearRecent}
              disabled={querying || messages.length === 0}
              aria-label="Letzte 6 Nachrichten loeschen"
            >
              <Trash2 size={14} />
            </button>

            <div className="chat-area" role="log" aria-live="polite" aria-label="Chat messages">
              {messages.map((msg, i) => (
                <MessageItem key={i} {...msg} />
              ))}

              {queryError && (
                <div className="banner banner-err" role="alert">
                  <AlertCircle size={14} />
                  {queryError}
                </div>
              )}

              <div ref={bottomRef} aria-hidden="true" />
            </div>

            <div className="input-footer">{inputBox(false)}</div>
          </div>
        )}
      </main>
    </div>
  )
}
