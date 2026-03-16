import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Image,
  Copy,
  Check,
  CornerDownRight,
} from 'lucide-react'
import { Button } from './button'
import { PdfModal, readableTitle } from './PdfModal'
import { cn } from '@/lib/utils'

function scoreSentences(content, logprobs) {
  if (!logprobs?.length || !content?.trim()) return null

  const sentenceRegex = /[^.!?\n]+[.!?\n]?/g
  const rawSentences = content.match(sentenceRegex) ?? [content]
  const sentences = rawSentences.map((s) => s.trim()).filter(Boolean)

  if (!sentences.length) return null

  let tokenCursor = 0
  return sentences.map((sentence) => {
    const sentProbs = []
    let charsMatched = 0

    for (let i = tokenCursor; i < logprobs.length; i++) {
      const t = logprobs[i]
      if (typeof t.probability !== 'number') continue

      charsMatched += t.token.length
      sentProbs.push(t.probability)

      if (charsMatched >= sentence.length) {
        tokenCursor = i + 1
        break
      }
    }

    const avg =
      sentProbs.length > 0
        ? Math.round(sentProbs.reduce((s, p) => s + p, 0) / sentProbs.length)
        : null
    const min = sentProbs.length > 0 ? Math.round(Math.min(...sentProbs)) : null

    return { text: sentence, avgProb: avg, minProb: min }
  })
}

function sentenceBorderColor(avgProb) {
  if (avgProb === null) return 'transparent'
  if (avgProb >= 97) return 'rgba(34,197,94,0.5)'
  if (avgProb >= 93) return 'rgba(234,179,8,0.6)'
  if (avgProb >= 88) return 'rgba(249,115,22,0.7)'
  return 'rgba(239,68,68,0.8)'
}

function SentenceScoredAnswer({ content, logprobs }) {
  const scored = scoreSentences(content, logprobs)

  if (!scored) {
    return (
      <div className="prose prose-sm prose-invert max-w-none [&>*]:my-6 [&>p]:leading-relaxed">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      {scored.map((s, i) => {
        const borderColor = sentenceBorderColor(s.avgProb)
        const tooltip =
          s.avgProb !== null
            ? `avg confidence: ${s.avgProb}% | min: ${s.minProb}%`
            : 'no confidence data'

        return (
          <div
            key={i}
            title={tooltip}
            style={{
              borderLeft: `3px solid ${borderColor}`,
              paddingLeft: '8px',
              cursor: 'help',
            }}
          >
            <ReactMarkdown
              components={{
                p: ({ children }) => <span className="text-sm leading-relaxed">{children}</span>,
              }}
            >
              {s.text}
            </ReactMarkdown>
          </div>
        )
      })}

      <div
        style={{
          display: 'flex',
          gap: '10px',
          marginTop: '6px',
          fontSize: '10px',
          color: '#6c757d',
          flexWrap: 'wrap',
        }}
      >
        <span>
          <span style={{ color: 'rgba(34,197,94,0.9)' }}>▌</span> ≥97%
        </span>
        <span>
          <span style={{ color: 'rgba(234,179,8,0.9)' }}>▌</span> 93–97%
        </span>
        <span>
          <span style={{ color: 'rgba(249,115,22,0.9)' }}>▌</span> 88–93%
        </span>
        <span>
          <span style={{ color: 'rgba(239,68,68,0.9)' }}>▌</span> &lt;88%
        </span>
        <span style={{ opacity: 0.5 }}>hover for details</span>
      </div>
    </div>
  )
}

// Renders one chat bubble (user or assistant) with sources, images, and follow-ups.
export function MessageItem({
  role,
  content,
  sources,
  avgProbability = null,
  streaming = false,
  debugImages = [],
  logprobs = [],
  followups = [],
  showFollowups = false,
  onFollowupClick,
}) {
  const [srcOpen, setSrcOpen] = useState(false)
  const [imgOpen, setImgOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showSentenceScores, setShowSentenceScores] = useState(false)

  const isUser = role === 'user'
  const showTyping = !isUser && streaming && !content?.trim()
  const showCopy = !isUser && !streaming && content?.trim()

  const pdfs =
    sources?.map((item) => (typeof item === 'string' ? { filename: item, chunks: [] } : item)) ?? []

  // Copies assistant text to clipboard.
  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-2 max-w-[680px] w-full px-4 group/msg',
        isUser ? 'ml-auto items-end' : 'mr-auto items-start'
      )}
    >
      <div
        className={cn(
          showTyping
            ? 'px-3 py-2 rounded-full w-fit'
            : 'px-4 py-3 rounded-lg max-w-full break-words overflow-hidden',
          showCopy && 'relative pb-8',
          isUser ? 'border' : 'border'
        )}
        style={
          isUser
            ? {
                background: 'var(--msg-user-bg)',
                color: 'var(--msg-user-text)',
                borderColor: 'var(--msg-user-border)',
              }
            : {
                background: 'var(--msg-ai-bg)',
                color: 'var(--msg-ai-text)',
                borderColor: 'var(--msg-ai-border)',
              }
        }
      >
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{content}</p>
        ) : showTyping ? (
          <div className="typing" aria-label="Assistant is typing" role="status">
            <span />
            <span />
            <span />
          </div>
        ) : showSentenceScores && logprobs.length > 0 ? (
          <SentenceScoredAnswer content={content} logprobs={logprobs} />
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&>*]:my-6 [&>p]:leading-relaxed">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}

        {showCopy && (
          <button
            onClick={handleCopy}
            className="absolute bottom-2 right-2 inline-flex items-center justify-center rounded p-1 opacity-70 hover:opacity-100 transition-opacity"
            style={{ color: 'var(--msg-ai-text)' }}
            title="Copy to clipboard"
            aria-label="Copy to clipboard"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        )}
      </div>

      {!isUser && !streaming && logprobs.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {typeof avgProbability === 'number' && (
            <span style={{ fontSize: '10px', color: '#6c757d' }}>
              avg confidence:{' '}
              <strong
                style={{
                  color: sentenceBorderColor(avgProbability),
                }}
              >
                {avgProbability.toFixed(1)}%
              </strong>
            </span>
          )}
          <button
            onClick={() => setShowSentenceScores((v) => !v)}
            style={{
              fontSize: '10px',
              padding: '2px 7px',
              borderRadius: '4px',
              cursor: 'pointer',
              border: '1px solid #444',
              background: showSentenceScores ? '#6366f1' : 'transparent',
              color: showSentenceScores ? '#fff' : '#aaa',
            }}
            title="Show sentence-level confidence scores"
          >
            {showSentenceScores ? 'hide confidence' : 'show confidence'}
          </button>
        </div>
      )}

      {!isUser && !streaming && (
        <div className="flex flex-col gap-2 w-full">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setImgOpen((v) => !v)}
            className="self-start gap-2 h-7 px-2 text-xs"
          >
            <Image size={12} />
            <span>
              {debugImages.length} Image{debugImages.length !== 1 ? 's' : ''} sent to LLM
            </span>
            {imgOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </Button>

          {imgOpen && (
            <div className="flex flex-col gap-2 pl-4 border-l-2 border-accent/30">
              {debugImages.length > 0 ? (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px',
                    alignItems: 'flex-start',
                  }}
                >
                  {debugImages.map((b64, i) => (
                    <img
                      key={i}
                      src={`data:image/png;base64,${b64}`}
                      style={{ maxWidth: '300px', height: 'auto', borderRadius: '4px' }}
                      alt={`Debug image ${i + 1}`}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No images found on retrieved pages.</p>
              )}
            </div>
          )}
        </div>
      )}

      {!isUser && !streaming && pdfs.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSrcOpen((v) => !v)}
            className="self-start gap-2 h-7 px-2 text-xs"
          >
            <BookOpen size={12} />
            <span>
              {pdfs.length} Document{pdfs.length > 1 ? 's' : ''}
            </span>
            {srcOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </Button>

          {srcOpen && (
            <div className="flex flex-col gap-2 pl-4 border-l-2 border-accent/30">
              {pdfs.map((item) => (
                <PdfModal
                  key={item.filename}
                  filename={item.filename}
                  chunks={item.chunks}
                  trigger={
                    <button className="group flex items-center gap-3 bg-surface2 border border-border rounded-md p-3 text-left w-full hover:border-accent/60 hover:bg-surface2/80 transition-colors cursor-pointer">
                      <FileText size={16} className="text-accent shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-accent truncate">
                          {readableTitle(item.filename)}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium text-accent border border-accent/45 bg-accent/12 group-hover:bg-accent/20 group-hover:border-accent/65 transition-colors">
                            Open PDF
                          </span>
                        </div>
                      </div>
                    </button>
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}

      {showFollowups && followups?.length > 0 && (
        <div className="followup-chips">
          <span className="followup-label">
            <CornerDownRight size={11} />
            You might also want to know
          </span>
          {followups.map((q, idx) => (
            <button
              key={idx}
              className="followup-chip"
              onClick={() => onFollowupClick?.(q)}
              title={q}
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
