import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Shield, Lock } from 'lucide-react'
import Editor from './components/Editor'
import AISidebar from './components/AISidebar'
import TokenMeter from './components/TokenMeter'
import { getHealth, getDocuments, createDocument, updateDocument, getFiles } from './api/client'
import './App.css'

interface Document { id: number; title: string; version: number; updated_at: string }
interface FileItem { filename: string; size_bytes: number; path: string }

export default function App() {
  const [currentDoc, setCurrentDoc] = useState<Document | null>(null)
  const [docTitle, setDocTitle] = useState('Untitled Document')
  const [docContent, setDocContent] = useState('')
  const [models, setModels] = useState<string[]>(['llama3:latest', 'mistral:latest'])
  const [activeModel, setActiveModel] = useState('llama3:latest')
  const [status, setStatus] = useState<'ok' | 'error' | 'checking'>('checking')
  const [files, setFiles] = useState<FileItem[]>([])
  const [lastSaved, setLastSaved] = useState<string | null>(null)
  const [selectedText, setSelectedText] = useState('')
  const [selectionAction, setSelectionAction] = useState<'summarize' | 'improve' | 'rephrase' | null>(null)
  const [applyText, setApplyText] = useState<string | null>(null)
  const [importContent, setImportContent] = useState<string | null>(null)

  const CYAN_BORDER = '1.5px solid rgba(0,212,255,0.3)'

  // Init
  useEffect(() => {
    // Health check
    getHealth().then(r => {
      setModels(r.data.models_available || ['llama3:latest', 'mistral:latest'])
      setStatus(r.data.status === 'ok' ? 'ok' : 'error')
    }).catch(() => setStatus('error'))

    // Fix: load existing doc or create new one
    getDocuments().then(async r => {
      const docs: Document[] = r.data
      if (docs.length > 0) {
        const doc = docs[0]
        setCurrentDoc(doc)
        setDocTitle(doc.title)
      } else {
        const r2 = await createDocument('Untitled Document', '')
        setCurrentDoc(r2.data)
        setDocTitle(r2.data.title)
      }
    }).catch(async () => {
      const r2 = await createDocument('Untitled Document', '')
      setCurrentDoc(r2.data)
    })

    // Load files
    loadFiles()
  }, [])

  const loadFiles = async () => {
    try {
      const r = await getFiles()
      setFiles(r.data)
    } catch { }
  }

  const handleSaveVersion = async () => {
    if (!currentDoc) return
    try {
      await updateDocument(currentDoc.id, { title: docTitle, content: docContent })
      setLastSaved(new Date().toLocaleTimeString())
    } catch { }
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden cyber-grid"
      style={{ background: 'linear-gradient(135deg, #020b18 0%, #030d1f 60%, #020b18 100%)' }}>

      <div className="scanline" />

      {/* ── HEADER ── */}
      <motion.header initial={{ y: -50, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="flex items-center justify-between px-5 py-2.5 flex-shrink-0"
        style={{ background: 'rgba(2,11,24,0.97)', borderBottom: CYAN_BORDER, backdropFilter: 'blur(20px)' }}>

        <div className="flex items-center gap-3">
          <motion.div whileHover={{ scale: 1.08 }} className="relative">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(0,212,255,0.1)', border: CYAN_BORDER }}>
              <Shield size={17} className="text-cyan-400" />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
          </motion.div>
          <div>
            <div className="font-black text-sm tracking-widest text-white font-mono">
              LOOMIN<span className="text-cyan-400">-DOCS</span>
            </div>
            <div className="text-xs text-slate-600 font-mono tracking-wider">SECURE · AIR-GAPPED · LOCAL</div>
          </div>
          <div className="w-px h-8 mx-2" style={{ background: 'rgba(0,212,255,0.2)' }} />
          <input value={docTitle} onChange={e => setDocTitle(e.target.value)}
            className="bg-transparent text-sm text-slate-200 focus:outline-none font-mono w-52 px-2 py-1 rounded-lg transition-all"
            style={{ border: '1px solid transparent' }}
            onFocus={e => e.currentTarget.style.border = CYAN_BORDER}
            onBlur={e => e.currentTarget.style.border = '1px solid transparent'} />
        </div>

        <div className="flex items-center gap-3">
          {lastSaved && <span className="text-xs text-slate-600 font-mono">saved {lastSaved}</span>}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-xs font-bold"
            style={{
              border: status === 'ok' ? '1.5px solid rgba(0,212,255,0.4)' : '1.5px solid rgba(239,68,68,0.4)',
              background: status === 'ok' ? 'rgba(0,212,255,0.08)' : 'rgba(239,68,68,0.08)',
              color: status === 'ok' ? '#00d4ff' : '#ef4444',
            }}>
            <div className={`w-2 h-2 rounded-full ${status === 'ok' ? 'bg-cyan-400 pulse-dot' : 'bg-red-400'}`} />
            {status === 'ok' ? 'ONLINE' : status === 'checking' ? 'INIT…' : 'OFFLINE'}
          </div>
          <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            onClick={handleSaveVersion}
            className="flex items-center gap-2 px-4 py-2 text-xs font-mono font-bold rounded-lg"
            style={{ border: CYAN_BORDER, background: 'rgba(0,212,255,0.06)', color: '#00d4ff' }}>
            <Lock size={12} /> SAVE VERSION
          </motion.button>
        </div>
      </motion.header>

      {/* ── BODY ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── EDITOR COLUMN ── */}
        <motion.main initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
          className="flex flex-col flex-1 overflow-hidden">
          <TokenMeter documentText={docContent} model={activeModel} />
          <Editor
            documentId={currentDoc?.id ?? null}
            documentTitle={docTitle}
            onContentChange={setDocContent}
            onSelectionAction={(text, action) => {
              setSelectedText(text)
              setSelectionAction(action)
            }}
            applyText={applyText}
            onApplyDone={() => setApplyText(null)}
            importContent={importContent}
            onImportDone={() => setImportContent(null)}
          />
        </motion.main>

        {/* ── SIDEBAR ── */}
        <motion.div initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.15 }}
          className="flex-shrink-0 flex flex-col"
          style={{ width: '420px', borderLeft: CYAN_BORDER }}>
          <AISidebar
            documentId={currentDoc?.id ?? null}
            documentContent={docContent}
            models={models}
            activeModel={activeModel}
            onModelChange={setActiveModel}
            selectedText={selectedText}
            selectionAction={selectionAction}
            onApplyToDocument={setApplyText}
            onSelectionHandled={() => { setSelectedText(''); setSelectionAction(null) }}
            files={files}
            onFilesChanged={loadFiles}
            onImportToEditor={setImportContent}
          />
        </motion.div>
      </div>
    </div>
  )
}