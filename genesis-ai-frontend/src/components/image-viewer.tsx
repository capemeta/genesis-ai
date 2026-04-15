import * as React from 'react'
import {
    RotateCw,
    RotateCcw,
    Download,
    X,
    RefreshCcw,
    Minus,
    Plus,
    Maximize2,
} from 'lucide-react'
import {
    Dialog,
    DialogContent,
    DialogTrigger,
    DialogClose,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ImageViewerProps {
    src: string
    alt?: string
    trigger?: React.ReactNode
    className?: string
    /** 应用于触发器内缩略图 <img> 的额外 CSS class，用于约束缩略图尺寸 */
    imgClassName?: string
}

export function ImageViewer({ src, alt, trigger, className, imgClassName }: ImageViewerProps) {
    const [scale, setScale] = React.useState(1)
    const [rotate, setRotate] = React.useState(0)
    const [offset, setOffset] = React.useState({ x: 0, y: 0 })
    const [isDragging, setIsDragging] = React.useState(false)
    const [startPos, setStartPos] = React.useState({ x: 0, y: 0 })

    const imgRef = React.useRef<HTMLImageElement>(null)

    // 重置状态
    const handleReset = () => {
        setScale(1)
        setRotate(0)
        setOffset({ x: 0, y: 0 })
    }

    // 放大
    const handleZoomIn = () => setScale((s) => Math.min(s + 0.2, 5))
    // 缩小
    const handleZoomOut = () => setScale((s) => Math.max(s - 0.2, 0.5))
    // 旋转
    const handleRotateCw = () => setRotate((r) => r + 90)
    const handleRotateCcw = () => setRotate((r) => r - 90)

    // 处理滚轮缩放
    const handleWheel = (e: React.WheelEvent) => {
        if (e.deltaY < 0) {
            handleZoomIn()
        } else {
            handleZoomOut()
        }
    }

    // 处理拖拽
    const handleMouseDown = (e: React.MouseEvent) => {
        if (scale <= 1) return
        e.preventDefault()
        setIsDragging(true)
        setStartPos({ x: e.clientX - offset.x, y: e.clientY - offset.y })
    }

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDragging) return
        setOffset({
            x: e.clientX - startPos.x,
            y: e.clientY - startPos.y,
        })
    }

    const handleMouseUp = () => {
        setIsDragging(false)
    }

    // 下载图片
    const handleDownload = async () => {
        try {
            const response = await fetch(src)
            const blob = await response.blob()
            const blobUrl = window.URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = blobUrl
            link.download = alt ? `${alt}.png` : 'image.png'
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            window.URL.revokeObjectURL(blobUrl)
        } catch (error) {
            console.error('Download failed:', error)
            // 备选方案：通过新标签页打开
            window.open(src, '_blank')
        }
    }

    return (
        <Dialog onOpenChange={(open) => !open && handleReset()}>
            <DialogTrigger asChild>
                {trigger || (
                    <span
                        className={cn(
                            "group relative cursor-pointer overflow-hidden rounded-lg border bg-muted/50 transition-all hover:border-primary/50 hover:shadow-md inline-block",
                            className
                        )}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* 图片本身 */}
                        <img
                            src={src}
                            alt={alt || 'Image'}
                            className={cn(
                                "max-w-full h-auto object-contain block transition-transform duration-500 group-hover:scale-[1.02]",
                                imgClassName
                            )}
                        />

                        {/* 悬浮提示层 */}
                        <span className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300 flex items-center justify-center">
                            <span className="opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-300">
                                <span className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-md p-2 rounded-full shadow-lg border border-white/20 flex items-center justify-center">
                                    <Maximize2 className="w-5 h-5 text-primary" />
                                </span>
                            </span>
                        </span>

                        {/* 角标提示 */}
                        <span className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            <span className="bg-black/20 backdrop-blur-sm px-1.5 py-0.5 rounded text-[10px] text-white font-medium flex items-center gap-1">
                                <span>点击预览</span>
                            </span>
                        </span>
                    </span>
                )}
            </DialogTrigger>
            <DialogContent
                showCloseButton={false}
                className="p-0 overflow-hidden bg-white/98 dark:bg-slate-900/98 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl z-[100] sm:max-w-none shadow-[0_32px_64px_-12px_rgba(0,0,0,0.14)]"
                style={{
                    width: '80vw',
                    maxWidth: '80vw',
                    height: '85vh',
                    maxHeight: '85vh'
                }}
            >
                {/* 隐藏的标题和描述 */}
                <div className="sr-only">
                    <DialogTitle>{alt || '图片预览'}</DialogTitle>
                    <DialogDescription>支持缩放、旋转和拖拽查看图片详情</DialogDescription>
                </div>

                <div
                    className="relative flex h-full w-full flex-col overflow-hidden"
                    onWheel={handleWheel}
                >
                    {/* 顶部栏: 标题 + 信息 + 关闭按钮 */}
                    <div className="relative z-50 flex h-20 w-full shrink-0 items-center justify-between px-8 bg-white/50 backdrop-blur-sm border-b border-slate-100 dark:bg-slate-900/50 dark:border-slate-800">
                        <div className="flex flex-col gap-0.5">
                            <span className="text-slate-900 dark:text-slate-100 text-base font-bold tracking-tight">{alt || '图片预览'}</span>
                            <div className="flex items-center gap-2.5">
                                <span className="text-slate-500 text-[11px] font-bold font-mono bg-slate-100 dark:bg-slate-800 dark:text-slate-400 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700">Zoom: {Math.round(scale * 100)}%</span>
                                <span className="text-slate-500 text-[11px] font-bold font-mono bg-slate-100 dark:bg-slate-800 dark:text-slate-400 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700">Rotate: {rotate}°</span>
                            </div>
                        </div>

                        <div className="flex items-center">
                            <DialogClose asChild>
                                <Button variant="ghost" size="icon" className="h-10 w-10 text-slate-400 hover:text-slate-900 hover:bg-slate-100 rounded-full transition-all dark:text-slate-500 dark:hover:text-slate-100 dark:hover:bg-slate-800">
                                    <X className="h-6 w-6" />
                                </Button>
                            </DialogClose>
                        </div>
                    </div>

                    {/* 中间图片区域 */}
                    <div
                        className="relative flex-1 w-full overflow-hidden flex items-center justify-center p-4"
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        {/* 背景装饰 - 亮色点阵 */}
                        <div className="absolute inset-0 z-0 opacity-[0.03] dark:opacity-[0.05]"
                            style={{
                                backgroundImage: 'radial-gradient(circle, #000 1.2px, transparent 1.2px)',
                                backgroundSize: '40px 40px'
                            }}
                        />

                        {/* 图片容器 */}
                        <div
                            className={cn(
                                "relative z-10 transition-transform duration-200 ease-out flex items-center justify-center",
                                isDragging ? "cursor-grabbing" : scale > 1 ? "cursor-grab" : "cursor-auto"
                            )}
                            style={{
                                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale}) rotate(${rotate}deg)`,
                            }}
                            onMouseDown={handleMouseDown}
                        >
                            <img
                                ref={imgRef}
                                src={src}
                                alt={alt}
                                className="max-h-[55vh] max-w-[70vw] object-contain select-none shadow-[0_20px_50px_rgba(0,0,0,0.1)]"
                                draggable={false}
                            />
                        </div>
                    </div>

                    {/* 底部悬浮工具栏区 - 固定高度 */}
                    <div className="relative h-28 w-full shrink-0 flex items-center justify-center z-50">
                        <div className="p-2 rounded-2xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-2xl border border-slate-200 dark:border-slate-700 flex items-center gap-1 shadow-[0_10px_40px_rgba(0,0,0,0.08)]">
                            <TooltipLightButton onClick={handleZoomOut} icon={<Minus className="h-4 w-4" />} label="缩小" />
                            <div className="px-3 text-slate-600 dark:text-slate-300 text-xs font-bold font-mono min-w-[3.5rem] text-center select-none">
                                {Math.round(scale * 100)}%
                            </div>
                            <TooltipLightButton onClick={handleZoomIn} icon={<Plus className="h-4 w-4" />} label="放大" />

                            <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-2" />

                            <TooltipLightButton onClick={handleRotateCcw} icon={<RotateCcw className="h-4 w-4" />} label="逆时针旋转" />
                            <TooltipLightButton onClick={handleRotateCw} icon={<RotateCw className="h-4 w-4" />} label="顺时针旋转" />

                            <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-2" />

                            <TooltipLightButton onClick={handleReset} icon={<RefreshCcw className="h-4 w-4" />} label="重置" />
                            <TooltipLightButton onClick={handleDownload} icon={<Download className="h-4 w-4" />} label="保存图片" />
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}

function TooltipLightButton({ onClick, icon, label }: { onClick: () => void, icon: React.ReactNode, label: string }) {
    return (
        <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-700 rounded-xl transition-all"
            onClick={(e) => {
                e.stopPropagation()
                onClick()
            }}
            title={label}
        >
            {icon}
        </Button>
    )
}
