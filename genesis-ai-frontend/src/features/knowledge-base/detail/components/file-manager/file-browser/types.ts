export interface ParseAttempt {
    attempt: number
    started_at: string
    ended_at: string | null
    status: 'completed' | 'failed' | 'cancelled' | 'processing' | 'interrupted'
    error?: string
    duration_ms?: number
    logs: Array<{
        step: string
        message: string
        time: string
        status: string
    }>
}

export interface FileItem {
    id: string
    name: string
    type: 'PDF' | 'Markdown' | 'TXT' | 'DOCX' | 'XLSX' | 'PPTX'
    size: string
    chunks: number
    status: 'Completed' | 'Processing' | 'Queued' | 'Failed' | 'Pending' | 'Cancelled' | 'Cancelling' | 'SyncedChunking'
    uploadTime: string
    startTime?: string
    duration?: string
    enabled: boolean
    tags: string[]
    creator?: string
    parsingLogs?: ParseAttempt[]  // 修改为新的结构
    progress?: number
    parseError?: string
    runtimeModels?: Record<string, {
        tenant_model_id?: string
        provider_code?: string
        raw_model_name?: string
        display_name?: string
        capability_type?: string
    }>
    runtimeUpdatedAt?: string
    chunkConfig?: ChunkConfig
    metadata?: Record<string, unknown>
    intelligenceConfig?: Record<string, any>
    markdown_document_id?: string | null  // 🟢 新增：中间转换后的 Markdown 文档 ID（用于预览）
    // 文件夹信息
    folderId?: string | null
    folderName?: string
    folderPath?: string // 完整路径，如 "文件夹1/文件夹2"
    folderLevel?: number // 层级深度，用于缩进显示
    folderPathArray?: Array<{  // 路径数组（包含每一级的 ID 和名称）
        id: string
        name: string
        level: number
    }>
    sourceType?: string
    assetKind?: string
    isVirtualFile?: boolean
    contentKind?: string
    canDownloadSourceFile?: boolean
}

// 标签定义与 resource_tags（kb_doc/folder）语义一致，从共享类型复用
export type { TagDefinition } from '../shared/tag-types'

export interface ChunkConfig {
    chunkSize: number
    chunkOverlap: number
    separators: string
    chunkMethod: 'fixed' | 'semantic' | 'recursive'
}

export interface MetadataField {
    key: string
    value: string
    readonly?: boolean
}
