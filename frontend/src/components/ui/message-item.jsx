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

function sentenceConfidenceLevel(avgProb) {
  if (avgProb === null) return 'none'
  if (avgProb >= 97) return 'high'
  if (avgProb >= 93) return 'medium'
  if (avgProb >= 88) return 'low'
  return 'very-low'
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
        const confidenceLevel = sentenceConfidenceLevel(s.avgProb)
        const tooltip =
          s.avgProb !== null
            ? `avg confidence: ${s.avgProb}% | min: ${s.minProb}%`
            : 'no confidence data'

        const borderClass =
          confidenceLevel === 'high'
            ? 'border-l-emerald-400/70'
            : confidenceLevel === 'medium'
              ? 'border-l-amber-400/70'
              : confidenceLevel === 'low'
                ? 'border-l-orange-400/80'
                : confidenceLevel === 'very-low'
                  ? 'border-l-rose-400/90'
                  : 'border-l-transparent'

        return (
          <div
            key={i}
            title={tooltip}
            className={cn('cursor-help border-l-[3px] pl-2', borderClass)}
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

      <div className="mt-1.5 flex flex-wrap gap-2.5 text-[10px] text-[#6c757d]">
        <span>
          <span className="text-emerald-400">▌</span> ≥97%
        </span>
        <span>
          <span className="text-amber-400">▌</span> 93–97%
        </span>
        <span>
          <span className="text-orange-400">▌</span> 88–93%
        </span>
        <span>
          <span className="text-rose-400">▌</span> &lt;88%
        </span>
        <span className="opacity-50">hover for details</span>
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
        'group/msg flex w-full max-w-[680px] flex-col gap-2 px-4',
        isUser ? 'ml-auto items-end' : 'mr-auto items-start'
      )}
    >
      <div
        className={cn(
          showTyping
            ? 'w-fit rounded-full px-3 py-2'
            : 'max-w-full overflow-hidden break-words rounded-[14px] border px-4 py-3',
          showCopy && 'relative pb-8',
          isUser
            ? 'border-[#2d5490] bg-[#1c3658] text-[#d6e8ff]'
            : 'border-[#2f4c50] bg-[#21373a] text-[#e8e5f2]'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed break-words">{content}</p>
        ) : showTyping ? (
          <div
            className="flex items-center gap-1 px-px"
            aria-label="Assistant is typing"
            role="status"
          >
            <span className="h-[5px] w-[5px] animate-bounce rounded-full bg-[#9ba0aa] [animation-delay:0ms]" />
            <span className="h-[5px] w-[5px] animate-bounce rounded-full bg-[#9ba0aa] [animation-delay:120ms]" />
            <span className="h-[5px] w-[5px] animate-bounce rounded-full bg-[#9ba0aa] [animation-delay:240ms]" />
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
            className="absolute bottom-2 right-2 rounded p-1 text-[#e8e5f2] opacity-70 transition hover:opacity-100"
            title="Copy to clipboard"
            aria-label="Copy to clipboard"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        )}
      </div>

      {!isUser && !streaming && logprobs.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {typeof avgProbability === 'number' && (
            <span className="text-[10px] text-[#6c757d]">
              avg confidence:{' '}
              <strong
                className={cn(
                  sentenceConfidenceLevel(avgProbability) === 'high' && 'text-emerald-400',
                  sentenceConfidenceLevel(avgProbability) === 'medium' && 'text-amber-400',
                  sentenceConfidenceLevel(avgProbability) === 'low' && 'text-orange-400',
                  sentenceConfidenceLevel(avgProbability) === 'very-low' && 'text-rose-400'
                )}
              >
                {avgProbability.toFixed(1)}%
              </strong>
            </span>
          )}
          <button
            onClick={() => setShowSentenceScores((v) => !v)}
            className={cn(
              'rounded-[4px] border border-[#444] px-[7px] py-[2px] text-[10px] text-[#aaa] transition',
              showSentenceScores
                ? 'border-[#6366f1] bg-[#6366f1] text-white'
                : 'hover:border-[#666] hover:bg-transparent'
            )}
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
            <div className="flex flex-col gap-2 border-l-2 border-[rgba(213,217,224,0.3)] pl-4">
              {debugImages.length > 0 ? (
                <div className="flex flex-wrap items-start gap-2">
                  {debugImages.map((b64, i) => (
                    <img
                      key={i}
                      src={`data:image/png;base64,${b64}`}
                      className="h-auto max-w-[300px] rounded-[12px]"
                      alt={`Debug image ${i + 1}`}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[#9ba0aa]">No images found on retrieved pages.</p>
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
            <div className="flex flex-col gap-2 border-l-2 border-[rgba(213,217,224,0.3)] pl-4">
              {pdfs.map((item) => (
                <PdfModal
                  key={item.filename}
                  filename={item.filename}
                  chunks={item.chunks}
                  trigger={
                    <button className="group flex w-full cursor-pointer items-center gap-3 rounded-[12px] border border-[#363b44] bg-[#2a2e36] p-3 text-left transition-colors hover:border-[rgba(213,217,224,0.6)] hover:bg-[rgba(42,46,54,0.8)]">
                      <FileText size={16} className="shrink-0 text-[#d5d9e0]" />
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-xs font-medium text-[#d5d9e0]">
                          {readableTitle(item.filename)}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="inline-flex items-center rounded-[8px] border border-[rgba(213,217,224,0.45)] bg-[rgba(213,217,224,0.12)] px-2 py-0.5 text-[11px] font-medium text-[#d5d9e0] transition-colors group-hover:border-[rgba(213,217,224,0.65)] group-hover:bg-[rgba(213,217,224,0.2)]">
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
        <div className="mt-[2px] flex flex-wrap items-center gap-[6px]">
          <span className="mr-[2px] inline-flex select-none items-center gap-1 text-[10px] uppercase tracking-[0.06em] text-[#6e7480]">
            <CornerDownRight size={11} />
            You might also want to know
          </span>
          {followups.map((q, idx) => (
            <button
              key={idx}
              className="inline-flex rounded-full border border-[#363b44] bg-[#2a2e36] px-3 py-[5px] text-left text-[11.5px] leading-[1.4] text-[#d5d9e0] transition hover:border-[#9aa3af] hover:bg-[rgba(213,217,224,0.08)] hover:text-[#ede9e1]"
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
