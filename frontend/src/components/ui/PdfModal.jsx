import { Dialog } from 'radix-ui'
import { X } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

// Cleans PDF filenames to a nicer title for showing in the modal header.
export function readableTitle(filename) {
  return filename
    .replace(/\.pdf$/i, '')
    .replace(/_[0-9a-f]{5,}$/, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// PDF viewer modal that can show the original file or a highlighted preview.
export function PdfModal({ filename, trigger, chunks = [] }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      setPdfUrl(null)
      return
    }

    // Loads highlighted PDF when chunk matches exist, otherwise opens original file.
    const fetchPdf = async () => {
      setIsLoading(true)
      try {
        if (chunks?.length > 0) {
          const response = await fetch('/api/pdf/highlight', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, chunks }),
          })
          if (!response.ok) throw new Error(`HTTP ${response.status}`)
          const blob = await response.blob()
          const url = URL.createObjectURL(blob)
          setPdfUrl(url)
        } else {
          setPdfUrl(`/api/pdf/${encodeURIComponent(filename)}`)
        }
      } catch (error) {
        console.error('Failed to fetch PDF:', error)
        setPdfUrl(`/api/pdf/${encodeURIComponent(filename)}`)
      } finally {
        setIsLoading(false)
      }
    }

    fetchPdf()

    return () => {
      if (pdfUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(pdfUrl)
      }
    }
  }, [isOpen, filename, chunks])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 flex h-[90vh] w-[90vw] max-w-5xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-lg border border-[#363b44] bg-[#22252b] shadow-[0_20px_50px_rgba(0,0,0,0.35)]',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95'
          )}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-[#363b44] px-4 py-3">
            <Dialog.Title className="truncate text-sm font-medium text-[#ede9e1]">
              {readableTitle(filename)}
            </Dialog.Title>
            <Dialog.Close className="rounded p-1 text-[#9ba0aa] transition hover:bg-[#2a2e36] hover:text-[#ede9e1]">
              <X size={16} />
            </Dialog.Close>
          </div>
          {isLoading ? (
            <div className="flex flex-1 items-center justify-center text-[#9ba0aa]">
              Loading PDF...
            </div>
          ) : pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="h-full w-full flex-1 rounded-b-lg border-0"
              title={filename}
            />
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
