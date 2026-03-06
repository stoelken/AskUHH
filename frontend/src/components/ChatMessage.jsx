import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ChevronDown, ChevronUp, BookOpen } from 'lucide-react'

export default function ChatMessage({ role, content, sources }) {
  const [srcOpen, setSrcOpen] = useState(false)
  const isUser = role === 'user'

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-bubble">
        {isUser ? (
          <p>{content}</p>
        ) : (
          <ReactMarkdown>{content}</ReactMarkdown>
        )}
      </div>

      {!isUser && sources?.length > 0 && (
        <div className="sources">
          <button className="sources-toggle" onClick={() => setSrcOpen(v => !v)}>
            <BookOpen size={12} />
            <span>{sources.length} source{sources.length > 1 ? 's' : ''}</span>
            {srcOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>

          {srcOpen && (
            <div className="sources-list">
              {sources.map((src, i) => (
                <div key={i} className="source-card">
                  <div className="source-header">
                    <span className="source-file">{src.file}</span>
                    <span className="source-score">{(src.score * 100).toFixed(0)}%</span>
                  </div>
                  <p className="source-text">{src.text.slice(0, 300)}{src.text.length > 300 ? '…' : ''}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
