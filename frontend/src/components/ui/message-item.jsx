import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from './button'
import { cn } from '@/lib/utils'

export function MessageItem({ role, content, sources }) {
  const [srcOpen, setSrcOpen] = useState(false)
  const isUser = role === 'user'

  return (
    <div className={cn(
      'flex flex-col gap-2 max-w-[680px] w-full px-4',
      isUser ? 'ml-auto items-end' : 'mr-auto items-start'
    )}>
      <div className={cn(
        'px-4 py-3 rounded-lg max-w-full break-words overflow-hidden',
        isUser
          ? 'border'
          : 'border'
      )}
        style={isUser
          ? { background: 'var(--msg-user-bg)', color: 'var(--msg-user-text)', borderColor: 'var(--msg-user-border)' }
          : { background: 'var(--msg-ai-bg)',   color: 'var(--msg-ai-text)',   borderColor: 'var(--msg-ai-border)'  }
        }
      >
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{content}</p>
        ) : (
          <div className="prose prose-sm prose-invert max-w-none [&>*]:my-2 [&>p]:leading-relaxed">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && sources?.length > 0 && (
        <div className="flex flex-col gap-2 w-full">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSrcOpen(v => !v)}
            className="self-start gap-2 h-7 px-2 text-xs"
          >
            <BookOpen size={12} />
            <span>{sources.length} source{sources.length > 1 ? 's' : ''}</span>
            {srcOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </Button>

          {srcOpen && (
            <div className="flex flex-col gap-2 pl-4 border-l-2 border-accent/30">
              {sources.map((src, i) => (
                <div key={i} className="bg-surface2 border border-border rounded-md p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-accent truncate">{src.file}</span>
                    <span className="text-xs text-text-muted ml-2">{(src.score * 100).toFixed(0)}%</span>
                  </div>
                  <p className="text-xs text-text-muted leading-relaxed">
                    {src.text.slice(0, 300)}{src.text.length > 300 ? '…' : ''}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
