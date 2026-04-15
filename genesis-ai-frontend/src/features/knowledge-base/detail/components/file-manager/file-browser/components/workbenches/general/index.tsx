import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { fetchKnowledgeBase, updateKnowledgeBase } from '@/lib/api/knowledge-base'
import { DEFAULT_CHUNKING_CONFIG } from '@/features/knowledge-base/detail/components/shared-config/constants'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import { FileBrowser } from '@/features/knowledge-base/detail/components/file-manager'
import { ChunkingConfigSection } from './components/chunking-config-section'
import { PdfParserSection } from './components/pdf-parser-section'

export type GeneralWorkbenchView = 'files' | 'general-parsing'

interface GeneralWorkbenchProps {
  kbId: string
  view: GeneralWorkbenchView
  selectedFolderId: string | null
  onFolderChange: (folderId: string | null) => void
  isFolderTreeCollapsed?: boolean
  onToggleFolderTree?: () => void
  onSetFolderTreeCollapsed?: (collapsed: boolean) => void
}

function buildParsingConfig(kb: any): ConfigState {
  return {
    type: kb.type,
    chunking_mode: kb.chunking_mode ?? 'smart',
    chunking_config: {
      ...DEFAULT_CHUNKING_CONFIG,
      ...(kb.chunking_config ?? {}),
      pdf_chunk_strategy: 'markdown',
    },
    pdf_parser_config: kb.pdf_parser_config ?? {
      parser: 'native',
      enable_ocr: true,
      ocr_engine: 'tesseract',
      ocr_languages: ['ch', 'en'],
      extract_images: true,
      extract_tables: true,
    },
  }
}

function formatApiErrorMessage(error: any): string {
  const data = error?.response?.data
  const baseMessage = data?.message ?? data?.detail ?? '保存失败，请重试'
  const detailMessages = Array.isArray(data?.details)
    ? data.details
      .map((item: any) => item?.msg ?? item?.message)
      .filter((item: unknown) => typeof item === 'string' && item)
    : []
  return detailMessages.length > 0 ? `${baseMessage}：${detailMessages.join('；')}` : baseMessage
}

export function GeneralWorkbench({
  kbId,
  view,
  selectedFolderId,
  onFolderChange,
  isFolderTreeCollapsed,
  onToggleFolderTree,
  onSetFolderTreeCollapsed,
}: GeneralWorkbenchProps) {
  const queryClient = useQueryClient()
  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId, 'general-parsing'],
    queryFn: () => fetchKnowledgeBase(kbId),
    enabled: view === 'general-parsing',
    staleTime: 10_000,
  })
  const [config, setConfig] = useState<ConfigState | null>(null)

  const effectiveConfig = useMemo(() => {
    if (config) return config
    if (!kb) return null
    return buildParsingConfig(kb)
  }, [config, kb])

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!effectiveConfig) return null
      return updateKnowledgeBase(kbId, {
        chunking_mode: effectiveConfig.chunking_mode,
        chunking_config: {
          ...(effectiveConfig.chunking_config ?? DEFAULT_CHUNKING_CONFIG),
          pdf_chunk_strategy: 'markdown',
        },
        pdf_parser_config: effectiveConfig.pdf_parser_config,
      })
    },
    onSuccess: async () => {
      toast.success('解析配置已保存')
      setConfig(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-base', kbId] })
    },
    onError: (error: any) => {
      toast.error(formatApiErrorMessage(error))
    },
  })

  if (view === 'files') {
    return (
      <FileBrowser
        kbId={kbId}
        kbType='general'
        selectedFolderId={selectedFolderId}
        onFolderChange={onFolderChange}
        isFolderTreeCollapsed={isFolderTreeCollapsed}
        onToggleFolderTree={onToggleFolderTree}
        onSetFolderTreeCollapsed={onSetFolderTreeCollapsed}
      />
    )
  }

  if (isLoading || !effectiveConfig) {
    return (
      <div className='flex h-full items-center justify-center gap-2 text-sm text-muted-foreground'>
        <Loader2 className='h-4 w-4 animate-spin' />
        加载解析配置中...
      </div>
    )
  }

  return (
    <div className='h-full min-h-0 overflow-auto p-6'>
      <div className='mx-auto max-w-[1280px] space-y-4'>
        <div className='sticky top-0 z-10 flex items-center justify-between rounded-xl border bg-background/90 px-4 py-3 backdrop-blur'>
          <h2 className='text-[15px] font-semibold text-slate-800'>解析配置</h2>
          <Button size='sm' disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            {saveMutation.isPending ? <Loader2 className='mr-2 h-4 w-4 animate-spin' /> : <Save className='mr-2 h-4 w-4' />}
            保存解析配置
          </Button>
        </div>
        <div className='grid grid-cols-2 items-start gap-5'>
          <ChunkingConfigSection config={effectiveConfig} onConfigChange={setConfig} />
          <PdfParserSection config={effectiveConfig} onConfigChange={setConfig} />
        </div>
      </div>
    </div>
  )
}
