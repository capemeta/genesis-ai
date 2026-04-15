/**
 * 文档预览类型定义
 */

/**
 * 文档预览模式
 */
export type PreviewMode = 'source' | 'parsed';

/**
 * 源文件类型
 */
export type SourceFileType =
  | 'word' // .doc, .docx
  | 'pdf' // .pdf
  | 'excel' // .xls, .xlsx
  | 'ppt' // .ppt, .pptx
  | 'image' // .jpg, .png, .gif, etc.
  | 'text' // .txt, .md
  | 'csv' // .csv
  | 'json' // .json
  | 'html' // .html
  | 'unknown'; // 未知类型

/**
 * 解析内容类型
 */
export type ParsedContentType =
  | 'markdown' // Markdown 格式
  | 'json' // JSON 格式
  | 'html' // HTML 格式
  | 'text' // 纯文本
  | 'none'; // 无解析内容

/**
 * 文档预览配置
 */
export interface DocumentPreviewConfig {
  kbDocId: string;
  fileName: string;
  fileExtension: string;

  // 源文件信息
  sourceFileType: SourceFileType;
  sourceDocumentId?: string;

  // 解析内容信息
  parsedContentType: ParsedContentType;
  markdownDocumentId?: string;

  // 能力标识
  hasSourcePreview: boolean; // 是否支持源文件预览
  hasParsedPreview: boolean; // 是否支持解析视图
}

/**
 * 查看器组件 Props
 */
export interface ViewerProps {
  documentId: string;
  fileName: string;
  onError?: (error: Error) => void;
}

/**
 * Markdown 预览响应
 */
export interface MarkdownPreviewResponse {
  has_markdown: boolean;
  markdown_content?: string;
  markdown_document_id?: string;
  file_name?: string;
  file_size?: number;
  created_at?: string;
  message?: string;
}
