import { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'
import { getTokenCount } from '../api/client'

interface Props {
  documentText: string
  model: string
}

interface TokenData {
  document_tokens: number
  chunk_tokens: number
  total_tokens: number
  context_window: number
  usage_percent: number
}

export default function TokenMeter({ documentText, model }: Props) {
  const [data, setData] = useState<TokenData | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      try {
        const r = await getTokenCount({
          document_text: documentText,
          retrieved_chunks: '',
          model_name: model,
        })
        setData(r.data)
      } catch { }
    }, 1000)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [documentText, model])

  const pct = data?.usage_percent ?? 0
  const color = pct < 50 ? '#22c55e' : pct < 80 ? '#f59e0b' : '#ef4444'
  const CYAN_BORDER = '1px solid rgba(0,212,255,0.25)'

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 flex-shrink-0"
      style={{ borderBottom: CYAN_BORDER, background: 'rgba(0,0,0,0.3)' }}>
      <Zap size={11} style={{ color }} className="flex-shrink-0" />
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
        <motion.div className="h-full rounded-full"
          style={{ backgroundColor: color }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }} />
      </div>
      <span className="text-xs font-mono flex-shrink-0" style={{ color, minWidth: '120px' }}>
        {pct.toFixed(1)}% of context
        {data && (
          <span className="text-slate-600 ml-1">
            ({data.document_tokens} doc + {data.chunk_tokens} ctx)
          </span>
        )}
      </span>
    </div>
  )
}