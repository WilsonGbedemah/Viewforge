import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function Modal({ title, onClose, children, width = 'max-w-lg' }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 animate-fade-in p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className={`bg-forge-surface border border-forge-border rounded-lg w-full ${width} animate-slide-up`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-forge-border">
          <h2 className="font-semibold text-forge-text">{title}</h2>
          <button onClick={onClose} className="text-forge-dim hover:text-forge-text transition-colors">
            <X size={16} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
