/**
 * 文件上传对话框 - 两阶段上传
 *
 * 设计理念：
 * 1. 第一阶段：上传文件 → 创建 documents 记录（自动执行）
 * 2. 第二阶段：用户点击"保存" → 关联到知识库 → 创建 knowledge_base_documents 记录
 *
 * 标签：上传时暂不选标签；文档入库后可在文件列表/元数据中打标签（resource_tags.target_type=kb_doc）。
 * 后续若需在上传阶段选标签，可在此扩展（如 initialTagIds / onUploadSuccess 时写 resource_tags）。
 *
 * 参考 RAGFlow 设计：
 * - 极简的标题栏
 * - 紧凑的文件列表
 * - 充分利用空间
 */
import { useEffect, useRef, useState } from 'react'
import { AxiosError } from 'axios'
import { Trash2, Folder, HelpCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { FileUploadDropzone } from '../components/file-upload-dropzone'
import { FileUploadList } from '../components/file-upload-list'
import { useFileUpload } from '../hooks/use-file-upload'
import { toast } from 'sonner'
import {
  fetchKnowledgeBase,
  fetchKnowledgeBaseDocuments,
  precheckTableDocumentImport,
  type AttachDocumentsResponse,
} from '@/lib/api/knowledge-base'
import {
  filterFilesByKbProfile,
  getKbUploadProfile,
} from '@/features/knowledge-base/kb-upload-profile'
import { downloadQATemplate } from '@/lib/api/qa-items'
import { downloadTableImportTemplate } from '@/lib/api/table-rows'

interface FileUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  kbType?: string
  currentFolderName?: string
  currentFolderId?: string | null
  isLoadingFolder?: boolean
  onUploadSuccess?: () => void // 上传成功后的回调
  onTableSchemaInitialized?: (payload: AttachDocumentsResponse) => void
}

export function FileUploadDialog({
  open,
  onOpenChange,
  kbId,
  kbType,
  currentFolderName = '/',
  currentFolderId,
  onUploadSuccess,
  onTableSchemaInitialized,
}: FileUploadDialogProps) {
  const MAX_FILES = 20
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [parseImmediately, setParseImmediately] = useState(true)
  /** 模板下载中，避免重复点击 */
  const [templateDownloading, setTemplateDownloading] = useState<'qa' | 'table' | null>(null)
  const { data: knowledgeBase } = useQuery({
    queryKey: ['knowledge-base', kbId, 'upload-dialog'],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: open && !!kbId,
    staleTime: 0,
  })
  const { data: existingTableDocuments } = useQuery({
    queryKey: ['kb-documents', kbId, 'upload-dialog'],
    queryFn: () =>
      fetchKnowledgeBaseDocuments(kbId, {
        page: 1,
        page_size: 1,
      }),
    enabled: open && !!kbId && kbType === 'table',
    staleTime: 0,
  })

  const effectiveKbType = kbType ?? knowledgeBase?.type
  const uploadProfile = getKbUploadProfile(effectiveKbType)

  const tableSchemaColumns = Array.isArray(knowledgeBase?.retrieval_config?.table?.schema?.columns)
    ? knowledgeBase.retrieval_config.table.schema.columns
    : []
  const tableSchemaStatus = String(knowledgeBase?.retrieval_config?.table?.schema_status || '').toLowerCase()
  const isTableSchemaDraft = kbType === 'table' && tableSchemaColumns.length > 0 && tableSchemaStatus !== 'confirmed'
  const existingTableDocumentCount = existingTableDocuments?.total || 0
  const hasExistingTableDocuments = existingTableDocumentCount > 0

  const {
    uploadFiles,
    addFiles,
    removeFile,
    processUploadQueue,
    attachToKnowledgeBase,
    clearAll,
    retryFailed,
    isUploading,
    isAllUploaded,
    isAttaching,
    hasError,
    totalCount,
    uploadedCount,
    duplicateCount,
    pendingCount,
  } = useFileUpload()

  /**
   * 处理文件添加（带数量限制和重复检测）
   */
  const handleAddFiles = (files: File[]) => {
    const { allowed, rejected } = filterFilesByKbProfile(files, uploadProfile)
    if (rejected.length > 0) {
      toast.warning(
        `已跳过 ${rejected.length} 个不符合当前知识库类型的文件：${rejected
          .slice(0, 3)
          .map((f) => f.name)
          .join(', ')}${rejected.length > 3 ? '…' : ''}`
      )
    }
    if (allowed.length === 0) {
      if (rejected.length > 0) {
        toast.info('没有符合格式的文件可添加')
      }
      return
    }

    const remainingSlots = MAX_FILES - totalCount

    if (remainingSlots <= 0) {
      toast.error(`最多只能上传 ${MAX_FILES} 个文件`)
      return
    }

    // 检测重复文件（基于文件名和大小）
    const existingFiles = new Map(
      uploadFiles.map(f => [`${f.file.name}-${f.file.size}`, f.file.name])
    )

    const newFiles: File[] = []
    const duplicates: string[] = []

    for (const file of allowed) {
      const fileKey = `${file.name}-${file.size}`
      if (existingFiles.has(fileKey)) {
        duplicates.push(file.name)
      } else {
        newFiles.push(file)
        existingFiles.set(fileKey, file.name)
      }
    }

    // 提示重复文件
    if (duplicates.length > 0) {
      toast.warning(
        `已跳过 ${duplicates.length} 个重复文件：${duplicates.slice(0, 3).join(', ')}${duplicates.length > 3 ? '...' : ''}`
      )
    }

    // 检查数量限制
    if (newFiles.length === 0) {
      if (duplicates.length > 0) {
        toast.info('所有文件都已存在')
      }
      return
    }

    if (newFiles.length > remainingSlots) {
      toast.warning(`只能再添加 ${remainingSlots} 个文件，已自动截取前 ${remainingSlots} 个`)
      addFiles(newFiles.slice(0, remainingSlots))
    } else {
      addFiles(newFiles)
      if (newFiles.length > 0) {
        toast.success(`已添加 ${newFiles.length} 个文件`)
      }
    }
  }

  /**
   * 处理文件选择
   */
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleAddFiles(Array.from(files))
    }
    // 重置 input，允许选择相同文件
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  /**
   * 第一阶段：自动开始上传
   */
  useEffect(() => {
    if (pendingCount > 0 && !isUploading) {
      processUploadQueue()
    }
  }, [pendingCount, isUploading, processUploadQueue])

  /**
   * 第二阶段：处理保存（关联到知识库）
   */
  const handleSave = async () => {
    if (!isAllUploaded) {
      toast.error('请等待所有文件上传完成')
      return
    }

    if (uploadedCount === 0) {
      toast.error('没有可保存的文件')
      return
    }

    try {
      if (kbType === 'table') {
        const uploadedTableFiles = uploadFiles.filter((file) => file.status === 'uploaded' && file.documentId)
        if (isTableSchemaDraft && hasExistingTableDocuments) {
          toast.error('当前结构草稿尚未定稿，请先到结构定义中确认结构后再继续导入')
          return
        }
        let initialHeader: string[] | null = null
        let initialFileName: string | null = null
        for (const file of uploadedTableFiles) {
          const result = await precheckTableDocumentImport(kbId, file.documentId!)
          if (!tableSchemaColumns.length) {
            if (initialHeader === null) {
              initialHeader = result.detected_header
              initialFileName = file.name
            } else if (result.detected_header.join('|') !== initialHeader.join('|')) {
              toast.error(`${file.name} 与首个文件 ${initialFileName} 的表头不一致`)
              return
            }
          }
          if (!result.compatible) {
            const message = `${file.name} 结构预检未通过：${result.summary}`
            toast.error(message)
            return
          }
        }
      }

      const result = await attachToKnowledgeBase({
        kbId,
        folderId: currentFolderId,
        parseImmediately, // 传递立即解析参数
      })

      // 显示统计信息
      const messages: string[] = []
      if (result.data.success_count > 0) {
        messages.push(`成功关联 ${result.data.success_count} 个文件`)
      }
      if (result.data.duplicate_count > 0) {
        messages.push(`跳过 ${result.data.duplicate_count} 个重复文件`)
      }
      if (result.data.failed_count > 0) {
        messages.push(`失败 ${result.data.failed_count} 个`)
      }

      if (result.data.failed_count > 0) {
        toast.warning(messages.join('，'))
      } else if (result.data.duplicate_count > 0 && result.data.success_count === 0) {
        toast.info(messages.join('，'))
      } else {
        toast.success(messages.join('，'))
      }

      if (result.data.table_schema_initialized) {
        toast.success(`已生成表格结构草稿，共识别 ${result.data.table_schema_column_count || 0} 个字段，请先到结构定义中确认后再继续导入其他文档`)
        onTableSchemaInitialized?.(result.data)
      }

      // 触发父组件刷新文件列表
      onUploadSuccess?.()

      onOpenChange(false)
      clearAll()
      setParseImmediately(true) // 重置为默认勾选
    } catch (error: unknown) {
      const message =
        error instanceof AxiosError
          ? error.response?.data?.message ?? error.response?.data?.detail ?? error.message
          : error instanceof Error
            ? error.message
            : '关联失败'
      toast.error(message)
    }
  }

  /**
   * 处理关闭
   */
  const handleDownloadQATemplate = async () => {
    try {
      setTemplateDownloading('qa')
      await downloadQATemplate()
      toast.success('已开始下载 QA 导入模板')
    } catch {
      toast.error('QA 模板下载失败，请稍后重试')
    } finally {
      setTemplateDownloading(null)
    }
  }

  const handleDownloadTableSample = async () => {
    try {
      setTemplateDownloading('table')
      await downloadTableImportTemplate()
      toast.success('已开始下载表格导入样例')
    } catch {
      toast.error('表格样例下载失败，请稍后重试')
    } finally {
      setTemplateDownloading(null)
    }
  }

  const handleClose = () => {
    if (isUploading || isAttaching) {
      if (!confirm('正在处理中，确定要中断并关闭吗？')) {
        return
      }
    }
    onOpenChange(false)
    setTimeout(() => {
      clearAll()
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className="sm:max-w-[900px] max-h-[90vh] overflow-hidden flex flex-col p-0 gap-0"
        onInteractOutside={(e) => {
          // 阻止点击外部关闭
          e.preventDefault()
        }}
        onEscapeKeyDown={(e) => {
          // ESC 键也需要确认
          if (isUploading || isAttaching) {
            e.preventDefault()
            if (confirm('正在处理中，确定要中断并关闭吗？')) {
              onOpenChange(false)
              setTimeout(clearAll, 300)
            }
          }
        }}
      >
        {/* 标题栏 - 参考文件夹对话框的渐变样式 */}
        <DialogHeader className="border-b px-8 py-4 shrink-0 space-y-2">
          <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-green-600 to-blue-600 bg-clip-text text-transparent">
            上传文件
          </DialogTitle>
          {effectiveKbType === 'qa' && (
            <div className="rounded-md border border-orange-500/50 bg-orange-50/95 px-3 py-2 dark:border-orange-500/40 dark:bg-orange-950/45">
              <p className="text-sm leading-snug sm:text-[15px]">
                <span className="text-orange-950 dark:text-orange-50">
                  说明：支持 .xlsx / .csv；按模板列填写：相似问用 <span className="whitespace-nowrap">||</span> 分隔，enabled 填是/否等。
                </span>
                <button
                  type="button"
                  disabled={templateDownloading !== null}
                  onClick={handleDownloadQATemplate}
                  className="ml-1 inline p-0 align-baseline text-blue-600 underline decoration-blue-600/70 underline-offset-2 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60 dark:text-blue-400 dark:decoration-blue-400/70 dark:hover:text-blue-300"
                >
                  {templateDownloading === 'qa' ? '下载中…' : '下载模板'}
                </button>
              </p>
            </div>
          )}
          {effectiveKbType === 'table' && (
            <div className="space-y-1.5">
              <div className="rounded-md border border-orange-500/50 bg-orange-50/95 px-3 py-2 dark:border-orange-500/40 dark:bg-orange-950/45">
                <p className="text-sm leading-snug sm:text-[15px]">
                  <span className="text-orange-950 dark:text-orange-50">
                    说明：首行表头、第二行开始为数据；批量导入时各文件列名与顺序须一致。
                  </span>
                  <button
                    type="button"
                    disabled={templateDownloading !== null}
                    onClick={handleDownloadTableSample}
                    className="ml-1 inline p-0 align-baseline text-blue-600 underline decoration-blue-600/70 underline-offset-2 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60 dark:text-blue-400 dark:decoration-blue-400/70 dark:hover:text-blue-300"
                  >
                    {templateDownloading === 'table' ? '下载中…' : '下载样例'}
                  </button>
                </p>
              </div>
              {isTableSchemaDraft && !hasExistingTableDocuments && (
                <p className="px-0.5 text-xs leading-snug text-orange-900/90 dark:text-orange-100/90">
                  有结构草稿、尚无样例时，将按草稿校验。
                </p>
              )}
              {isTableSchemaDraft && hasExistingTableDocuments && (
                <p className="px-0.5 text-xs leading-snug text-orange-950 dark:text-orange-50">
                  草稿未定稿，请先在「结构定义」确认后再导入。
                </p>
              )}
            </div>
          )}
          {uploadProfile.dialogDescription.trim() ? (
            <DialogDescription className="text-left text-[12px] leading-snug text-muted-foreground sm:text-[13px]">
              {uploadProfile.dialogDescription}
            </DialogDescription>
          ) : null}
        </DialogHeader>

        {/* 主内容区 */}
        <div className="flex-1 min-h-0 flex flex-col">
          {/* 固定区域：文件夹信息 */}
          <div className="px-8 pt-6 pb-5 space-y-5 shrink-0 border-b">
            {/* 文件夹 - 简洁清爽的样式 */}
            <div className="space-y-2">
              <Label className="text-base font-semibold text-gray-800 dark:text-gray-200">
                目标文件夹
              </Label>
              <TooltipProvider>
                <Tooltip delayDuration={300}>
                  <TooltipTrigger asChild>
                    <div className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-950/30 dark:to-blue-950/30 border-2 border-green-200 dark:border-green-800 max-w-md cursor-help">
                      <Folder className="h-4 w-4 text-green-600 dark:text-green-400 shrink-0" />
                      <span className="font-semibold text-base text-gray-800 dark:text-gray-200 truncate">
                        {currentFolderName === '/' ? '根目录' : currentFolderName}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-md break-all">
                    <p className="text-sm">
                      <span className="font-semibold">完整路径：</span>
                      <br />
                      {currentFolderName === '/' ? '根目录' : currentFolderName}
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            {/* 文件标题栏 + 立即解析 */}
            <div className="flex items-center justify-between pt-2">
              <Label className="text-base font-semibold text-gray-800 dark:text-gray-200">
                文件列表 <span className="text-muted-foreground font-normal">({totalCount}/{MAX_FILES})</span>
              </Label>

              <div className="flex items-center gap-3">
                {/* 立即解析选项 */}
                <div className="flex items-center gap-2">
                  <Switch
                    id="parse-immediately"
                    checked={parseImmediately}
                    onCheckedChange={setParseImmediately}
                  />
                  <label
                    htmlFor="parse-immediately"
                    className="text-sm font-medium cursor-pointer select-none"
                  >
                    立即解析
                  </label>
                  <TooltipProvider>
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <HelpCircle className="h-4 w-4 text-muted-foreground hover:text-blue-500 cursor-help transition-colors" />
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="max-w-xs">
                        <p className="text-sm">勾选后将自动进行文档分块和向量化处理</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                {/* 操作按钮 */}
                {uploadFiles.length > 0 && (
                  <div className="flex items-center gap-2 pl-3 border-l">
                    {hasError && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-sm hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
                        onClick={retryFailed}
                      >
                        重试失败
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
                      onClick={clearAll}
                    >
                      <Trash2 className="h-4 w-4 mr-1.5" />
                      清空列表
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 滚动区域：文件列表 */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="p-8 space-y-4">
              {uploadFiles.length === 0 ? (
                <FileUploadDropzone
                  onFilesSelected={handleAddFiles}
                  className="min-h-[220px]"
                  accept={uploadProfile.accept}
                  formatTags={uploadProfile.formatTags}
                />
              ) : (
                <>
                  <FileUploadList
                    files={uploadFiles}
                    onRemove={removeFile}
                    onCancel={() => { }}
                  />

                  {totalCount < MAX_FILES && (
                    <FileUploadDropzone
                      onFilesSelected={handleAddFiles}
                      compact
                      compactText={`继续添加文件（还可添加 ${MAX_FILES - totalCount} 个）`}
                      compactHint="支持继续拖拽到这里，或点击选择文件"
                      accept={uploadProfile.accept}
                      formatTags={uploadProfile.formatTags}
                    />
                  )}
                </>
              )}

              {/* 提示信息 - 参考文件夹对话框的样式 */}
              <div className="p-4 rounded-lg bg-gray-50/50 dark:bg-gray-900/30 border-2 border-dashed border-gray-200 dark:border-gray-700">
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">温馨提示</p>
                <div className="text-sm text-muted-foreground space-y-1">
                  {uploadProfile.typeHintLine.trim() ? (
                    <p className="text-foreground/90 font-medium">• {uploadProfile.typeHintLine}</p>
                  ) : null}
                  <p>• 支持格式：{uploadProfile.formatsLine}</p>
                  <p>• 单次最多上传 {MAX_FILES} 个文件</p>
                  <p>• 单个文件最大 100MB</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 底部按钮 - 参考文件夹对话框的渐变按钮 */}
        <div className="px-8 py-5 border-t flex items-center justify-between shrink-0 bg-muted/30">
          <div className="text-base text-muted-foreground font-medium">
            {isUploading && <span>正在上传... {uploadedCount}/{totalCount}</span>}
            {isAttaching && <span>正在关联到知识库...</span>}
            {isAllUploaded && !isAttaching && (
              <span className="text-green-600 font-semibold">
                ✓ 上传完成 ({uploadedCount} 个{duplicateCount > 0 ? `，${duplicateCount} 个秒传` : ''})
              </span>
            )}
          </div>

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isUploading || isAttaching}
              className="h-10 px-6 text-base"
            >
              取消
            </Button>
            <Button
              onClick={handleSave}
              disabled={!isAllUploaded || totalCount === 0 || isAttaching}
              className="h-10 px-8 text-base font-semibold bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 shadow-md"
            >
              {isAttaching ? '保存中...' : '保存到知识库'}
            </Button>
          </div>
        </div>

        {/* 隐藏的文件输入 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileInputChange}
          accept={uploadProfile.accept}
        />
      </DialogContent>
    </Dialog>
  )
}
