import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { BookOpen, ChevronDown, ChevronUp, FileText } from 'lucide-react'
import { Button } from './button'
import { PdfModal, readableTitle } from './PdfModal'

export function MessageItem({ role, content, sources, streaming = false }) {
  const [srcOpen, setSrcOpen] = useState(false)
  const isUser = role === 'user'
  const showTyping = !isUser && streaming && !content?.trim()
  const pdfs = sources ?? []

  return (
    <div
      className="msg-animate"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        maxWidth: '700px',
        width: '100%',
        padding: '0 4px',
        ...(isUser
          ? { marginLeft: 'auto', alignItems: 'flex-end' }
          : { marginRight: 'auto', alignItems: 'flex-start' }),
      }}
    >
      {/* Bubble */}
      {showTyping ? (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: '9999px',
            width: 'fit-content',
            background: 'var(--surface)',
            border: '1px solid var(--msg-ai-border)',
            boxShadow: 'var(--shadow-xs)',
          }}
        >
          <div className="typing" aria-label="Assistant is typing" role="status">
            <span />
            <span />
            <span />
          </div>
        </div>
      ) : (
        <div
          style={
            isUser
              ? {
                  background: 'var(--msg-user-bg)',
                  color: 'var(--msg-user-text)',
                  borderRadius: '22px 22px 6px 22px',
                  padding: '14px 20px',
                  maxWidth: '100%',
                  overflowWrap: 'break-word',
                  wordBreak: 'break-word',
                  overflow: 'hidden',
                  boxShadow: 'var(--shadow-sm)',
                }
              : {
                  background: 'var(--msg-ai-bg)',
                  color: 'var(--msg-ai-text)',
                  border: '1px solid var(--msg-ai-border)',
                  borderRadius: '22px 22px 22px 6px',
                  padding: '14px 20px',
                  maxWidth: '100%',
                  overflowWrap: 'break-word',
                  wordBreak: 'break-word',
                  overflow: 'hidden',
                  boxShadow: 'var(--shadow)',
                }
          }
        >
          {isUser ? (
            <p style={{ fontSize: '14px', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
              {content}
            </p>
          ) : (
            <div className="prose prose-sm max-w-none [&>*]:my-6 [&>p]:leading-relaxed">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Sources — PdfModal logic unchanged */}
      {!isUser && !streaming && pdfs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSrcOpen((v) => !v)}
            className="sources-btn self-start gap-2"
          >
            <BookOpen size={12} />
            <span>
              {pdfs.length} Dokument{pdfs.length > 1 ? 'e' : ''}
            </span>
            {srcOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </Button>

          {srcOpen && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                paddingLeft: '16px',
                borderLeft: '2px solid var(--accent-soft)',
                borderRadius: '0 0 0 8px',
              }}
            >
              {pdfs.map((filename) => (
                <PdfModal
                  key={filename}
                  filename={filename}
                  trigger={
                    <button className="source-card"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        textAlign: 'left',
                        width: '100%',
                        cursor: 'pointer',
                      }}
                    >
                      <FileText size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p className="source-file" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {readableTitle(filename)}
                        </p>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>PDF öffnen</p>
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