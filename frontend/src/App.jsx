import { useState, useRef, useEffect } from 'react'
import { Send, StopCircle, GraduationCap, AlertCircle } from 'lucide-react'
import Sidebar from './components/ui/Sidebar'
import { useStatus } from './hooks/useStatus'
import { api } from './api/client'
import { Button } from './components/ui/button'
import { MessageItem } from './components/ui/message-item'

export default function App() {
  const { status, loading: statusLoading, error: statusError, refresh } = useStatus()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [querying, setQuerying] = useState(false)
  const [queryError, setQueryError] = useState(null)
  const [animating, setAnimating] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const abortRef = useRef(null)
  const hasStarted = messages.length > 0

  function handleAbort() {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setQuerying(false)
    setAnimating(false)
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, querying])

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [input])

  async function handleSend() {
    const q = input.trim()
    if (!q || querying || animating) return

    // 1. Vanish-Animation starten
    setAnimating(true)

    // 2. Nach Animation: Input leeren, Message + Query starten
    setTimeout(async () => {
      setAnimating(false)
      setInput('')
      setQueryError(null)
      setMessages(m => [...m, { role: 'user', content: q }])
      setQuerying(true)
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const res = await api.query(q, controller.signal)
        setMessages(m => [...m, { role: 'assistant', content: res.answer, sources: res.sources }])
      } catch (e) {
        if (e.name !== 'AbortError') setQueryError(e.message)
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
        placeholder={centered ? 'Ask about university regulations… (Enter to send, Shift+Enter for new line)' : 'Follow-up question…'}
        value={input}
        onChange={e => !animating && setInput(e.target.value)}
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
      <Sidebar status={status} onStatusRefresh={refresh} />

      <main className="main" role="main" aria-label="Chat interface">
        {/* Header */}
        <header className="main-header">
          <GraduationCap size={22} />
          <div>
            <h1>University Regulations Assistant</h1>
            <p>Ask questions about rules, procedures, and documents</p>
          </div>
        </header>

        {/* Banners (always visible) */}
        {statusError && (
          <div className="banner banner-err" style={{ margin: '16px 28px 0' }}>
            <AlertCircle size={15} />
            Backend unreachable: {statusError}
          </div>
        )}
        {notIndexed && !statusError && (
          <div className="banner banner-info" style={{ margin: '16px 28px 0' }}>
            No documents indexed yet. Add PDFs to <code>backend/data/docs/</code> and click <strong>Index / Re-index</strong> in the sidebar.
          </div>
        )}

        {!hasStarted ? (
          /* ── Centered start screen ── */
          <div className="centered-input-wrap">
            <p className="centered-hint">What do you want to know?</p>
            {inputBox(true)}
          </div>
        ) : (
          /* ── Chat + bottom input ── */
          <div className="chat-wrapper">
            <div
              className="chat-area"
              role="log"
              aria-live="polite"
              aria-label="Chat messages"
            >
              {messages.map((msg, i) => (
                <MessageItem key={i} {...msg} />
              ))}

              {querying && (
                <div className="message message-assistant" aria-label="Assistant is typing">
                  <div className="message-bubble typing" role="status">
                    <span /><span /><span />
                  </div>
                </div>
              )}

              {queryError && (
                <div className="banner banner-err" role="alert">
                  <AlertCircle size={14} />
                  {queryError}
                </div>
              )}

              <div ref={bottomRef} aria-hidden="true" />
            </div>

            <div className="input-footer">
              {inputBox(false)}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
