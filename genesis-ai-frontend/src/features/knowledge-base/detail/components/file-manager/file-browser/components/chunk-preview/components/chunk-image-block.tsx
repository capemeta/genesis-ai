import { cn } from '@/lib/utils'
import { ImageViewer } from '@/components/image-viewer'
import type { ChunkPreviewRecord } from '../types'
import {
  normalizeImageAnalysis,
  resolveImageBlockType,
  IMAGE_TYPE_BADGE_CONFIG,
} from '../lib/image'

// ============================================================
// ChunkImageBlock - 图片块渲染（缩略图 + 类型徽章 + 字幕）
// ============================================================

interface ChunkImageBlockProps {
  /** 图片 URL */
  src: string
  /** alt 文本（fallback） */
  alt?: string
  /** 对应的 content_block 元数据（含 source/modality/caption/vision_text） */
  blockMeta?: ChunkPreviewRecord
  /**
   * chunk.metadata_info.parser（"mineru" / "docling" / "native" 等）
   * 用于兼容旧数据：当 blockMeta 中无 source 字段时，通过 chunk 级别的 parser 推断 OCR 类型
   */
  chunkParser?: string
  /**
   * compact 模式：用于 markdown 行内图片，缩略图更小，不占整行
   * full 模式：用于独立 IMAGE 类型 chunk，居中展示，更宽松
   */
  variant?: 'compact' | 'full'
}

/**
 * 统一的图片块渲染组件
 *
 * - compact: 内联于文本流中，缩略图高度约 144px，左对齐
 * - full: 独立图片 chunk，缩略图高度约 200px，居中展示
 *
 * 点击缩略图会通过 ImageViewer 弹出全屏查看器（支持缩放/旋转/拖拽）。
 * 通过 blockMeta.source 或 chunkParser 自动推断图片类型徽章：
 * - "mineru"/"docling"/"ocr" → OCR识别（琥珀色）
 * - vision_text → AI视觉（紫色）
 * - 有 caption → 图文（蓝色）
 * - 其他 → 图片（灰色）
 */
export function ChunkImageBlock({
  src,
  alt,
  blockMeta,
  chunkParser,
  variant = 'full',
}: ChunkImageBlockProps) {
  const imageType = resolveImageBlockType(blockMeta, chunkParser)
  const badgeConfig = IMAGE_TYPE_BADGE_CONFIG[imageType]
  const imageAnalysis = normalizeImageAnalysis(blockMeta)

  const captionLines: string[] = imageAnalysis.caption
  const captionText = captionLines.join(' ')

  const extractedText: string =
    imageAnalysis.visionText || imageAnalysis.ocrText || ''

  const isCompact = variant === 'compact'

  return (
    <span
      className={cn(
        'inline-flex flex-col gap-1.5 rounded-lg',
        isCompact ? 'my-1' : 'my-2'
      )}
    >
      {/* 缩略图容器：相对定位，用于叠加徽章 */}
      <span className='relative inline-block'>
        {/* 图片类型徽章 - 左上角浮层 */}
        <span
          className={cn(
            'absolute top-1.5 left-1.5 z-10 inline-flex items-center gap-0.5 rounded-full border px-1.5 py-0.5 text-[10px] leading-none font-semibold select-none',
            badgeConfig.className
          )}
        >
          <span className='text-[8px]'>{badgeConfig.icon}</span>
          {badgeConfig.label}
        </span>

        <ImageViewer
          src={src}
          alt={alt || captionText || '图片'}
          className={cn(
            'rounded-lg border',
            isCompact ? 'max-w-[220px]' : 'max-w-sm'
          )}
          imgClassName={cn(
            'object-contain',
            isCompact ? 'max-h-36' : 'max-h-52'
          )}
        />
      </span>

      {/* 字幕文本（图注）*/}
      {captionText && (
        <span className='max-w-sm px-0.5 text-[11px] leading-relaxed text-muted-foreground italic'>
          {captionText}
        </span>
      )}

      {/* OCR / 视觉理解提取文本 */}
      {extractedText && (
        <span className='block max-w-sm rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs leading-relaxed whitespace-pre-wrap text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400'>
          {extractedText}
        </span>
      )}
    </span>
  )
}
