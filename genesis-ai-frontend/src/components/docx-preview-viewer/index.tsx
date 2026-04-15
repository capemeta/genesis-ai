/**
 * Word (.docx) 预览组件
 *
 * 基于 docx-preview 实现
 *
 * 使用方式：
 *   <DocxPreview blob={blob} fileName="xxx.docx" />
 */

import { useEffect, useRef } from 'react'
import { renderAsync } from 'docx-preview'

export interface DocxPreviewProps {
    /** 文档 Blob（来自 fetchDocumentRaw 等） */
    blob: Blob
    /** 文件名 */
    fileName: string
    /** 根节点 className */
    className?: string
    /** 根节点 style */
    style?: React.CSSProperties
}

// ============ 实现：docx-preview ============

export function DocxPreview({
    blob,
    className,
    style,
}: DocxPreviewProps) {
    const containerRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!blob || !containerRef.current) return
        const el = containerRef.current
        renderAsync(blob, el, undefined, {
            className: 'docx-preview-output',
            inWrapper: true,
            ignoreWidth: false,
            ignoreHeight: false,
            breakPages: true,
            renderHeaders: true,
            renderFooters: true,
            renderFootnotes: true,
            renderEndnotes: true,
            experimental: true,
            debug: false,
            // 尝试使用更好的分页算法
            useBase64URL: false,
            renderChanges: false,
            renderComments: false,
        }).catch((err) => {
            console.error('Word 预览加载失败 (docx-preview):', err)
        })
    }, [blob])

    return (
        <div
            className={`docx-preview-root overflow-x-auto ${className ?? ''}`}
            style={style}
        >
            {/* 预览限制提示 */}
            <div className="bg-amber-50 border-l-4 border-amber-400 p-3 mb-4 mx-6 mt-6">
                <div className="flex items-start">
                    <svg className="h-5 w-5 text-amber-400 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <div className="text-sm text-amber-700">
                        <p className="font-medium">预览限制说明</p>
                        <p className="mt-1">由于浏览器渲染限制，Word 文档预览可能存在以下问题：页码显示不准确、分页位置偏移、复杂格式丢失。如需查看完整格式，请下载原文件。</p>
                    </div>
                </div>
            </div>
            
            <div
                ref={containerRef}
                className="w-full"
                style={{ fontFamily: 'initial', color: '#333' }}
            />
            <style
                dangerouslySetInnerHTML={{
                    __html: `
                    .docx-preview-root .docx-wrapper {
                        background: transparent !important;
                        padding: 24px !important;
                    }
                    .docx-preview-root section.docx {
                        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1) !important;
                        margin-bottom: 24px !important;
                    }
                `,
                }}
            />
        </div>
    )
}
