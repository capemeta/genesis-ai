/**
 * 文档预览工具函数
 */

import type {
  DocumentPreviewConfig,
  SourceFileType,
  ParsedContentType,
} from './types'

interface PreviewKnowledgeBaseDocument {
  id: string
  document_id?: string
  markdown_document_id?: string | null
}

/**
 * 根据文件扩展名获取源文件类型
 */
export function getSourceFileType(extension: string): SourceFileType {
  const ext = extension.toLowerCase()
  const typeMap: Record<string, SourceFileType> = {
    doc: 'word',
    docx: 'word',
    pdf: 'pdf',
    xls: 'excel',
    xlsx: 'excel',
    ppt: 'ppt',
    pptx: 'ppt',
    jpg: 'image',
    jpeg: 'image',
    png: 'image',
    gif: 'image',
    webp: 'image',
    txt: 'text',
    md: 'text',
    csv: 'csv',
    json: 'json',
    html: 'html',
    htm: 'html',
  }
  return typeMap[ext] || 'unknown'
}

/**
 * 检查源文件类型是否支持预览
 */
export function isSourcePreviewSupported(type: SourceFileType): boolean {
  // 当前支持的类型
  return ['word', 'pdf', 'excel', 'csv', 'text', 'image'].includes(type)

  // 未来扩展：
  // return ['word', 'pdf', 'excel', 'text', 'image'].includes(type);
}

/**
 * 获取文件类型的显示标签
 */
export function getFileTypeLabel(type: SourceFileType): string {
  const labels: Record<SourceFileType, string> = {
    word: 'Word',
    pdf: 'PDF',
    excel: 'Excel',
    ppt: 'PPT',
    image: '图片',
    text: '文本',
    csv: 'CSV',
    json: 'JSON',
    html: 'HTML',
    unknown: '未知',
  }
  return labels[type]
}

/**
 * 生成文档预览配置
 */
export function getDocumentPreviewConfig(
  fileName: string,
  kbDoc: PreviewKnowledgeBaseDocument
): DocumentPreviewConfig {
  const extension = fileName.split('.').pop()?.toLowerCase() || ''
  const sourceFileType = getSourceFileType(extension)
  const parsedContentType: ParsedContentType = kbDoc.markdown_document_id
    ? 'markdown'
    : 'none'

  return {
    kbDocId: kbDoc.id,
    fileName,
    fileExtension: extension,
    sourceFileType,
    sourceDocumentId: kbDoc.document_id,
    parsedContentType,
    markdownDocumentId: kbDoc.markdown_document_id ?? undefined,
    hasSourcePreview: isSourcePreviewSupported(sourceFileType),
    hasParsedPreview: parsedContentType !== 'none',
  }
}
