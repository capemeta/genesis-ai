/**
 * 文件上传 Hook（两阶段上传）
 * 
 * 设计理念：
 * 1. 第一阶段：上传文件 → 创建 documents 记录（与知识库无关）
 * 2. 第二阶段：用户点击"保存" → 关联到知识库 → 创建 knowledge_base_documents 记录
 * 
 * 功能：
 * - 文件验证（类型、大小）
 * - 上传进度跟踪
 * - 批量上传管理
 * - 错误处理
 * - 支持秒传和去重
 */
import { useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadDocument } from '@/lib/api/document'
import {  attachDocumentsToKB} from '@/lib/api/knowledge-base'

/**
 * 支持的文件类型
 */
const ALLOWED_FILE_TYPES = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
  'application/msword': 'DOC',
  'text/plain': 'TXT',
  'text/markdown': 'MD',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
  'application/vnd.ms-excel': 'XLS',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
  'application/vnd.ms-powerpoint': 'PPT',
  'text/csv': 'CSV',
}

const ALLOWED_EXTENSIONS = [
  'pdf', 'docx', 'doc', 'txt', 'md', 'xlsx', 'xls', 'pptx', 'ppt', 'csv'
]

/**
 * 文件大小限制（100MB）
 */
const MAX_FILE_SIZE = 100 * 1024 * 1024

/**
 * 上传文件项
 */
export interface UploadFileItem {
  id: string
  file: File
  name: string
  size: number
  type: string
  status: 'pending' | 'uploading' | 'uploaded' | 'error' | 'cancelled'
  progress: number
  error?: string
  documentId?: string  // 第一阶段完成后的 document_id
  isDuplicate?: boolean  // 是否秒传
}

/**
 * 上传选项
 */
export interface UploadOptions {
  kbId: string
  folderId?: string | null
  parseImmediately?: boolean  // 是否立即解析
}

/**
 * 文件上传 Hook
 */
export function useFileUpload() {
  const queryClient = useQueryClient()
  const [uploadFiles, setUploadFiles] = useState<UploadFileItem[]>([])
  const [isAttaching, setIsAttaching] = useState(false)
  const uploadingRef = useRef<Set<string>>(new Set())

  /**
   * 验证文件
   */
  const validateFile = useCallback((file: File): { valid: boolean; error?: string } => {
    // 检查文件类型
    const extension = file.name.split('.').pop()?.toLowerCase()
    const isValidType =
      ALLOWED_FILE_TYPES[file.type as keyof typeof ALLOWED_FILE_TYPES] ||
      (extension && ALLOWED_EXTENSIONS.includes(extension))

    if (!isValidType) {
      return {
        valid: false,
        error: `不支持的文件类型。支持的格式：${ALLOWED_EXTENSIONS.join(', ')}`,
      }
    }

    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: `文件大小超过限制（最大 100MB）`,
      }
    }

    // 检查文件名
    if (file.name.length > 255) {
      return {
        valid: false,
        error: `文件名过长（最大 255 个字符）`,
      }
    }

    return { valid: true }
  }, [])

  /**
   * 更新文件状态
   */
  const updateFileStatus = useCallback((
    fileId: string,
    updates: Partial<UploadFileItem>
  ) => {
    setUploadFiles(prev =>
      prev.map(f => (f.id === fileId ? { ...f, ...updates } : f))
    )
  }, [])

  /**
   * 第一阶段：上传单个文件（纯物理上传）
   */
  const uploadSingleFile = useCallback(async (
    fileItem: UploadFileItem
  ) => {
    if (uploadingRef.current.has(fileItem.id)) return
    uploadingRef.current.add(fileItem.id)

    try {
      // 上传文件
      updateFileStatus(fileItem.id, { status: 'uploading', progress: 0 })

      const result = await uploadDocument(
        fileItem.file,
        // 进度回调
        (progress) => {
          updateFileStatus(fileItem.id, { progress })
        }
      )

      // 上传成功
      updateFileStatus(fileItem.id, {
        status: 'uploaded',
        progress: 100,
        documentId: result.data.id,
        isDuplicate: result.data.is_duplicate,
      })
    } catch (error: any) {
      // 上传失败
      updateFileStatus(fileItem.id, {
        status: 'error',
        error: error.message || '上传失败',
      })
    } finally {
      uploadingRef.current.delete(fileItem.id)
    }
  }, [updateFileStatus])

  /**
   * 第一阶段：执行上传队列
   */
  const processUploadQueue = useCallback(async () => {
    const pendingFiles = uploadFiles.filter(f => f.status === 'pending')
    if (pendingFiles.length === 0) return

    // 并发上限
    const MAX_CONCURRENCY = 3

    const run = async () => {
      const activePromises: Promise<void>[] = []

      for (const file of pendingFiles) {
        if (uploadingRef.current.size >= MAX_CONCURRENCY) {
          await Promise.race(activePromises)
        }

        const p = uploadSingleFile(file).finally(() => {
          activePromises.splice(activePromises.indexOf(p), 1)
        })
        activePromises.push(p)
      }

      await Promise.all(activePromises)
    }

    run()
  }, [uploadFiles, uploadSingleFile])

  /**
   * 第二阶段：关联文档到知识库（用户点击"保存"时调用）
   */
  const attachToKnowledgeBase = useCallback(async (options: UploadOptions) => {
    // 收集所有成功上传的 document_id
    const uploadedFiles = uploadFiles.filter(f => f.status === 'uploaded' && f.documentId)
    if (uploadedFiles.length === 0) {
      throw new Error('没有可关联的文档')
    }

    const documentIds = uploadedFiles.map(f => f.documentId!)

    setIsAttaching(true)
    try {
      // 调用关联 API，传递 parseImmediately 参数
      const result = await attachDocumentsToKB(
        options.kbId,
        documentIds,
        options.folderId,
        options.parseImmediately
      )

      // 刷新缓存
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['knowledge-base', options.kbId] })
      queryClient.invalidateQueries({ queryKey: ['knowledge-bases'] })

      return result
    } finally {
      setIsAttaching(false)
    }
  }, [uploadFiles, queryClient])

  /**
   * 添加文件到上传队列
   */
  const addFiles = useCallback((files: File[]) => {
    const newFiles: UploadFileItem[] = files.map(file => ({
      id: `${Date.now()}-${Math.random()}`,
      file,
      name: file.name,
      size: file.size,
      type: file.type,
      status: 'pending',
      progress: 0,
    }))

    // 验证文件
    const validatedFiles = newFiles.map(item => {
      const validation = validateFile(item.file)
      if (!validation.valid) {
        return { ...item, status: 'error' as const, error: validation.error }
      }
      return item
    })

    setUploadFiles(prev => [...prev, ...validatedFiles])
    return validatedFiles
  }, [validateFile])

  /**
   * 移除文件
   */
  const removeFile = useCallback((fileId: string) => {
    uploadingRef.current.delete(fileId)
    setUploadFiles(prev => prev.filter(f => f.id !== fileId))
  }, [])

  /**
   * 取消上传
   */
  const cancelUpload = useCallback((fileId: string) => {
    uploadingRef.current.delete(fileId)
    updateFileStatus(fileId, { status: 'cancelled' })
  }, [updateFileStatus])

  /**
   * 批量清空
   */
  const clearAll = useCallback(() => {
    setUploadFiles(prev =>
      prev.filter(f => f.status === 'uploading')
    )
  }, [])

  /**
   * 重试失败的文件
   */
  const retryFailed = useCallback(() => {
    setUploadFiles(prev =>
      prev.map(f => f.status === 'error' ? { ...f, status: 'pending', error: undefined } : f)
    )
  }, [])

  // 暴露关键状态
  const isUploading = uploadFiles.some(f => f.status === 'uploading')
  const isAllUploaded = uploadFiles.length > 0 && uploadFiles.every(f => f.status === 'uploaded' || f.status === 'error')
  const hasError = uploadFiles.some(f => f.status === 'error')
  const totalCount = uploadFiles.length
  const uploadedCount = uploadFiles.filter(f => f.status === 'uploaded').length
  const duplicateCount = uploadFiles.filter(f => f.status === 'uploaded' && f.isDuplicate).length
  const pendingCount = uploadFiles.filter(f => f.status === 'pending').length

  return {
    uploadFiles,
    addFiles,
    removeFile,
    processUploadQueue,
    attachToKnowledgeBase,
    cancelUpload,
    clearAll,
    retryFailed,
    // 状态
    isUploading,
    isAllUploaded,
    isAttaching,
    hasError,
    totalCount,
    uploadedCount,
    duplicateCount,
    pendingCount,
  }
}
