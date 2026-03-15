import { Dialog } from 'radix-ui'
import { X } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

export function readableTitle(filename) {
  return filename
    .replace(/\.pdf$/i, '')
    .replace(/_[0-9a-f]{5,}$/, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function PdfModal({ filename, trigger, chunks = [] }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      setPdfUrl(null)
      return
    }

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
            'fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2',
            'w-[90vw] h-[90vh] max-w-5xl',
            'bg-surface border border-border rounded-lg shadow-xl',
            'flex flex-col',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95'
          )}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <Dialog.Title className="text-sm font-medium text-text truncate">
              {readableTitle(filename)}
            </Dialog.Title>
            <Dialog.Close className="rounded p-1 hover:bg-surface2 transition-colors text-text-muted hover:text-text">
              <X size={16} />
            </Dialog.Close>
          </div>
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              Loading PDF...
            </div>
          ) : pdfUrl ? (
            <iframe src={pdfUrl} className="flex-1 w-full rounded-b-lg" title={filename} />
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
