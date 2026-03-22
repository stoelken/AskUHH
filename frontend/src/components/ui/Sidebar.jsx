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
    <aside
      className={[
        'z-20 flex h-full flex-col gap-4 overflow-x-hidden overflow-y-auto bg-[#22252b] pt-14 transition-all duration-[220ms] ease-in-out',
        isOpen
          ? 'w-[260px] border-r border-[#363b44] px-4 pb-5 opacity-100 pointer-events-auto'
          : 'w-0 border-r-0 px-0 pb-5 opacity-0 pointer-events-none',
      ].join(' ')}
    >
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col items-center gap-[3px] rounded-[6px] border border-[#363b44] bg-[#2a2e36] px-2 py-[10px] text-[#9ba0aa]">
          <FileText size={14} className="text-[#9aa3af]" />
          <span className="text-[20px] font-medium leading-none text-[#d5d9e0]">
            {status?.pdf_count ?? '—'}
          </span>
          <span className="text-[10px] uppercase tracking-[0.08em] text-[#6e7480]">PDFs</span>
        </div>
        <div className="flex flex-col items-center gap-[3px] rounded-[6px] border border-[#363b44] bg-[#2a2e36] px-2 py-[10px] text-[#9ba0aa]">
          <Database size={14} className="text-[#9aa3af]" />
          <span className="text-[20px] font-medium leading-none text-[#d5d9e0]">
            {status?.chunk_count ?? '—'}
          </span>
          <span className="text-[10px] uppercase tracking-[0.08em] text-[#6e7480]">Chunks</span>
        </div>
      </div>

      <button
        className={[
          'flex w-full items-center justify-center gap-[7px] rounded-[6px] border px-3 py-[9px] text-xs transition',
          ingesting
            ? 'border-[#9aa3af] text-[#9ba0aa]'
            : 'border-[#9aa3af] text-[#d5d9e0] hover:border-[#d5d9e0] hover:bg-[rgba(213,217,224,0.12)]',
        ].join(' ')}
        onClick={handleIngest}
        disabled={ingesting || !canIngest}
        title={canIngest ? 'Index current documents' : 'No new documents to index'}
      >
        <RefreshCw size={14} className={ingesting ? 'animate-spin' : ''} />
        {ingesting ? 'Indexing…' : 'Index / Re-index'}
      </button>

      {ingestMsg && (
        <div
          className={[
            'rounded-[6px] border px-[10px] py-2 text-[11.5px] leading-[1.4]',
            ingestMsg.ok
              ? 'border-[rgba(90,158,124,0.3)] bg-[rgba(90,158,124,0.12)] text-[#5a9e7c]'
              : 'border-[rgba(192,80,77,0.3)] bg-[rgba(192,80,77,0.12)] text-[#e06666]',
          ].join(' ')}
        >
          {ingestMsg.text}
        </div>
      )}

      <div
        className={[
          'flex flex-col gap-[7px] rounded-[6px] border border-dashed p-[10px] transition',
          dragActive
            ? 'border-[#d5d9e0] bg-[rgba(213,217,224,0.1)]'
            : 'border-[#9aa3af] bg-[rgba(213,217,224,0.04)]',
          uploading ? 'opacity-70' : 'opacity-100',
        ].join(' ')}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <p className="text-[11.5px] font-medium text-[#d5d9e0]">Drop PDFs here</p>
        <p className="text-[10.5px] leading-[1.4] text-[#6e7480]">
          You can upload multiple files at once.
        </p>
        <label className="cursor-pointer rounded-[5px] border border-[#363b44] bg-[#2a2e36] px-2 py-[7px] text-center text-[11px] text-[#9ba0aa] transition hover:border-[#9aa3af] hover:text-[#ede9e1]">
          {uploading ? 'Uploading…' : 'Browse files'}
          <input
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={handleFileInputChange}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>

      {uploadMsg && (
        <div
          className={[
            'rounded-[6px] border px-[10px] py-2 text-[11.5px] leading-[1.4]',
            uploadMsg.ok
              ? 'border-[rgba(90,158,124,0.3)] bg-[rgba(90,158,124,0.12)] text-[#5a9e7c]'
              : 'border-[rgba(192,80,77,0.3)] bg-[rgba(192,80,77,0.12)] text-[#e06666]',
          ].join(' ')}
        >
          {uploadMsg.text}
        </div>
      )}

      {status?.documents?.length > 0 && (
        <div className="text-xs">
          <button
            className="flex w-full items-center gap-[5px] py-1 text-left text-[11px] uppercase tracking-[0.07em] text-[#9ba0aa] hover:text-[#ede9e1]"
            onClick={() => setDocsOpen((v) => !v)}
          >
            {docsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            <span>Loaded documents</span>
          </button>
          {docsOpen && (
            <ul className="mt-[6px] flex list-none flex-col gap-1">
              {status.documents.map((d) => (
                <li
                  key={d}
                  className="group flex items-center gap-[6px] rounded-[4px] bg-[#2a2e36] px-2 py-1 text-[11px] text-[#9ba0aa]"
                >
                  <FileText size={11} className="mt-[2px] shrink-0 text-[#6e7480]" />
                  <span className="min-w-0 flex-1 truncate">{d}</span>
                  <button
                    type="button"
                    className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-[4px] bg-transparent text-[#6e7480] opacity-0 transition group-hover:opacity-100 hover:bg-[rgba(224,102,102,0.12)] hover:text-[#e06666] focus-visible:opacity-100"
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
