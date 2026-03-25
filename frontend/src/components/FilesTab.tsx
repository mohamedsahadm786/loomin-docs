import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import { Upload, Trash2, Eye, X, FileText, CheckCircle } from 'lucide-react'
import { uploadFile, deleteFile, getFileContent } from '../api/client'

interface FileItem {
  filename: string
  size_bytes: number
  path: string
}

interface Props {
  files: FileItem[]
  onFilesChanged: () => void
  onImportToEditor: (content: string) => void
}


interface ViewerData {
  filename: string
  content: string
  character_count: number
  word_count: number
}

const STEPS = [
  'Uploading file…',
  'Extracting text…',
  'Creating embeddings…',
  'Indexing into FAISS…',
]

const ALLOWED = ['.pdf', '.md', '.txt', '.docx']
const CYAN_BORDER = '1.5px solid rgba(0,212,255,0.3)'
const CYAN_BG = 'rgba(0,212,255,0.06)'

export default function FilesTab({ files, onFilesChanged, onImportToEditor }: Props) {
  const [stepIndex, setStepIndex] = useState(-1)
  const [doneMsg, setDoneMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [viewer, setViewer] = useState<ViewerData | null>(null)
  const [viewerLoading, setViewerLoading] = useState(false)

  const runSteps = async (file: File) => {
    setError(null)
    setDoneMsg(null)
    for (let i = 0; i < STEPS.length; i++) {
      setStepIndex(i)
      if (i < STEPS.length - 1) await new Promise(r => setTimeout(r, 800))
    }
    try {
      const r = await uploadFile(file)
      setDoneMsg(`Done — ${r.data.chunks_indexed} chunks indexed ✓`)
      onFilesChanged()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Upload failed')
    }
    setStepIndex(-1)
  }

  const onDrop = useCallback(async (accepted: File[], rejected: any[]) => {
    if (rejected.length > 0) {
      setError(`Only ${ALLOWED.join(', ')} files are permitted. "${rejected[0].file.name}" was rejected.`)
      return
    }
    if (accepted.length === 0) return
    const file = accepted[0]
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED.includes(ext)) {
      setError(`Only ${ALLOWED.join(', ')} files are permitted. "${file.name}" was rejected.`)
      return
    }
    await runSteps(file)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: false,
  })

  const handleDelete = async (filename: string) => {
    try {
      await deleteFile(filename)
      onFilesChanged()
    } catch { }
  }

  const handleView = async (filename: string) => {
    setViewerLoading(true)
    try {
      const r = await getFileContent(filename)
      setViewer(r.data)
    } catch {
      setError('Could not load file content.')
    }
    setViewerLoading(false)
  }

  const isUploading = stepIndex >= 0

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* Drop zone */}
        <div {...getRootProps()}
          className="rounded-2xl p-7 text-center cursor-pointer transition-all duration-300"
          style={{
            border: isDragActive ? '2px solid #00d4ff' : '2px dashed rgba(0,212,255,0.25)',
            background: isDragActive ? 'rgba(0,212,255,0.08)' : CYAN_BG,
            boxShadow: isDragActive ? '0 0 30px rgba(0,212,255,0.12)' : 'none',
          }}>
          <input {...getInputProps()} />
          <motion.div animate={isDragActive ? { scale: 1.3, rotate: 12 } : { scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 280 }}>
            <Upload size={26} className="mx-auto mb-3"
              style={{ color: isDragActive ? '#00d4ff' : 'rgba(0,212,255,0.45)' }} />
          </motion.div>
          <p className="text-sm font-mono font-bold text-white mb-1">
            {isDragActive ? 'RELEASE TO INDEX' : 'DRAG & DROP FILES'}
          </p>
          <p className="text-xs text-slate-500 font-mono">or click to browse</p>
          <div className="flex items-center justify-center gap-2 mt-3">
            {ALLOWED.map(ext => (
              <span key={ext} className="px-2 py-0.5 text-xs font-mono font-bold rounded"
                style={{ border: CYAN_BORDER, color: '#00d4ff', background: 'rgba(0,212,255,0.08)' }}>
                {ext.toUpperCase()}
              </span>
            ))}
          </div>
        </div>

        {/* Upload progress steps */}
        <AnimatePresence>
          {isUploading && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="rounded-xl p-4 space-y-2"
              style={{ border: CYAN_BORDER, background: 'rgba(0,212,255,0.04)' }}>
              {STEPS.map((step, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                    {i < stepIndex
                      ? <CheckCircle size={14} className="text-cyan-400" />
                      : i === stepIndex
                        ? <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                          className="w-3.5 h-3.5 rounded-full border-2 border-cyan-400 border-t-transparent" />
                        : <div className="w-3 h-3 rounded-full" style={{ border: '1.5px solid rgba(0,212,255,0.2)' }} />
                    }
                  </div>
                  <span className={`text-xs font-mono ${i === stepIndex ? 'text-cyan-300' : i < stepIndex ? 'text-slate-500' : 'text-slate-700'}`}>
                    {step}
                  </span>
                </div>
              ))}
            </motion.div>
          )}
          {doneMsg && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-mono font-bold"
              style={{ border: '1.5px solid rgba(34,197,94,0.35)', background: 'rgba(34,197,94,0.08)', color: '#22c55e' }}>
              <CheckCircle size={13} /> {doneMsg}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex items-center justify-between gap-2 px-4 py-2.5 rounded-xl text-xs font-mono"
              style={{ border: '1.5px solid rgba(239,68,68,0.35)', background: 'rgba(239,68,68,0.08)', color: '#ef4444' }}>
              <span>{error}</span>
              <button onClick={() => setError(null)}><X size={12} /></button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* File list */}
        {files.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <p className="text-xs font-mono font-bold text-slate-500">INDEXED FILES ({files.length})</p>
              <span className="px-2 py-0.5 text-xs font-mono font-bold rounded-full"
                style={{ border: '1px solid rgba(34,197,94,0.3)', color: '#22c55e', background: 'rgba(34,197,94,0.08)' }}>
                RAG ACTIVE
              </span>
            </div>
            {files.map(f => (
              <motion.div key={f.filename} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-3 p-3 rounded-xl group transition-all"
                style={{ border: '1.5px solid rgba(0,212,255,0.12)', background: 'rgba(0,212,255,0.04)' }}
                whileHover={{ borderColor: 'rgba(0,212,255,0.28)' }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(0,212,255,0.1)', border: CYAN_BORDER }}>
                  <FileText size={14} className="text-cyan-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-mono truncate font-medium">{f.filename}</p>
                  <p className="text-xs text-slate-500 font-mono">
                    {(f.size_bytes / 1024).toFixed(1)} KB
                  </p>
                </div>
                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-all">
                <motion.button whileHover={{ scale: 1.1 }}
                    onClick={async () => {
                    try {
                        const r = await getFileContent(f.filename)
                        onImportToEditor(r.data.content)
                    } catch { }
                    }}
                    className="p-2 rounded-lg transition-colors"
                    title="Import to Editor"
                    style={{ color: '#a78bfa', background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.3)' }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
                </motion.button>
                <motion.button whileHover={{ scale: 1.1 }} onClick={() => handleView(f.filename)}
                    className="p-2 rounded-lg transition-colors"
                    title="Preview content"
                    style={{ color: '#e2e8f0', background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.25)' }}
                    onMouseEnter={e => e.currentTarget.style.color = '#00d4ff'}
                    onMouseLeave={e => e.currentTarget.style.color = '#e2e8f0'}>
                    <Eye size={15} />
                </motion.button>
                <motion.button whileHover={{ scale: 1.1 }} onClick={() => handleDelete(f.filename)}
                    className="p-2 rounded-lg transition-colors"
                    title="Delete file"
                    style={{ color: '#e2e8f0', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
                    onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                    onMouseLeave={e => e.currentTarget.style.color = '#e2e8f0'}>
                    <Trash2 size={15} />
                </motion.button>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {files.length === 0 && !isUploading && (
          <p className="text-xs text-slate-700 font-mono text-center py-2">NO FILES INDEXED YET</p>
        )}
      </div>

      {/* Document Viewer Modal */}
      <AnimatePresence>
        {(viewer || viewerLoading) && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-6"
            style={{ background: 'rgba(0,0,0,0.85)' }}
            onClick={() => setViewer(null)}>
            <motion.div initial={{ scale: 0.95, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95 }}
              className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl overflow-hidden"
              style={{ border: '1.5px solid rgba(0,212,255,0.3)', background: '#040f1e', boxShadow: '0 0 60px rgba(0,212,255,0.15)' }}
              onClick={e => e.stopPropagation()}>
              {/* Modal header */}
              <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0"
                style={{ borderBottom: '1px solid rgba(0,212,255,0.15)' }}>
                <div>
                  <p className="text-sm font-mono font-bold text-white">{viewer?.filename}</p>
                  {viewer && (
                    <p className="text-xs text-slate-500 font-mono mt-0.5">
                      {viewer.character_count.toLocaleString()} chars · {viewer.word_count.toLocaleString()} words
                    </p>
                  )}
                </div>
                <button onClick={() => setViewer(null)}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-white transition-colors">
                  <X size={16} />
                </button>
              </div>
              {/* Modal content */}
              <div className="flex-1 overflow-y-auto p-5">
                {viewerLoading
                  ? <div className="flex items-center justify-center h-32">
                    <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      className="w-6 h-6 rounded-full border-2 border-cyan-400 border-t-transparent" />
                  </div>
                  : <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'JetBrains Mono, monospace', fontSize: '13px', lineHeight: '1.7', color: '#94a3b8' }}>
                    {viewer?.content}
                  </pre>
                }
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}