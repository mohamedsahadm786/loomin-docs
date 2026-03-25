import { useEffect, useRef, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import Highlight from '@tiptap/extension-highlight'
import { motion, AnimatePresence } from 'framer-motion'
import { Bold, Italic, Underline as UnderlineIcon, Heading1, Heading2, Heading3, List, ListOrdered, Code, Quote } from 'lucide-react'
import { updateDocument } from '../api/client'


interface Props {
  documentId: number | null
  documentTitle: string
  onContentChange: (content: string) => void
  onSelectionAction: (text: string, action: 'summarize' | 'improve' | 'rephrase') => void
  applyText: string | null
  onApplyDone: () => void
  importContent: string | null
  onImportDone: () => void
}

const CYAN_BORDER = '1.5px solid rgba(0,212,255,0.3)'

export default function Editor({ documentId, documentTitle, onContentChange, onSelectionAction, applyText, onApplyDone, importContent, onImportDone }: Props) {
  const [selectedText, setSelectedText] = useState('')
  const [selectionCoords, setSelectionCoords] = useState<{ top: number; left: number } | null>(null)
  const [lastSaved, setLastSaved] = useState<string | null>(null)
  const autoSaveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Write or paste content here — or import a file from the Files tab using the ↓ import button. Then select any text to Summarize, Improve, or Rephrase it with AI.' }),
      Underline,
      Highlight.configure({ multicolor: false }),
    ],
    content: '',
    onUpdate({ editor }) {
      onContentChange(editor.getText())
    },
    onSelectionUpdate({ editor }) {
      const { from, to } = editor.state.selection
      const text = editor.state.doc.textBetween(from, to, ' ').trim()
      setSelectedText(text)
      if (text && containerRef.current) {
        const sel = window.getSelection()
        if (sel && sel.rangeCount > 0) {
          const range = sel.getRangeAt(0)
          const rect = range.getBoundingClientRect()
          const containerRect = containerRef.current.getBoundingClientRect()
          setSelectionCoords({
            top: rect.top - containerRect.top - 44,
            left: Math.max(0, rect.left - containerRect.left),
          })
        }
      } else {
        setSelectionCoords(null)
      }
    },
  })

  // Apply text from AI (improve/rephrase)
  // Import file content into editor
  useEffect(() => {
    if (!importContent || !editor) return
    editor.commands.setContent(importContent.replace(/\n/g, '<br/>'))
    onImportDone()
  }, [importContent])

  useEffect(() => {
    if (!applyText || !editor) return
    const { from, to } = editor.state.selection
    if (from !== to) {
      editor.chain().focus().deleteRange({ from, to }).insertContentAt(from, applyText).run()
    } else {
      editor.commands.insertContent(applyText)
    }
    onApplyDone()
  }, [applyText])

  // Auto-save every 30s
  useEffect(() => {
    if (!documentId || !editor) return
    if (autoSaveRef.current) clearInterval(autoSaveRef.current)
    autoSaveRef.current = setInterval(async () => {
      try {
        await updateDocument(documentId, { title: documentTitle, content: editor.getHTML() })
        setLastSaved(new Date().toLocaleTimeString())
      } catch { }
    }, 30000)
    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current) }
  }, [documentId, documentTitle, editor])

  const toolbarItems = [
    { icon: <Bold size={15} />, action: () => editor?.chain().focus().toggleBold().run(), label: 'Bold' },
    { icon: <Italic size={15} />, action: () => editor?.chain().focus().toggleItalic().run(), label: 'Italic' },
    { icon: <UnderlineIcon size={15} />, action: () => editor?.chain().focus().toggleUnderline().run(), label: 'Underline' },
    { icon: null, label: '|' },
    { icon: <Heading1 size={15} />, action: () => editor?.chain().focus().toggleHeading({ level: 1 }).run(), label: 'H1' },
    { icon: <Heading2 size={15} />, action: () => editor?.chain().focus().toggleHeading({ level: 2 }).run(), label: 'H2' },
    { icon: <Heading3 size={15} />, action: () => editor?.chain().focus().toggleHeading({ level: 3 }).run(), label: 'H3' },
    { icon: null, label: '|' },
    { icon: <List size={15} />, action: () => editor?.chain().focus().toggleBulletList().run(), label: 'Bullet' },
    { icon: <ListOrdered size={15} />, action: () => editor?.chain().focus().toggleOrderedList().run(), label: 'Ordered' },
    { icon: null, label: '|' },
    { icon: <Code size={15} />, action: () => editor?.chain().focus().toggleCode().run(), label: 'Code' },
    { icon: <Quote size={15} />, action: () => editor?.chain().focus().toggleBlockquote().run(), label: 'Quote' },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-4 py-2 flex-shrink-0 flex-wrap"
        style={{ background: 'rgba(2,11,24,0.9)', borderBottom: '1px solid rgba(0,212,255,0.12)' }}>
        {toolbarItems.map((t, i) =>
          t.icon === null
            ? <div key={i} className="w-px h-5 mx-1.5" style={{ background: 'rgba(0,212,255,0.12)' }} />
            : (
              <motion.button key={i} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                onClick={t.action} title={t.label}
                className="p-2 rounded-lg text-slate-500 hover:text-cyan-400 transition-all"
                style={{ fontSize: '13px' }}>
                {t.icon}
              </motion.button>
            )
        )}
        {lastSaved && (
          <span className="ml-auto text-xs text-slate-700 font-mono">saved {lastSaved}</span>
        )}
      </div>

      {/* Editor area with floating toolbar */}
      <div ref={containerRef} className="flex-1 overflow-y-auto relative px-12 py-10"
        style={{ background: 'rgba(2,8,18,0.6)' }}>

        {/* Floating selection toolbar */}
        <AnimatePresence>
          {selectedText && selectionCoords && (
            <motion.div initial={{ opacity: 0, scale: 0.9, y: 4 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="absolute z-30 flex items-center gap-1.5 px-2 py-1.5 rounded-xl"
              style={{
                top: selectionCoords.top,
                left: selectionCoords.left,
                background: '#040f1e',
                border: CYAN_BORDER,
                boxShadow: '0 0 20px rgba(0,212,255,0.2)',
              }}>
              {(['summarize', 'improve', 'rephrase'] as const).map((action, i) => (
                <motion.button key={action} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={() => { onSelectionAction(selectedText, action); setSelectionCoords(null) }}
                  className="px-4 py-2 text-sm font-mono font-bold rounded-xl transition-all"
                  style={i === 0
                    ? { background: 'rgba(139,92,246,0.2)', border: '2px solid rgba(139,92,246,0.5)', color: '#a78bfa' }
                    : i === 1
                      ? { background: 'rgba(0,212,255,0.15)', border: '2px solid rgba(0,212,255,0.45)', color: '#00d4ff' }
                      : { background: 'rgba(34,197,94,0.15)', border: '2px solid rgba(34,197,94,0.45)', color: '#22c55e' }
                  }>
                  {action.toUpperCase()}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="max-w-2xl mx-auto min-h-full p-8 rounded-2xl"
          style={{ border: '1px solid rgba(0,212,255,0.07)', background: 'rgba(2,11,24,0.5)' }}>
          <EditorContent editor={editor} className="min-h-full" />
        </div>
      </div>
    </div>
  )
}