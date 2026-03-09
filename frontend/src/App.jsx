import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, GraduationCap, AlertCircle, Square } from 'lucide-react'
import Sidebar from './components/Sidebar'
import ChatMessage from './components/ChatMessage'
import { useStatus } from './hooks/useStatus'
import { api } from './api/client'

export default function App() {
  const { status, loading: statusLoading, error: statusError, refresh } = useStatus()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [querying, setQuerying] = useState(false)
  const [queryError, setQueryError] = useState(null)
  const bottomRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, querying])

  async function handleSend() {
    const q = input.trim()
    if (!q || querying) return
    setInput('')
    setQueryError(null)

    // Add user message
    setMessages(m => [...m, { role: 'user', content: q }])

    setMessages(m => [...m, { role: 'assistant', content: '', sources: [], streaming: true }])
    setQuerying(true)

    // Abort controller for cancellation
    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      await api.queryStream(
        q,
        {
          onSources(sources) {
            setMessages(m => {
              const updated = [...m]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, sources }
              }
              return updated
            })
          },
          onToken(token) {
            setMessages(m => {
              const updated = [...m]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: last.content + token }
              }
              return updated
            })
          },
          onDone() {
            setMessages(m => {
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
            setMessages(m => {
              const updated = [...m]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, streaming: false }
              }
              return updated
            })
          },
        },
        abortController.signal,
      )
    } catch (e) {
      if (e.name !== 'AbortError') {
        setQueryError(e.message)
      }
      // Mark streaming as done on error/abort
      setMessages(m => {
        const updated = [...m]
        const last = updated[updated.length - 1]
        if (last?.role === 'assistant') {
          updated[updated.length - 1] = { ...last, streaming: false }
        }
        return updated
      })
    } finally {
      setQuerying(false)
      abortRef.current = null
    }
  }

  function handleStop() {
    abortRef.current?.abort()
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const notIndexed = !statusLoading && status?.chunk_count === 0

  return (
    <div className="layout">
      <Sidebar status={status} onStatusRefresh={refresh} />

      <main className="main">
        {/* Header */}
        <header className="main-header">
          <GraduationCap size={22} />
          <div>
            <h1>University Regulations Assistant</h1>
            <p>Ask questions about rules, procedures, and documents</p>
          </div>
        </header>

        {/* Chat area */}
        <div className="chat-area">
          {statusError && (
            <div className="banner banner-err">
              <AlertCircle size={15} />
              Backend unreachable: {statusError}
            </div>
          )}

          {notIndexed && !statusError && (
            <div className="banner banner-info">
              No documents indexed yet. Add PDFs to <code>backend/data/docs/</code> and click <strong>Index / Re-index</strong> in the sidebar.
            </div>
          )}

          {messages.length === 0 && !notIndexed && (
            <div className="empty-state">
              <span className="empty-icon">📋</span>
              <p>Ask anything about university regulations</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessage key={i} {...msg} />
          ))}

          {queryError && (
            <div className="banner banner-err">
              <AlertCircle size={14} />
              {queryError}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="input-row">
          <textarea
            className="chat-input"
            rows={1}
            placeholder="Ask about university regulations…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={querying || notIndexed}
          />

          {querying ? (
            <button
              className="stop-btn"
              onClick={handleStop}
              title="Stop generating"
            >
              <Square size={16} />
            </button>
          ) : (
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || notIndexed}
            >
              <Send size={18} />
            </button>
          )}

          {messages.length > 0 && (
            <button
              className="clear-btn"
              onClick={() => setMessages([])}
              title="Clear chat"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </main>
    </div>
  )
}