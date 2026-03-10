import { useState } from 'react'
import { FileText, RefreshCw, Database, Cpu, Server, ChevronDown, ChevronRight } from 'lucide-react'
import { api } from '../../api/client'

export default function Sidebar({ status, onStatusRefresh }) {
  const [ingesting, setIngesting] = useState(false)
  const [ingestMsg, setIngestMsg] = useState(null)
  const [docsOpen, setDocsOpen] = useState(true)

  async function handleIngest() {
    setIngesting(true)
    setIngestMsg(null)
    try {
      const res = await api.ingest()
      setIngestMsg({ ok: true, text: res.message })
      onStatusRefresh()
    } catch (e) {
      setIngestMsg({ ok: false, text: e.message })
    } finally {
      setIngesting(false)
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-logo">⬡</span>
        <span className="sidebar-title">RAG Control</span>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <FileText size={14} />
          <span className="stat-value">{status?.pdf_count ?? '—'}</span>
          <span className="stat-label">PDFs</span>
        </div>
        <div className="stat-card">
          <Database size={14} />
          <span className="stat-value">{status?.chunk_count ?? '—'}</span>
          <span className="stat-label">Chunks</span>
        </div>
      </div>

      {/* Ingest button */}
      <button
        className={`ingest-btn ${ingesting ? 'loading' : ''}`}
        onClick={handleIngest}
        disabled={ingesting}
      >
        <RefreshCw size={14} className={ingesting ? 'spin' : ''} />
        {ingesting ? 'Indexing…' : 'Index / Re-index'}
      </button>

      {ingestMsg && (
        <div className={`ingest-msg ${ingestMsg.ok ? 'ok' : 'err'}`}>{ingestMsg.text}</div>
      )}

      {/* Document list */}
      {status?.documents?.length > 0 && (
        <div className="doc-list">
          <button className="doc-list-toggle" onClick={() => setDocsOpen((v) => !v)}>
            {docsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            <span>Loaded documents</span>
          </button>
          {docsOpen && (
            <ul>
              {status.documents.map((d) => (
                <li key={d}>
                  <FileText size={11} />
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Config info */}
      <div className="config-info">
        <div className="config-row">
          <Cpu size={11} />
          <span>{status?.llm_model ?? '—'}</span>
        </div>
        <div className="config-row">
          <Server size={11} />
          <span className="truncate">{status?.ollama_host ?? '—'}</span>
        </div>
      </div>

      {/* How-to */}
      <div className="howto">
        <p className="howto-title">Adding documents</p>
        <ol>
          <li>
            Copy PDFs into <code>backend/data/docs/</code>
          </li>
          <li>
            Click <em>Index / Re-index</em>
          </li>
          <li>Start asking questions</li>
        </ol>
      </div>
    </aside>
  )
}
