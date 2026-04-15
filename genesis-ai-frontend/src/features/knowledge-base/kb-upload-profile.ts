/**
 * 按知识库类型的上传 UI 与校验（与后端 attach 预检一致：
 * - table：xlsx / xls / csv
 * - qa：xlsx / csv（不含 xls）
 * - 其余类型按通用文档处理）
 */

export interface KbUploadProfile {
  /** 弹窗副标题 */
  dialogDescription: string
  /** input accept 属性 */
  accept: string
  /** 小写、带点，用于拖拽/选择后的扩展名校验 */
  allowedExtensions: string[]
  /** 拖拽区底部格式角标 */
  formatTags: string[]
  /** 「温馨提示」中支持格式那一行的中文说明 */
  formatsLine: string
  /** 类型提示行（置于温馨提示最前；空则整行不展示） */
  typeHintLine: string
}

const GENERAL: KbUploadProfile = {
  dialogDescription:
    '当前为通用文档知识库，支持 PDF、Word、Excel、PPT、TXT、Markdown、CSV 等常见格式（以解析流水线能力为准）。',
  accept: '.pdf,.docx,.txt,.md,.xlsx,.xls,.ppt,.pptx,.csv',
  allowedExtensions: ['.pdf', '.docx', '.txt', '.md', '.xlsx', '.xls', '.ppt', '.pptx', '.csv'],
  formatTags: ['PDF', 'DOCX', 'XLSX', 'PPT', 'TXT', 'MD', 'CSV'],
  /** Word 仅 .docx：后端 BasicParser 不支持旧版 .doc */
  formatsLine: 'PDF、Word（.docx）、Excel（.xlsx/.xls）、PPT、TXT、Markdown、CSV',
  typeHintLine: '当前知识库类型：通用文档 — 按办公与文本类文件导入。',
}

const TABLE: KbUploadProfile = {
  /** 规则见顶部提示区，此处不再重复副标题 */
  dialogDescription: '',
  accept: '.xlsx,.xls,.csv',
  allowedExtensions: ['.xlsx', '.xls', '.csv'],
  formatTags: ['XLSX', 'XLS', 'CSV'],
  formatsLine: '仅 Excel（.xlsx / .xls）与 CSV',
  typeHintLine: '',
}

const QA: KbUploadProfile = {
  /** 规则见顶部提示区 */
  dialogDescription: '',
  accept: '.xlsx,.csv',
  allowedExtensions: ['.xlsx', '.csv'],
  formatTags: ['XLSX', 'CSV'],
  formatsLine: '仅 Excel（.xlsx）与 CSV（不支持 .xls）',
  typeHintLine: '',
}

/** 非 table/qa 时沿用通用扩展名，但文案带出真实知识库类型名 */
const NON_TABLE_QA_LABELS: Record<string, string> = {
  general: '通用文档',
  web: '网页同步',
  media: '音视频转录',
  connector: '同步应用',
}

function profileForNonTableQa(kbType: string | undefined): KbUploadProfile {
  const label = NON_TABLE_QA_LABELS[kbType ?? 'general'] ?? NON_TABLE_QA_LABELS.general
  return {
    ...GENERAL,
    dialogDescription: `当前为「${label}」知识库；上传本地文件时支持 ${GENERAL.formatsLine}（以解析流水线能力为准）。`,
    typeHintLine: `当前知识库类型：${label} — 与 QA / 结构化表格 专用库不同，允许常见办公与文本类文件。`,
  }
}

export function getKbUploadProfile(kbType: string | undefined): KbUploadProfile {
  switch (kbType) {
    case 'table':
      return TABLE
    case 'qa':
      return QA
    case 'general':
      return GENERAL
    default:
      return profileForNonTableQa(kbType)
  }
}

/** 从文件名判断是否允许上传 */
export function filterFilesByKbProfile(
  files: File[],
  profile: KbUploadProfile
): { allowed: File[]; rejected: File[] } {
  const allowed: File[] = []
  const rejected: File[] = []
  for (const file of files) {
    const lower = file.name.toLowerCase()
    const ok = profile.allowedExtensions.some((ext) => lower.endsWith(ext))
    if (ok) allowed.push(file)
    else rejected.push(file)
  }
  return { allowed, rejected }
}
