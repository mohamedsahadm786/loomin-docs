import axios from 'axios'

export const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 600000,
})

// ── Health ──────────────────────────────────────────────────
export const getHealth = () => api.get('/health')

// ── Documents ───────────────────────────────────────────────
export const getDocuments = () => api.get('/documents')
export const createDocument = (title: string, content: string) =>
  api.post('/documents', { title, content })
export const getDocument = (id: number) => api.get(`/documents/${id}`)
export const updateDocument = (id: number, data: { title?: string; content?: string }) =>
  api.put(`/documents/${id}`, data)
export const deleteDocument = (id: number) => api.delete(`/documents/${id}`)

// ── Files ────────────────────────────────────────────────────
export const uploadFile = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/files/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const getFiles = () => api.get('/files')
export const deleteFile = (filename: string) => api.delete(`/files/${filename}`)
export const getFileContent = (filename: string) =>
  api.get(`/files/${encodeURIComponent(filename)}/content`)

// ── Chat ─────────────────────────────────────────────────────
export const sendChat = (payload: {
  message: string
  document_id: string | null
  model: string
  document_content: string
}) => api.post('/chat', payload)

export const getChatHistory = (documentId: number) =>
  api.get(`/chat/history/${documentId}`)

// ── Tokens ───────────────────────────────────────────────────
export const getTokenCount = (payload: {
  document_text: string
  retrieved_chunks: string
  model_name: string
}) => api.post('/token-count', payload)