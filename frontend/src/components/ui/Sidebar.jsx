import { useState } from 'react'
import { FileText, RefreshCw, Database, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { api } from '../../api/client'

// Main sidebar UI: shows stats, lets us upload PDFs, index them, and manage loaded docs.
export default function Sidebar({ status, onStatusRefresh, isOpen = false }) {
  const [ingesting, setIngesting] = useState(false)
  const [ingestMsg, setIngestMsg] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [deletingDoc, setDeletingDoc] = useState(null)
  const [docsOpen, setDocsOpen] = useState(true)
  const canIngest = Boolean(status?.needs_index)

  // Runs indexing when needed, then refreshes status so counts/messages stay updated.
  async function handleIngest() {
    if (!canIngest) return
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

  // Deletes one document by filename and refreshes status so the list updates right away.
  async function handleDeleteDocument(filename) {
    if (!filename || deletingDoc) return
    setDeletingDoc(filename)
    setUploadMsg(null)
    try {
      const res = await api.deleteDocument(filename)
      setUploadMsg({
        ok: true,
        text: `${res.message} Click Index / Re-index to refresh embeddings.`,
      })
      onStatusRefresh()
    } catch (e) {
      setUploadMsg({ ok: false, text: e.message })
    } finally {
      setDeletingDoc(null)
    }
  }

  // Keeps only PDF files from any dropped/selected file list.
  function filterPdfFiles(files) {
    return Array.from(files).filter(
      (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    )
  }

  // Uploads selected/dropped PDFs, handles success/error messages, and refreshes status.
  async function handleUploadFiles(fileList) {
    const pdfFiles = filterPdfFiles(fileList)
    if (pdfFiles.length === 0) {
      setUploadMsg({ ok: false, text: 'Please drop/select at least one PDF file.' })
      return
    }

    setUploading(true)
    setUploadMsg(null)
    try {
      const res = await api.uploadDocuments(pdfFiles)
      setUploadMsg({ ok: true, text: res.message })
      onStatusRefresh()
    } catch (e) {
      setUploadMsg({ ok: false, text: e.message })
    } finally {
      setUploading(false)
      setDragActive(false)
    }
  }

  // Enables dropzone highlight while dragging files over it.
  function handleDragOver(e) {
    e.preventDefault()
    setDragActive(true)
  }

  // Activates dropzone as soon as files enter, so dropping multiple feels reliable.
  function handleDragEnter(e) {
    e.preventDefault()
    setDragActive(true)
  }

  // Removes dropzone highlight when files leave the area.
  function handleDragLeave(e) {
    e.preventDefault()
    setDragActive(false)
  }

  // Normalizes dropped data so we reliably get all files from the browser drop event.
  function getDroppedFiles(e) {
    const itemFiles = Array.from(e.dataTransfer?.items || [])
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter(Boolean)

    if (itemFiles.length > 0) return itemFiles
    return Array.from(e.dataTransfer?.files || [])
  }

  // Handles dropped files and passes them to the upload flow.
  function handleDrop(e) {
    e.preventDefault()
    setDragActive(false)
    if (uploading) return
    const files = getDroppedFiles(e)
    if (!files.length) return
    handleUploadFiles(files)
  }

  // Handles file picker selection, uploads files, then resets the input value.
  function handleFileInputChange(e) {
    if (uploading) return
    const files = e.target.files
    if (!files?.length) return
    handleUploadFiles(files)
    e.target.value = ''
  }

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar--open' : ''}`}>
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

      <button
        className={`ingest-btn ${ingesting ? 'loading' : ''}`}
        onClick={handleIngest}
        disabled={ingesting || !canIngest}
        title={canIngest ? 'Index current documents' : 'No new documents to index'}
      >
        <RefreshCw size={14} className={ingesting ? 'spin' : ''} />
        {ingesting ? 'Indexing…' : 'Index / Re-index'}
      </button>

      {ingestMsg && (
        <div className={`ingest-msg ${ingestMsg.ok ? 'ok' : 'err'}`}>{ingestMsg.text}</div>
      )}

      <div
        className={`dropzone ${dragActive ? 'dropzone--active' : ''} ${uploading ? 'dropzone--disabled' : ''}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <p className="dropzone-title">Drop PDFs here</p>
        <p className="dropzone-subtitle">You can upload multiple files at once.</p>
        <label className="dropzone-browse">
          {uploading ? 'Uploading…' : 'Browse files'}
          <input
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={handleFileInputChange}
            disabled={uploading}
          />
        </label>
      </div>

      {uploadMsg && (
        <div className={`ingest-msg ${uploadMsg.ok ? 'ok' : 'err'}`}>{uploadMsg.text}</div>
      )}

      {status?.documents?.length > 0 && (
        <div className="doc-list">
          <button className="doc-list-toggle" onClick={() => setDocsOpen((v) => !v)}>
            {docsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            <span>Loaded documents</span>
          </button>
          {docsOpen && (
            <ul>
              {status.documents.map((d) => (
                <li key={d} className="doc-list-item">
                  <FileText size={11} />
                  <span className="doc-list-name">{d}</span>
                  <button
                    type="button"
                    className="doc-delete-btn"
                    onClick={() => handleDeleteDocument(d)}
                    disabled={deletingDoc === d}
                    title={`Delete ${d}`}
                    aria-label={`Delete ${d}`}
                  >
                    <Trash2 size={11} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </aside>
  )
}
