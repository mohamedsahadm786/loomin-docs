import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Shield, Lock, AlertCircle, ChevronDown, Cpu, X, MessageSquare, Database, Activity } from 'lucide-react'
import { sendChat, getChatHistory, api } from '../api/client'
import FilesTab from './FilesTab'

interface Citation { source: string; chunk_id: number; preview_text: string }
interface TraceInfo { request_id: string; retrieval_ms: number; llm_ms: number; total_ms: number; tokens_per_second: number; prompt_tokens: number; completion_tokens: number }
interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  trace?: TraceInfo
  piiCount?: number
  timestamp?: string
}
interface FileItem { filename: string; size_bytes: number; path: string }

interface Props {
  documentId: number | null
  documentContent: string
  models: string[]
  activeModel: string
  onModelChange: (m: string) => void
  selectedText: string
  selectionAction: 'summarize' | 'improve' | 'rephrase' | null
  onApplyToDocument: (text: string) => void
  onSelectionHandled: () => void
  files: FileItem[]
  onFilesChanged: () => void
  onImportToEditor: (content: string) => void
}

const CYAN_BORDER = '1.5px solid rgba(0,212,255,0.3)'
const CYAN_BG = 'rgba(0,212,255,0.06)'

function CitationBadge({ c, idx }: { c: Citation; idx: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative inline-block mr-1 mb-1">
      <button onClick={() => setOpen(!open)}
        className="px-2 py-1 text-xs rounded-lg font-mono transition-all"
        style={{ background: 'rgba(0,212,255,0.1)', border: CYAN_BORDER, color: '#00d4ff' }}>
        [{idx + 1}] {c.source.length > 16 ? c.source.slice(0, 16) + '…' : c.source}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="absolute bottom-full left-0 mb-2 w-72 p-3 rounded-xl z-50"
            style={{ background: '#040f1e', border: CYAN_BORDER, boxShadow: '0 0 30px rgba(0,212,255,0.15)' }}
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-mono font-bold text-cyan-400">{c.source}</span>
              <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-white"><X size={11} /></button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">{c.preview_text}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function TypingDots() {
  return (
    <div className="flex gap-1.5 px-4 py-3">
      {[0, 1, 2].map(i => (
        <motion.div key={i} className="w-2 h-2 rounded-full" style={{ background: '#00d4ff' }}
          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 0.9, delay: i * 0.18, repeat: Infinity }} />
      ))}
    </div>
  )
}

const PII_REGEX = /\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b|\b\d{10,}\b/

export default function AISidebar({
  documentId, documentContent, models, activeModel, onModelChange,
  selectedText, selectionAction, onApplyToDocument, onSelectionHandled,
  files, onFilesChanged, onImportToEditor,
}: Props) {
  const [tab, setTab] = useState<'chat' | 'files' | 'history'>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [history, setHistory] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [piiStatus, setPiiStatus] = useState<'active' | 'redacted'>('active')
  const [piiCount, setPiiCount] = useState(0)
  const [piiWarning, setPiiWarning] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const piiTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Handle contextual actions from editor
  // Handle contextual actions — direct Ollama call, NO RAG pipeline
  useEffect(() => {
    if (!selectedText || !selectionAction) return
    handleDirectEdit(selectedText, selectionAction)
    onSelectionHandled()
  }, [selectedText, selectionAction])

  const handleDirectEdit = async (text: string, action: 'summarize' | 'improve' | 'rephrase') => {
    const prompts = {
      summarize: `Summarize the following text in 3-5 concise bullet points. Return only the summary, no preamble:\n\n${text}`,
      improve: `Improve the writing quality of the following text. Fix grammar, clarity, and flow. Return only the improved text, no preamble:\n\n${text}`,
      rephrase: `Rephrase the following text in clear professional English. Preserve the exact meaning. Return only the rephrased text, no preamble:\n\n${text}`,
    }
    setTab('chat')
    setMessages(prev => [...prev, { role: 'user', content: `[${action.toUpperCase()}] ${text.slice(0, 80)}${text.length > 80 ? '…' : ''}` }])
    setLoading(true)
    try {
      // Direct Ollama call — no RAG, no file search, just LLM
      const r = await api.post('/chat', {
        message: prompts[action],
        document_id: documentId ? String(documentId) : null,
        model: activeModel,
        document_content: '',
        skip_rag: true,
      })
      const response = r.data.response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response,
        citations: [],  // No citations — this is a direct edit, not RAG
        trace: r.data.trace,
      }])
      if (action === 'improve' || action === 'rephrase') {
        onApplyToDocument(response)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Could not process editing action.' }])
    }
    setLoading(false)
  }

  const flashPii = (count: number) => {
    setPiiCount(count)
    setPiiStatus('redacted')
    if (piiTimerRef.current) clearTimeout(piiTimerRef.current)
    piiTimerRef.current = setTimeout(() => setPiiStatus('active'), 3000)
  }

  const handleSend = async (msg: string, action?: string) => {
    const text = msg || input.trim()
    if (!text || !documentId) return
    if (PII_REGEX.test(text)) setPiiWarning(true)
    else setPiiWarning(false)
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInput('')
    setLoading(true)
    try {
      const r = await sendChat({
        message: text,
        document_id: documentId ? String(documentId) : null,
        model: activeModel,
        document_content: documentContent,
      })
      const { response, citations, redacted_fields, trace } = r.data
      const piiCount = redacted_fields?.length ?? 0
      if (piiCount > 0) flashPii(piiCount)
      const assistantMsg: Message = { role: 'assistant', content: response, citations, trace, piiCount }
      setMessages(prev => [...prev, assistantMsg])
      if (action === 'improve' || action === 'rephrase') {
        onApplyToDocument(response)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Backend unreachable. Is the server running?' }])
    }
    setLoading(false)
  }

  const loadHistory = async () => {
    if (!documentId) return
    setHistoryLoading(true)
    try {
      const r = await getChatHistory(documentId)
      setHistory(r.data)
    } catch { }
    setHistoryLoading(false)
  }

  const handleTabChange = (t: 'chat' | 'files' | 'history') => {
    setTab(t)
    if (t === 'history') loadHistory()
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'rgba(2,8,20,0.97)' }}>

      {/* Tabs */}
      <div className="flex flex-shrink-0" style={{ borderBottom: '1.5px solid rgba(0,212,255,0.25)' }}>
        {([
          { key: 'chat', icon: <MessageSquare size={12} />, label: 'CHAT' },
          { key: 'files', icon: <Database size={12} />, label: 'FILES' },
          { key: 'history', icon: <Activity size={12} />, label: 'HISTORY' },
        ] as const).map((t, i) => (
          <button key={t.key} onClick={() => handleTabChange(t.key)}
            className="flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-mono font-bold transition-all"
            style={{
              color: tab === t.key ? '#00d4ff' : '#475569',
              background: tab === t.key ? CYAN_BG : 'transparent',
              borderBottom: tab === t.key ? '2px solid #00d4ff' : '2px solid transparent',
              borderRight: i < 2 ? '1px solid rgba(0,212,255,0.12)' : 'none',
            }}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* PII Shield — always visible on chat tab */}
      {tab === 'chat' && (
        <div className="flex items-center justify-between px-4 py-2 flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(0,212,255,0.1)', background: 'rgba(0,0,0,0.2)' }}>
          <motion.div
            animate={piiStatus === 'redacted' ? { scale: [1, 1.05, 1] } : {}}
            transition={{ duration: 0.4, repeat: piiStatus === 'redacted' ? 3 : 0 }}
            className="flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-bold"
            style={{
              border: piiStatus === 'active' ? '1px solid rgba(34,197,94,0.35)' : '1px solid rgba(245,158,11,0.4)',
              background: piiStatus === 'active' ? 'rgba(34,197,94,0.08)' : 'rgba(245,158,11,0.1)',
              color: piiStatus === 'active' ? '#22c55e' : '#f59e0b',
            }}>
            <Lock size={10} />
            {piiStatus === 'active' ? 'PII SHIELD ACTIVE' : `${piiCount} FIELDS REDACTED`}
          </motion.div>

          {/* PII warning */}
          <AnimatePresence>
            {piiWarning && (
              <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="flex items-center gap-1 text-xs font-mono text-amber-400">
                <AlertCircle size={10} /> May contain PII
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Model selector */}
      {tab === 'chat' && (
        <div className="flex items-center gap-2.5 px-4 py-2 flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(0,212,255,0.1)', background: 'rgba(0,212,255,0.02)' }}>
          <Cpu size={12} className="text-cyan-700 flex-shrink-0" />
          <div className="relative flex-1">
            <select value={activeModel} onChange={e => onModelChange(e.target.value)}
              className="w-full text-xs font-mono font-bold text-cyan-300 px-3 py-1.5 rounded-lg appearance-none focus:outline-none cursor-pointer pr-6"
              style={{ background: 'rgba(0,212,255,0.06)', border: CYAN_BORDER }}>
              {models.map(m => <option key={m} value={m} style={{ background: '#020b18' }}>{m}</option>)}
            </select>
            <ChevronDown size={10} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-cyan-600 pointer-events-none" />
          </div>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-hidden flex flex-col">

        {/* CHAT TAB */}
        {tab === 'chat' && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}
                  className="flex flex-col items-center justify-center h-full text-center py-14">
                  <motion.div animate={{ rotate: [0, 4, -4, 0] }} transition={{ duration: 5, repeat: Infinity }}
                    className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                    style={{ background: 'rgba(0,212,255,0.08)', border: CYAN_BORDER }}>
                    <Shield size={28} className="text-cyan-500" />
                  </motion.div>
                  <p className="text-sm font-mono font-bold text-slate-400">SECURE RAG INTERFACE</p>
                  <p className="text-xs text-slate-600 font-mono mt-1">Upload files → Ask questions</p>
                  <p className="text-xs text-slate-700 font-mono">All processing is local & air-gapped</p>
                </motion.div>
              )}
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-[88%] rounded-2xl px-4 py-3"
                      style={msg.role === 'user'
                        ? { background: 'rgba(0,212,255,0.12)', border: CYAN_BORDER, borderTopRightRadius: 4 }
                        : { background: 'rgba(255,255,255,0.04)', border: '1.5px solid rgba(255,255,255,0.09)', borderTopLeftRadius: 4 }}>
                      <p className={`text-sm leading-relaxed whitespace-pre-wrap ${msg.role === 'user' ? 'font-mono text-cyan-100' : 'text-slate-300'}`}>
                        {msg.content}
                      </p>
                      {msg.piiCount && msg.piiCount > 0 ? (
                        <div className="flex items-center gap-1 mt-1.5 text-xs font-mono text-amber-400">
                          <AlertCircle size={10} /> {msg.piiCount} PII FIELD(S) INTERCEPTED
                        </div>
                      ) : null}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2.5 pt-2" style={{ borderTop: '1px solid rgba(0,212,255,0.12)' }}>
                          <p className="text-xs font-mono text-slate-600 mb-1.5">SOURCES:</p>
                          {msg.citations.map((c, ci) => <CitationBadge key={ci} c={c} idx={ci} />)}
                        </div>
                      )}
                      {msg.trace && (
                        <div className="mt-1.5 pt-1 flex gap-3 text-xs font-mono text-slate-700"
                          style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                          <span>{msg.trace.retrieval_ms}ms</span>
                          <span>{msg.trace.tokens_per_second.toFixed(1)} tok/s</span>
                          <span className="opacity-40">{msg.trace.request_id?.slice(0, 8)}</span>
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              {loading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                  <div className="rounded-2xl rounded-tl-sm"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1.5px solid rgba(255,255,255,0.09)' }}>
                    <TypingDots />
                  </div>
                </motion.div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 flex-shrink-0"
              style={{ borderTop: '1.5px solid rgba(0,212,255,0.2)', background: 'rgba(0,0,0,0.3)' }}>
              <AnimatePresence>
                {piiWarning && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="text-xs font-mono text-amber-400 mb-2 flex items-center gap-1.5 px-1">
                    <AlertCircle size={11} />
                    This message may contain sensitive data. The PII Shield will intercept it.
                  </motion.div>
                )}
              </AnimatePresence>
              <div className="flex gap-2.5">
                <input value={input} onChange={e => { setInput(e.target.value); if (!e.target.value) setPiiWarning(false) }}
                    onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend(input)}
                    placeholder="Query secure documents…"
                    className="flex-1 text-sm text-slate-200 placeholder-slate-600 font-mono px-4 py-3.5 rounded-xl focus:outline-none transition-all"
                    style={{ background: 'rgba(0,212,255,0.05)', border: CYAN_BORDER, minHeight: '52px' }}
                    onFocus={e => e.currentTarget.style.boxShadow = '0 0 0 3px rgba(0,212,255,0.2)'}
                    onBlur={e => e.currentTarget.style.boxShadow = 'none'} />
                <motion.button whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.94 }}
                    onClick={() => handleSend(input)}
                    disabled={loading || !input.trim()}
                    className="px-5 rounded-xl disabled:opacity-30 transition-all flex items-center justify-center"
                    style={{ background: 'rgba(0,212,255,0.12)', border: CYAN_BORDER, minHeight: '52px' }}>
                    <Send size={17} className="text-cyan-400" />
                </motion.button>
                </div>
            </div>
          </>
        )}

        {/* FILES TAB */}
        {tab === 'files' && (
        <FilesTab files={files} onFilesChanged={onFilesChanged} onImportToEditor={onImportToEditor} />
        )}

        {/* HISTORY TAB */}
        {tab === 'history' && (
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {historyLoading && (
              <div className="flex justify-center py-8">
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  className="w-6 h-6 rounded-full border-2 border-cyan-400 border-t-transparent" />
              </div>
            )}
            {!historyLoading && history.length === 0 && (
              <p className="text-xs text-slate-700 font-mono text-center py-8">NO CHAT HISTORY YET</p>
            )}
            {history.map((msg, i) => (
              <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className="max-w-[88%] rounded-2xl px-4 py-3"
                  style={msg.role === 'user'
                    ? { background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)', borderTopRightRadius: 4 }
                    : { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderTopLeftRadius: 4 }}>
                  <p className="text-xs text-slate-500 font-mono mb-1">
                    {msg.role.toUpperCase()} · {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-400">{msg.content}</p>
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2">
                      {msg.citations.map((c, ci) => <CitationBadge key={ci} c={c} idx={ci} />)}
                    </div>
                  )}
                  {msg.trace && (
                    <p className="text-xs font-mono text-slate-700 mt-1">
                      {msg.trace.retrieval_ms}ms · {msg.trace.tokens_per_second.toFixed(1)} tok/s
                    </p>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}