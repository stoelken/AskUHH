import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { Button } from './button'
import { PdfModal, readableTitle } from './PdfModal'
import { cn } from '@/lib/utils'

export function MessageItem({ role, content, sources, streaming = false, debugImages = [] }) {
  const [srcOpen, setSrcOpen] = useState(false)
  const isUser = role === 'user'
  const showTyping = !isUser && streaming && !content?.trim()

  const pdfs =
    sources?.map((item) => {
      if (typeof item === 'string') {
        return { filename: item, chunks: [] }
      } else {
        return item
      }
    }) ?? []

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
          <div className="prose prose-sm prose-invert max-w-none [&>*]:my-6 [&>p]:leading-relaxed">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && !streaming && (
        <div
          style={{
            marginTop: '8px',
            padding: '6px 10px',
            background: '#22252b',
            borderRadius: '6px',
            fontSize: '11px',
            color: '#6c757d',
          }}
        >
          {debugImages.length > 0 ? (
            <>
              <p style={{ marginBottom: '6px' }}>{debugImages.length} image(s) sent to LLM</p>
              <div
                style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'flex-start' }}
              >
                {debugImages.map((b64, i) => (
                  <img
                    key={i}
                    src={`data:image/png;base64,${b64}`}
                    style={{
                      maxWidth: '300px',
                      height: 'auto',
                    }}
                    alt={`Debug image ${i + 1}`}
                  />
                ))}
              </div>
            </>
          ) : (
            <p>no images sent to LLM</p>
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
                        <span className="inline-flex items-center mt-1 rounded px-2 py-0.5 text-[11px] font-medium text-accent border border-accent/45 bg-accent/12 group-hover:bg-accent/20 group-hover:border-accent/65 transition-colors">
                          Open PDF
                        </span>
                      </div>
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
