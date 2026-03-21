import { useState, useRef, useEffect } from 'react'
import { Send, StopCircle, AlertCircle, Trash2, Menu, X } from 'lucide-react'
import Sidebar from './components/ui/Sidebar'
import { useStatus } from './hooks/useStatus'
import { api } from './api/client'
import { Button } from './components/ui/button'
import { MessageItem } from './components/ui/message-item'

const MAX_STORED_MESSAGES = 6
const STORAGE_KEY = 'askuhh_chat_history'

// Main app component: controls chat flow, sidebar state, and message rendering.
export default function App() {
  const { status, loading: statusLoading, error: statusError, refresh } = useStatus()
  const [messages, setMessages] = useState(() => {
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

  // Stops the current streaming request and resets loading animation states.
  function handleAbort() {
    abortRef.current?.abort()
    abortRef.current = null
    setQuerying(false)
    setAnimating(false)
  }

  // Clears the recent chat history and also cancels streaming if needed.
  function handleClearRecent() {
    if (querying) {
      handleAbort()
    }
    setQueryError(null)
    setMessages([])
  }

  useEffect(() => {
    if (messages.length === 0) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    // Keep only the latest messages so localStorage does not grow forever.
    try {
      const toStore = messages.slice(-MAX_STORED_MESSAGES).map((msg) => ({
        role: msg.role,
        content: msg.content,
        sources: msg.sources || [],
        avgProbability: msg.avgProbability ?? null,
        logprobs: msg.logprobs ?? [],
        followups: msg.followups ?? [],
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

  // Runs send animation first, then sends the trimmed user question.
  async function handleSend() {
    const q = input.trim()
    if (!q || querying || animating) return

    setAnimating(true)
    setTimeout(() => {
      setAnimating(false)
      setInput('')
      sendQuestion(q)
    }, 380)
  }

  // Enter sends the message, Shift+Enter keeps normal multiline typing.
  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Clicking a follow-up chip sends that exact question.
  function handleFollowupClick(question) {
    if (querying || animating) return
    setInput(question)
    setTimeout(() => {
      setInput('')
      sendQuestion(question)
    }, 50)
  }

  // Full ask flow: add user msg, stream assistant tokens, and update UI chunks.
  async function sendQuestion(q) {
    if (!q || querying || animating) return

    setQueryError(null)

    const previousUserQuestions = messages
      .filter((m) => m.role === 'user' && typeof m.content === 'string' && m.content.trim())
      .map((m) => m.content.trim())
      .slice(-8)

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
          onDone(data) {
            setMessages((m) => {
              const updated = [...m]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  streaming: false,
                  logprobs: data?.logprobs ?? [],
                  avgProbability: data?.avg_probability ?? null,
                  debugImages: data?.debug_images ?? [],
                }
              }
              return updated
            })
          },
          onFollowups(followups) {
            setMessages((m) => {
              const updated = [...m]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = { ...last, followups }
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
        controller.signal,
        previousUserQuestions
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
  }

  const notIndexed = !statusLoading && status?.chunk_count === 0

  // Reusable input UI for centered first question and bottom follow-up mode.
  const inputBox = (centered) => (
    <div
      className={[
        'mx-auto flex w-[min(680px,calc(100%-56px))] items-end gap-2 rounded-[14px] border-[1.5px] border-[#3a3f4a] bg-[#2c313a] px-[14px] py-2 transition focus-within:border-[#9aa3af] focus-within:shadow-[0_0_0_3px_rgba(213,217,224,0.16)]',
        centered ? 'mb-0' : '',
      ].join(' ')}
    >
      <textarea
        ref={textareaRef}
        className={[
          'min-h-[44px] max-h-[200px] w-full flex-1 resize-none bg-transparent px-[6px] py-[10px] text-[13.5px] leading-[1.65] text-[#ede9e1] outline-none placeholder:text-[#6e7480] disabled:opacity-40',
          animating
            ? 'opacity-0 -translate-y-[7px] blur-[3px] transition duration-[380ms] ease-in'
            : '',
        ].join(' ')}
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
      <div className="flex shrink-0 items-end pb-[6px]">
        {querying ? (
          <Button
            onClick={handleAbort}
            size="icon"
            variant="ghost"
            className="h-[30px] w-[30px] shrink-0 rounded-[8px] border border-[#363b44] bg-[rgba(34,37,43,0.9)] text-[#e06666] transition hover:border-[rgba(224,102,102,0.45)] hover:bg-[rgba(224,102,102,0.08)] hover:text-[#e06666]"
            title="Stop generation"
          >
            <StopCircle size={18} />
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={!input.trim() || animating || notIndexed}
            size="icon"
            className="h-[30px] w-[30px] shrink-0 rounded-[8px] border border-[#363b44] bg-[rgba(34,37,43,0.9)] text-[#9ba0aa] transition hover:border-[#9aa3af] hover:bg-[rgba(213,217,224,0.12)] hover:text-[#d5d9e0]"
            title="Send"
          >
            <Send size={18} />
          </Button>
        )}
      </div>
    </div>
  )

  return (
    <div className="relative flex h-screen overflow-hidden bg-[#1a1d21] text-[#ede9e1]">
      <button
        type="button"
        className="absolute left-4 top-[14px] z-30 inline-flex h-8 w-8 items-center justify-center rounded-[9px] border border-[#363b44] bg-[rgba(34,37,43,0.9)] text-[#9ba0aa] transition hover:border-[#9aa3af] hover:bg-[rgba(213,217,224,0.12)] hover:text-[#d5d9e0]"
        onClick={() => setSidebarOpen((v) => !v)}
      >
        {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
      </button>

      <Sidebar status={status} onStatusRefresh={refresh} isOpen={sidebarOpen} />

      <main className="flex min-w-0 flex-1 flex-col" role="main" aria-label="Chat interface">
        {statusError && (
          <div className="mx-7 mt-4 flex items-start gap-2 rounded-[6px] border border-[rgba(192,80,77,0.25)] bg-[rgba(192,80,77,0.1)] px-[14px] py-3 text-[13px] leading-[1.5] text-[#e07a77]">
            <AlertCircle size={15} />
            Backend unreachable: {statusError}
          </div>
        )}
        {notIndexed && !statusError && (
          <div className="mx-7 mt-4 flex items-start gap-2 rounded-[6px] border border-[rgba(77,127,168,0.25)] bg-[rgba(77,127,168,0.1)] px-[14px] py-3 text-[13px] leading-[1.5] text-[#7aaed0]">
            No documents indexed yet. Add PDFs to <code>backend/data/docs/</code> and click{' '}
            <strong>Index / Re-index</strong> in the sidebar.
          </div>
        )}

        {!hasStarted ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-5 p-7">
            <p className="text-center text-[30px] font-normal tracking-[0.01em] text-[#9ba0aa] [font-family:'Bebas_Neue',sans-serif]">
              What do you want to know?
            </p>
            {inputBox(true)}
          </div>
        ) : (
          <div className="relative flex flex-1 flex-col overflow-hidden">
            <button
              type="button"
              className="absolute right-[18px] top-[14px] z-20 inline-flex h-[30px] w-[30px] items-center justify-center rounded-[8px] border border-[#363b44] bg-[rgba(34,37,43,0.9)] text-[#9ba0aa] transition hover:border-[rgba(224,102,102,0.45)] hover:bg-[rgba(224,102,102,0.08)] hover:text-[#e06666] disabled:cursor-not-allowed disabled:opacity-45"
              onClick={handleClearRecent}
              disabled={querying || messages.length === 0}
              aria-label="Letzte 6 Nachrichten loeschen"
            >
              <Trash2 size={14} />
            </button>

            <div
              className="flex flex-1 flex-col gap-4 overflow-y-auto px-7 pb-40 pt-14 [scrollbar-width:thin] [scrollbar-color:#363b44_transparent] [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-[#363b44] [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:w-1"
              role="log"
              aria-live="polite"
              aria-label="Chat messages"
            >
              {messages.map((msg, i) => {
                const isLastAssistant =
                  msg.role === 'assistant' && !querying && i === messages.length - 1
                return (
                  <MessageItem
                    key={i}
                    {...msg}
                    showFollowups={isLastAssistant}
                    onFollowupClick={handleFollowupClick}
                  />
                )
              })}

              {queryError && (
                <div
                  className="flex items-start gap-2 rounded-[6px] border border-[rgba(192,80,77,0.25)] bg-[rgba(192,80,77,0.1)] px-[14px] py-3 text-[13px] leading-[1.5] text-[#e07a77]"
                  role="alert"
                >
                  <AlertCircle size={14} />
                  {queryError}
                </div>
              )}

              <div ref={bottomRef} aria-hidden="true" />
            </div>

            <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-[linear-gradient(to_bottom,transparent_0%,#1a1d21_38%)] px-0 pb-8 pt-9">
              <div className="pointer-events-auto">{inputBox(false)}</div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
