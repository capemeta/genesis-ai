/**
 * 文件类型图标：根据文件名/扩展名返回 public/icons/file-types 下对应图标的 URL。
 * - 图片类：png/gif/jpg 用对应图标，其它图片格式用 icon_image.svg
 * - 非图片类：有对应图标则用；html/htm 使用 icon-web-url.svg；否则用 icon_file_unkown.svg
 */

import { withAppAssetPath } from '@/lib/app-base'

const ICON_BASE = withAppAssetPath('icons/file-types')

/** 暂无文件时的空状态图标 */
export const NO_FILE_ICON_URL = `${ICON_BASE}/icon_no_file.svg`

/** 有独立图标的图片扩展名（png/gif/jpg 用各自图标） */
const IMAGE_EXT_WITH_ICON = new Set(['png', 'gif', 'jpg', 'jpeg'])

/** 视为图片的扩展名（无独立图标时用 icon_image.svg） */
const IMAGE_EXTENSIONS = new Set([
  ...IMAGE_EXT_WITH_ICON,
  'webp', 'bmp', 'svg', 'ico', 'tiff', 'tif', 'heic', 'avif',
])

/** 扩展名 → 图标文件名（不含 .svg） */
const EXT_TO_ICON: Record<string, string> = {
  // 文档
  pdf: 'icon_pdf',
  doc: 'icon_word',
  docx: 'icon_word',
  xls: 'icon_excel',
  xlsx: 'icon_excel',
  ppt: 'icon_ppt',
  pptx: 'icon_ppt',
  txt: 'icon_txt',
  md: 'icon_markdown',
  html: 'icon-web-url',
  htm: 'icon-web-url',
  csv: 'icon_csv',
  json: 'icon_json',
  zip: 'icon_zip',
  // 图片（有独立图标的）
  png: 'icon_png',
  gif: 'icon_gif',
  jpg: 'icon_jpg',
  jpeg: 'icon_jpg',
  // 音视频
  mp3: 'icon_sound',
  wav: 'icon_sound',
  ogg: 'icon_sound',
  m4a: 'icon_sound',
  flac: 'icon_sound',
  mp4: 'icon_video',
  webm: 'icon_video',
  mov: 'icon_video',
  avi: 'icon_video',
  mkv: 'icon_video',
}

/**
 * 根据文件名或 MIME 类型获取文件类型图标的 URL。
 * @param fileName 文件名（如 "report.pdf"）或仅扩展名
 * @param mimeType 可选，MIME 类型（如 "application/pdf"），用于无扩展名时推断
 * @param logicalFileType 可选，后端 file_type（如 "HTML"），无扩展名且未传 mime 时用于 HTML 等补全
 * @returns 图标 URL，如 "/icons/file-types/icon_pdf.svg"
 */
export function getFileTypeIconUrl(
  fileName: string,
  mimeType?: string,
  logicalFileType?: string
): string {
  const ext = getExtension(fileName).toLowerCase()
  const isImageExt = IMAGE_EXTENSIONS.has(ext)

  if (ext) {
    const iconName = EXT_TO_ICON[ext]
    if (iconName) return `${ICON_BASE}/${iconName}.svg`
    // 图片类但无独立图标（如 webp）→ 默认图片图标
    if (isImageExt) return `${ICON_BASE}/icon_image.svg`
  }

  const effectiveMime =
    mimeType?.trim() ||
    (/^html$/i.test(String(logicalFileType ?? '').trim()) ? 'text/html' : '')

  // 无扩展名或未知扩展名时可用 MIME / 逻辑类型推断
  if (effectiveMime) {
    const lower = effectiveMime.toLowerCase()
    if (lower.startsWith('image/')) return `${ICON_BASE}/icon_image.svg`
    if (lower.includes('pdf')) return `${ICON_BASE}/icon_pdf.svg`
    // 须在通用 text/* 判断之前，否则 text/html 会落到 icon_txt
    if (lower.includes('text/html')) return `${ICON_BASE}/icon-web-url.svg`
    if (lower.includes('word') || lower.includes('document')) return `${ICON_BASE}/icon_word.svg`
    if (lower.includes('sheet') || lower.includes('excel')) return `${ICON_BASE}/icon_excel.svg`
    if (lower.includes('presentation') || lower.includes('powerpoint')) return `${ICON_BASE}/icon_ppt.svg`
    if (lower.includes('text') || lower.includes('markdown')) return `${ICON_BASE}/icon_txt.svg`
    if (lower.includes('json')) return `${ICON_BASE}/icon_json.svg`
    if (lower.includes('csv')) return `${ICON_BASE}/icon_csv.svg`
    if (lower.includes('zip') || lower.includes('compressed')) return `${ICON_BASE}/icon_zip.svg`
    if (lower.startsWith('audio/')) return `${ICON_BASE}/icon_sound.svg`
    if (lower.startsWith('video/')) return `${ICON_BASE}/icon_video.svg`
  }

  return `${ICON_BASE}/icon_file_unkown.svg`
}

function getExtension(fileName: string): string {
  if (!fileName || !fileName.includes('.')) return ''
  const last = fileName.split('.').pop()
  return last ?? ''
}
