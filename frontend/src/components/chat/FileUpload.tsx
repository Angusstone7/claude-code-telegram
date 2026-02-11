import { useState, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Upload, X, File as FileIcon, Loader2, Paperclip, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatFileSize } from '@/lib/utils'
import { api } from '@/services/api'

// ── Types ────────────────────────────────────────────────────────────────

interface FileInfo {
  file_id: string
  filename: string
  size: number
  content_type: string | null
  path: string
}

interface FileUploadProps {
  onFileUploaded: (fileInfo: FileInfo) => void
  compact?: boolean
  className?: string
}

// ── Constants ────────────────────────────────────────────────────────────

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

const ALLOWED_EXTENSIONS = new Set([
  '.txt', '.md', '.py', '.js', '.ts', '.tsx', '.jsx',
  '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini',
  '.html', '.css', '.scss', '.less',
  '.java', '.kt', '.go', '.rs', '.rb', '.php',
  '.c', '.cpp', '.h', '.hpp',
  '.sh', '.bash', '.zsh',
  '.sql', '.graphql',
  '.xml', '.csv',
  '.dockerfile', '.gitignore', '.env.example',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
  '.pdf',
  '.log',
])

// ── Helpers ──────────────────────────────────────────────────────────────

function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  if (lastDot === -1) return ''
  return filename.slice(lastDot).toLowerCase()
}

function validateFile(file: File): string | null {
  const ext = getFileExtension(file.name)
  if (ext && !ALLOWED_EXTENSIONS.has(ext)) {
    return `Тип файла '${ext}' не поддерживается`
  }
  if (file.size > MAX_FILE_SIZE) {
    return `Файл слишком большой. Максимум: ${MAX_FILE_SIZE / (1024 * 1024)}MB`
  }
  return null
}

// ── Component ────────────────────────────────────────────────────────────

export function FileUpload({ onFileUploaded, compact = false, className }: FileUploadProps) {
  const { t } = useTranslation()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  // ── Drag & drop handlers ──────────────────────────────────────────────

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set false if leaving the actual drop zone (not a child element)
    if (e.currentTarget === e.target) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    setError(null)

    const droppedFile = e.dataTransfer.files[0]
    if (!droppedFile) return

    const validationError = validateFile(droppedFile)
    if (validationError) {
      setError(validationError)
      return
    }

    setSelectedFile(droppedFile)
  }, [])

  // ── File input handler ────────────────────────────────────────────────

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null)
    const file = e.target.files?.[0]
    if (!file) return

    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setSelectedFile(file)
    // Reset input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  // ── Upload handler ────────────────────────────────────────────────────

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return

    setUploading(true)
    setProgress(0)
    setError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await api.post<FileInfo>('/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setProgress(pct)
          }
        },
      })

      onFileUploaded(response.data)
      setSelectedFile(null)
      setProgress(0)
    } catch (err: unknown) {
      let message = 'Ошибка загрузки файла'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        message = axiosErr.response?.data?.detail || message
      }
      setError(message)
    } finally {
      setUploading(false)
    }
  }, [selectedFile, onFileUploaded])

  // ── Clear selection ───────────────────────────────────────────────────

  const handleClear = useCallback(() => {
    setSelectedFile(null)
    setError(null)
    setProgress(0)
  }, [])

  // ── Click to browse ───────────────────────────────────────────────────

  const openFileBrowser = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  // ── Hidden file input ─────────────────────────────────────────────────

  const hiddenInput = (
    <input
      ref={fileInputRef}
      type="file"
      className="hidden"
      onChange={handleFileSelect}
    />
  )

  // ── Compact mode (icon button for chat input area) ────────────────────

  if (compact) {
    return (
      <div className={cn('relative', className)}>
        {hiddenInput}

        <button
          type="button"
          onClick={openFileBrowser}
          disabled={uploading}
          className={cn(
            'inline-flex items-center justify-center rounded-md p-2',
            'text-muted-foreground hover:text-card-foreground hover:bg-muted',
            'transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
          )}
          title={t('chat.upload.attach', 'Прикрепить файл')}
        >
          {uploading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Paperclip className="h-5 w-5" />
          )}
        </button>

        {/* Compact file preview popover */}
        {selectedFile && !uploading && (
          <div className="absolute bottom-full left-0 mb-2 w-72 rounded-lg border border-border bg-card p-3 shadow-lg">
            <div className="flex items-center gap-2">
              <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate text-sm text-card-foreground">
                {selectedFile.name}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatFileSize(selectedFile.size)}
              </span>
              <button
                type="button"
                onClick={handleClear}
                className="ml-auto shrink-0 rounded p-0.5 text-muted-foreground hover:text-card-foreground hover:bg-muted transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={handleUpload}
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Upload className="h-3.5 w-3.5" />
                {t('chat.upload.send', 'Загрузить')}
              </button>
              <button
                type="button"
                onClick={handleClear}
                className="inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-card-foreground hover:bg-muted transition-colors"
              >
                {t('chat.upload.cancel', 'Отмена')}
              </button>
            </div>
            {error && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-red-500">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Compact upload progress */}
        {uploading && (
          <div className="absolute bottom-full left-0 mb-2 w-72 rounded-lg border border-border bg-card p-3 shadow-lg">
            <div className="flex items-center gap-2 text-sm text-card-foreground">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <span className="truncate">{selectedFile?.name}</span>
              <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                {progress}%
              </span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Full drop zone mode ───────────────────────────────────────────────

  return (
    <div className={cn('w-full', className)}>
      {hiddenInput}

      {/* Drop zone */}
      {!selectedFile && !uploading && (
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={openFileBrowser}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-3',
            'rounded-lg border-2 border-dashed p-8 transition-colors',
            isDragging
              ? 'border-primary bg-primary/5'
              : 'border-border bg-card hover:border-muted-foreground/40 hover:bg-muted/50',
          )}
        >
          <div
            className={cn(
              'rounded-full p-3',
              isDragging ? 'bg-primary/10' : 'bg-muted',
            )}
          >
            <Upload
              className={cn(
                'h-6 w-6',
                isDragging ? 'text-primary' : 'text-muted-foreground',
              )}
            />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-card-foreground">
              {isDragging
                ? t('chat.upload.dropHere', 'Отпустите файл здесь')
                : t('chat.upload.dragOrClick', 'Перетащите файл или нажмите для выбора')}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {t('chat.upload.maxSize', 'Максимум 10MB')}
            </p>
          </div>
        </div>
      )}

      {/* File selected preview */}
      {selectedFile && !uploading && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-muted p-2">
              <FileIcon className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-card-foreground">
                {selectedFile.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatFileSize(selectedFile.size)}
              </p>
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-card-foreground hover:bg-muted transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={handleUpload}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Upload className="h-4 w-4" />
              {t('chat.upload.send', 'Загрузить')}
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="inline-flex items-center rounded-md px-4 py-2 text-sm font-medium text-muted-foreground hover:text-card-foreground hover:bg-muted transition-colors"
            >
              {t('chat.upload.cancel', 'Отмена')}
            </button>
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-500">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
        </div>
      )}

      {/* Upload progress */}
      {uploading && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-card-foreground">
                {selectedFile?.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('chat.upload.uploading', 'Загрузка...')} {progress}%
              </p>
            </div>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error without file selected */}
      {!selectedFile && !uploading && error && (
        <div className="mt-2 flex items-center gap-2 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-500">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
    </div>
  )
}
