import { useRef, useImperativeHandle, forwardRef, useEffect, useState } from 'react';
import {
    PdfLoader,
    PdfHighlighter,
    AreaHighlight,
    Highlight,
    Popup,
    type IHighlight,
} from 'react-pdf-highlighter';
import { Loader2, FileText } from 'lucide-react';
import './style.css';

// 强制指定 PDF.js Worker 路径 (Vite 兼容模式)
import * as pdfjsLib from 'pdfjs-dist';
// @ts-ignore
import PDFWorker from 'pdfjs-dist/build/pdf.worker.js?url';
pdfjsLib.GlobalWorkerOptions.workerSrc = PDFWorker;

export interface PdfPreviewerRef {
    scrollToHighlight: (highlight: IHighlight) => void;
}

interface PdfPreviewerProps {
    url: string;
    highlights?: IHighlight[];
}

/**
 * Genesis-AI 专用 PDF 预览器 (基于 RAGFlow 稳定选型)
 * 版本依赖: react-pdf-highlighter ^6.1.0, pdfjs-dist 2.16.105
 */
export const PdfPreviewer = forwardRef<PdfPreviewerRef, PdfPreviewerProps>(
    ({ url, highlights = [] }, ref) => {
        const containerRef = useRef<HTMLDivElement>(null);
        const scrollToRef = useRef<(highlight: IHighlight) => void>(() => { });
        const [isReady, setIsReady] = useState(false);
        const [currentPage, setCurrentPage] = useState(1);
        const [totalPages, setTotalPages] = useState(0);
        const [normalizedHighlights, setNormalizedHighlights] = useState<IHighlight[]>([]);
        const pdfDocumentRef = useRef<any>(null);
        const pageSizeCacheRef = useRef<Map<number, { width: number; height: number }>>(new Map());

        const _isFiniteNumber = (value: unknown): value is number =>
            typeof value === "number" && Number.isFinite(value);

        const _sanitizeRect = (rect: any, pageNumber: number, width: number, height: number) => {
            if (!rect || typeof rect !== "object") return null;
            const x1 = Number(rect.x1);
            const y1 = Number(rect.y1);
            const x2 = Number(rect.x2);
            const y2 = Number(rect.y2);
            if (![x1, y1, x2, y2].every(Number.isFinite)) return null;

            return {
                ...rect,
                x1: Math.min(x1, x2),
                y1: Math.min(y1, y2),
                x2: Math.max(x1, x2),
                y2: Math.max(y1, y2),
                pageNumber,
                width: _isFiniteNumber(width) && width > 0 ? width : 1,
                height: _isFiniteNumber(height) && height > 0 ? height : 1,
            };
        };

        // 暴露给父组件的指令方法
        useImperativeHandle(ref, () => ({
            scrollToHighlight: (highlight: IHighlight) => {
                if (scrollToRef.current) {
                    scrollToRef.current(highlight);
                }
            },
        }));

        // 使用 useEffect 更新总页数，避免在渲染期间调用 setState
        useEffect(() => {
            if (pdfDocumentRef.current && pdfDocumentRef.current.numPages !== totalPages) {
                setTotalPages(pdfDocumentRef.current.numPages);
            }
        }, [pdfDocumentRef.current, totalPages]);

        // 当前前端统一使用 COORD:BU（Bottom-Up）坐标模式，不再支持切换。
        const _convertRectToBottomUp = (rect: any, pageHeight: number) => {
            if (!rect) return rect;
            const out = { ...rect };
            const y1 = Number(out.y1);
            const y2 = Number(out.y2);
            if (!Number.isFinite(y1) || !Number.isFinite(y2)) {
                return out;
            }
            out.y1 = pageHeight - y2;
            out.y2 = pageHeight - y1;
            return out;
        };

        // 按实际页面尺寸修正高亮坐标，避免 bbox 偏移
        useEffect(() => {
            let isCancelled = false;

            const normalizeHighlights = async () => {
                if (!Array.isArray(highlights) || highlights.length === 0) {
                    if (!isCancelled) {
                        setNormalizedHighlights([]);
                    }
                    return;
                }

                const pdfDocument = pdfDocumentRef.current;
                if (!pdfDocument) {
                    if (!isCancelled) {
                        const safe = highlights.filter((h: any) => {
                            const pageNumber = Number(h?.position?.pageNumber);
                            const rect = h?.position?.boundingRect;
                            if (!Number.isFinite(pageNumber) || pageNumber < 1 || !rect) return false;
                            return !!_sanitizeRect(rect, pageNumber, Number(rect.width), Number(rect.height));
                        });
                        setNormalizedHighlights(safe);
                    }
                    return;
                }

                const pageNumbers = Array.from(
                    new Set(
                        highlights
                            .map((h: any) => Number(h?.position?.pageNumber))
                            .filter((p) => Number.isFinite(p) && p >= 1)
                    )
                ) as number[];

                const pageSizeMap = new Map<number, { width: number; height: number }>();
                await Promise.all(
                    pageNumbers.map(async (pageNumber) => {
                        const cached = pageSizeCacheRef.current.get(pageNumber);
                        if (cached) {
                            pageSizeMap.set(pageNumber, cached);
                            return;
                        }
                        try {
                            const page = await pdfDocument.getPage(pageNumber);
                            const viewport = page.getViewport({ scale: 1 });
                            const size = { width: viewport.width, height: viewport.height };
                            pageSizeMap.set(pageNumber, size);
                            pageSizeCacheRef.current.set(pageNumber, size);
                        } catch {
                            // ignore single page sizing failure
                        }
                    })
                );

                const next = highlights.map((h: any) => {
                    const pageNumber = Number(h?.position?.pageNumber);
                    const size = pageSizeMap.get(pageNumber);
                    const rect = h?.position?.boundingRect;
                    if (!size || !rect) return null;

                    const normalizedRectBase = _sanitizeRect(rect, pageNumber, size.width, size.height);
                    if (!normalizedRectBase) return null;
                    const normalizedRect = _convertRectToBottomUp(normalizedRectBase, size.height);
                    const normalizedRects = Array.isArray(h?.position?.rects) && h.position.rects.length > 0
                        ? h.position.rects
                            .map((r: any) => _sanitizeRect(r, pageNumber, size.width, size.height))
                            .filter(Boolean)
                            .map((r: any) => _convertRectToBottomUp(r, size.height))
                        : [normalizedRect];
                    if (!Array.isArray(normalizedRects) || normalizedRects.length === 0) return null;

                    return {
                        ...h,
                        position: {
                            ...h.position,
                            pageNumber,
                            usePdfCoordinates: true,
                            boundingRect: normalizedRect,
                            rects: normalizedRects,
                        },
                    };
                }).filter(Boolean) as IHighlight[];

                if (!isCancelled) {
                    setNormalizedHighlights(next);
                }
            };

            normalizeHighlights();
            return () => {
                isCancelled = true;
            };
        }, [highlights, isReady, totalPages]);

        // 自动跳转到第一个高亮块 (如果存在且格式正确)
        useEffect(() => {
            if (!isReady || !Array.isArray(normalizedHighlights) || normalizedHighlights.length === 0) return;
            const first = normalizedHighlights[0];
            if (!first?.position?.boundingRect) return;

            let cancelled = false;
            const timer = setTimeout(() => {
                if (cancelled) return;
                try {
                    // 避免切换视图时 PdfHighlighter 内部尚未准备好导致异常中断页面
                    scrollToRef.current(first);
                } catch {
                    // ignore scroll failure
                }
            }, 0);

            return () => {
                cancelled = true;
                clearTimeout(timer);
            };
        }, [isReady, normalizedHighlights]);

        // 使用 IntersectionObserver 监听当前在视口中的页码
        useEffect(() => {
            if (!isReady || !containerRef.current) return;

            const observerOptions = {
                root: containerRef.current.querySelector('.PdfHighlighter__pdfviewer'),
                threshold: 0.1, // 只要进入 10% 就算可见
            };

            const handleIntersection = (entries: IntersectionObserverEntry[]) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const pageNum = entry.target.getAttribute('data-page-number');
                        if (pageNum) {
                            setCurrentPage(parseInt(pageNum, 10));
                        }
                    }
                });
            };

            const observer = new IntersectionObserver(handleIntersection, observerOptions);

            // 延迟一点点等待 PdfHighlighter 渲染完成
            const timer = setTimeout(() => {
                const pages = containerRef.current?.querySelectorAll('.page');
                pages?.forEach((page) => observer.observe(page));
            }, 1000);

            return () => {
                observer.disconnect();
                clearTimeout(timer);
            };
        }, [isReady]);

        return (
            <div
                ref={containerRef}
                className="pdf-previewer-container h-full w-full bg-slate-100 dark:bg-slate-900 overflow-hidden relative"
            >
                {/* 页码悬浮指示器 */}
                {totalPages > 0 && (
                    <div className="pdf-pagination-indicator">
                        <FileText className="w-3 h-3 text-sky-400" />
                        <span className="current-page">{currentPage}</span>
                        <span className="total-pages">/ {totalPages}</span>
                    </div>
                )}

                <PdfLoader
                    url={url}
                    beforeLoad={
                        <div className="flex flex-col items-center justify-center p-20 gap-3">
                            <Loader2 className="h-8 w-8 animate-spin text-primary/40" />
                            <p className="text-xs text-muted-foreground animate-pulse">
                                RAG 引擎正在解析文档结构...
                            </p>
                        </div>
                    }
                >
                    {(pdfDocument) => {
                        // 保存 pdfDocument 引用，在 useEffect 中更新总页数
                        pdfDocumentRef.current = pdfDocument;

                        return (
                            <PdfHighlighter
                                pdfDocument={pdfDocument}
                                enableAreaSelection={(event) => event.altKey}
                                onScrollChange={() => { }}
                                scrollRef={(scrollTo) => {
                                    scrollToRef.current = scrollTo;
                                    setIsReady((prev) => prev || true);
                                }}
                                onSelectionFinished={() => null}
                                highlightTransform={(
                                    highlight,
                                    index,
                                    setTip,
                                    hideTip,
                                    _viewportToScaled,
                                    _screenshot,
                                    isScrolledTo
                                ) => {
                                    // 防御性检查：如果数据格式不空或不标准，直接跳过渲染该高亮块
                                    if (!highlight || !highlight.position || !highlight.position.boundingRect) {
                                        return <div key={index} />;
                                    }

                                    const isAreaHighlight = !!(highlight.content && highlight.content.image);

                                    const component = isAreaHighlight ? (
                                        <AreaHighlight
                                            isScrolledTo={isScrolledTo}
                                            highlight={highlight}
                                            onChange={() => { }}
                                        />
                                    ) : (
                                        <Highlight
                                            isScrolledTo={isScrolledTo}
                                            position={highlight.position}
                                            comment={highlight.comment || { text: '', emoji: '' }}
                                        />
                                    );

                                    return (
                                        <Popup
                                            popupContent={
                                                <div className="bg-slate-900 text-white p-2 rounded-md shadow-xl text-[10px] border border-slate-700 animate-in fade-in zoom-in duration-200">
                                                    {highlight.comment?.text || (isAreaHighlight ? '区域高亮' : '文本片段')}
                                                </div>
                                            }
                                            onMouseOver={(popupContent) =>
                                                setTip(highlight, () => popupContent)
                                            }
                                            onMouseOut={hideTip}
                                            key={index}
                                        >
                                            {component}
                                        </Popup>
                                    );
                                }}
                                highlights={normalizedHighlights}
                            />
                        );
                    }}
                </PdfLoader>
            </div>
        );
    }
);

PdfPreviewer.displayName = 'PdfPreviewer';
