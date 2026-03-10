import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { Button } from './button'
import { PdfModal, readableTitle } from './PdfModal'
import { cn } from '@/lib/utils'

function deduplicateSources(sources) {
  const map = {}
  for (const src of sources) {
    const key = src.file_name
    if (!map[key] || src.score > map[key].score) {
      map[key] = src
    }
  }
  return Object.values(map).sort((a, b) => b.score - a.score)
}

export function MessageItem({ role, content, sources, streaming = false }) {
  const [srcOpen, setSrcOpen] = useState(false)
  const isUser = role === 'user'
  const showTyping = !isUser && streaming && !content?.trim()
  const uniquePdfs = sources?.length > 0 ? deduplicateSources(sources).slice(0, 3) : []

  return (
    <div
      className={cn(
        'flex flex-col gap-2 max-w-[680px] w-full px-4',
        isUser ? 'ml-auto items-end' : 'mr-auto items-start'
      )}
    >
      <div
        className={cn(
          showTyping
            ? 'px-3 py-2 rounded-full w-fit'
            : 'px-4 py-3 rounded-lg max-w-full break-words overflow-hidden',
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
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&>*]:my-2 [&>p]:leading-relaxed">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && !streaming && uniquePdfs.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSrcOpen((v) => !v)}
            className="self-start gap-2 h-7 px-2 text-xs"
          >
            <BookOpen size={12} />
            <span>
              {uniquePdfs.length} Dokument{uniquePdfs.length > 1 ? 'e' : ''}
            </span>
            {srcOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </Button>

          {srcOpen && (
            <div className="flex flex-col gap-2 pl-4 border-l-2 border-accent/30">
              {uniquePdfs.map((src, index) => (
                <PdfModal
                  key={src.file_name}
                  filename={src.file_name}
                  trigger={
                    <button className="flex items-center gap-3 bg-surface2 border border-border rounded-md p-3 text-left w-full hover:border-accent/50 hover:bg-surface2/80 transition-colors cursor-pointer">
                      <FileText size={16} className="text-accent shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-accent truncate">
                          {readableTitle(src.file_name)}
                        </p>
                        <p className="text-xs text-text-muted mt-0.5">PDF öffnen</p>
                      </div>
                      <span className="shrink-0 text-[10px] font-mono bg-accent/10 text-accent border border-accent/20 rounded px-1.5 py-0.5">
                        #{index + 1}
                      </span>
                    </button>
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
