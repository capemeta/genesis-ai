import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Sparkles,
  Sliders,
  Scissors,
  Hash,
  Layers,
  Type,
  FileSearch,
  AlertTriangle,
  Plus,
  X,
} from 'lucide-react'
import type { SplitRuleConfig } from '@/lib/api/knowledge-base'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import { DEFAULT_CHUNKING_CONFIG } from '@/features/knowledge-base/detail/components/shared-config/constants'
import { getModelLimit } from '@/features/knowledge-base/detail/components/shared-config/model-limits'

interface ChunkingConfigSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
}

type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6

const DEFAULT_VISIBLE_HEADING_LEVELS = 3
const MAX_HEADING_LEVEL = 6

const CHAPTER_RULES = [
  { name: '一级标题', level: 1 as const, pattern: '^第[一二三四五六七八九十百千万0-9]+章\\s+.+$', keep_heading: true },
  { name: '二级标题', level: 2 as const, pattern: '^第[一二三四五六七八九十百千万0-9]+节\\s+.+$', keep_heading: true },
  { name: '三级标题', level: 3 as const, pattern: '^第[一二三四五六七八九十百千万0-9]+条\\s*.*$', keep_heading: true },
]

const NUMBERED_RULES = [
  { name: '一级编号', level: 1 as const, pattern: '^\\d+\\s+.+$', keep_heading: true },
  { name: '二级编号', level: 2 as const, pattern: '^\\d+\\.\\d+\\s+.+$', keep_heading: true },
  { name: '三级编号', level: 3 as const, pattern: '^\\d+\\.\\d+\\.\\d+\\s+.+$', keep_heading: true },
]

const CN_HEADING_RULES = [
  { name: '一级标题', level: 1 as const, pattern: '^[一二三四五六七八九十]+、\\s*.+$', keep_heading: true },
  { name: '二级标题', level: 2 as const, pattern: '^（[一二三四五六七八九十]+）\\s*.+$', keep_heading: true },
  { name: '三级标题', level: 3 as const, pattern: '^\\d+\\.\\s*.+$', keep_heading: true },
]

const GENERAL_RULE_TEMPLATES: Array<{
  label: string
  description: string
  rules: SplitRuleConfig[]
}> = [
  {
    label: '段落优先',
    description: '空行、换行、句号',
    rules: [
      { pattern: '\\n\\n', is_regex: false },
      { pattern: '\\n', is_regex: false },
      { pattern: '。', is_regex: false },
    ],
  },
  {
    label: '中文句读',
    description: '句号、问号、分号',
    rules: [{ pattern: '[。！？；;]', is_regex: true }],
  },
  {
    label: '数字编号',
    description: '1 / 1.1 / 1.1.1',
    rules: [{ pattern: '^\\d+(\\.\\d+)*\\s+.+$', is_regex: true }],
  },
  {
    label: '括号编号',
    description: '（一） (1)',
    rules: [{ pattern: '^[（(]?[一二三四五六七八九十0-9]+[）)]\\s*.+$', is_regex: true }],
  },
  {
    label: '问答格式',
    description: 'Q: / 问：',
    rules: [{ pattern: '^(Q|Q:|问|问：)\\s*.+$', is_regex: true }],
  },
  {
    label: '日志时间',
    description: '2026-04-08 12:00:00',
    rules: [{ pattern: '^\\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2}:\\d{2}.*$', is_regex: true }],
  },
]

function toDisplayPattern(pattern: string, isRegex?: boolean): string {
  if (!pattern || isRegex) return pattern
  return pattern
    .replace(/\r/g, '\\r')
    .replace(/\n/g, '\\n')
    .replace(/\t/g, '\\t')
}

function toStoredPattern(pattern: string, isRegex?: boolean): string {
  if (isRegex) return pattern
  return pattern
    .replace(/\\r/g, '\r')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
}

function toDisplaySplitRule(rule: SplitRuleConfig): SplitRuleConfig {
  return {
    pattern: toDisplayPattern(rule.pattern ?? '', rule.is_regex),
    is_regex: !!rule.is_regex,
  }
}

function getHeadingPlaceholder(level: HeadingLevel): string {
  if (level === 1) return '^第...章\\s+.+$ 或 ^\\d+\\s+.+$'
  if (level === 2) return '^第...节\\s+.+$ 或 ^\\d+\\.\\d+\\s+.+$'
  if (level === 3) return '^第...条\\s*.*$ 或 ^\\d+\\.\\d+\\.\\d+\\s+.+$'

  const markdownHeading = '#'.repeat(level)
  const numberedHeading = Array.from({ length: level }, (_, index) => index + 1).join('\\.')
  return `^${markdownHeading}\\s+.+$ 或 ^${numberedHeading}\\s+.+$`
}

function normalizeHeadingLevel(value: number): HeadingLevel {
  return Math.min(MAX_HEADING_LEVEL, Math.max(1, value)) as HeadingLevel
}

function buildMarkdownHeadingRules(maxLevel: number) {
  return Array.from(
    { length: Math.min(MAX_HEADING_LEVEL, Math.max(DEFAULT_VISIBLE_HEADING_LEVELS, maxLevel)) },
    (_, index) => {
      const level = normalizeHeadingLevel(index + 1)
      return {
        name: `${level}级标题`,
        level,
        pattern: `^${'#'.repeat(level)}\\s+.+$`,
        keep_heading: true,
      }
    },
  )
}

export function ChunkingConfigSection({
  config,
  onConfigChange,
}: ChunkingConfigSectionProps) {
  const isTableKB = config.type === 'table'
  const isGeneralKB = config.type === 'general'
  const mode = config.chunking_mode ?? 'smart'
  const isSmartMode = mode === 'smart'
  const isCustomMode = mode === 'custom'
  const isOneMode = mode === 'one'
  const chunking = config.chunking_config ?? DEFAULT_CHUNKING_CONFIG
  const effectiveChunkSize = chunking.chunk_size || (isSmartMode ? 512 : 500)

  const setMode = (value: 'smart' | 'custom' | 'one') => {
    const nextChunking: any = { ...chunking, pdf_chunk_strategy: 'markdown' }
    if (value === 'one') {
      nextChunking.chunk_strategy = 'one'
    } else if (value === 'custom') {
      if (!nextChunking.chunk_strategy || nextChunking.chunk_strategy === 'one') {
        nextChunking.chunk_strategy = 'general'
      }
    } else if (value === 'smart') {
      if (nextChunking.chunk_strategy === 'one') {
        nextChunking.chunk_strategy = 'general'
      }
    }
    onConfigChange({ ...config, chunking_mode: value as any, chunking_config: nextChunking })
  }

  const updateChunking = (patch: Partial<typeof chunking>) => {
    onConfigChange({
      ...config,
      chunking_config: { ...chunking, ...patch, pdf_chunk_strategy: 'markdown' },
    })
  }

  const modelLimit = getModelLimit(config.embedding_model)
  const isOverLimit = modelLimit && effectiveChunkSize > modelLimit.safe_tokens
  const maxChunkSize = modelLimit?.safe_tokens ?? 2000
  const [chunkSizeInput, setChunkSizeInput] = useState(String(effectiveChunkSize))
  const customStrategy = chunking.chunk_strategy === 'rule_based' ? 'rule_based' : 'general'
  const headingRules = chunking.heading_rules ?? []
  const hasHeadingRules = headingRules.some((rule) => rule.pattern?.trim())
  const visibleHeadingLevelCount = Math.min(
    MAX_HEADING_LEVEL,
    Math.max(
      DEFAULT_VISIBLE_HEADING_LEVELS,
      chunking.max_heading_level ?? DEFAULT_VISIBLE_HEADING_LEVELS,
      ...headingRules.map((rule) => rule.level ?? 1),
    ),
  )
  const visibleHeadingLevels = Array.from(
    { length: visibleHeadingLevelCount },
    (_, index) => normalizeHeadingLevel(index + 1),
  )
  const splitRules = chunking.split_rules?.length
    ? chunking.split_rules.map(toDisplaySplitRule)
    : [
      ...(chunking.separator ? [{ pattern: toDisplayPattern(chunking.separator, chunking.is_regex ?? false), is_regex: chunking.is_regex ?? false }] : []),
      ...((chunking.separators ?? []).map((pattern) => ({ pattern: toDisplayPattern(pattern, false), is_regex: false }))),
      ...((chunking.regex_separators ?? []).map((pattern) => ({ pattern, is_regex: true }))),
    ]
  const activeSplitRuleCount = splitRules.filter((rule) => rule.pattern !== '').length

  const updateSplitRules = (nextRules: SplitRuleConfig[]) => {
    const normalizedRules = nextRules.map((rule) => ({
      pattern: rule.pattern ?? '',
      is_regex: !!rule.is_regex,
    }))
    const storedRules = normalizedRules.map((rule) => ({
      pattern: toStoredPattern(rule.pattern, rule.is_regex),
      is_regex: rule.is_regex,
    }))
    const firstEffectiveRule = storedRules.find((rule) => rule.pattern !== '')
    const literalRules = storedRules
      .filter((rule) => !rule.is_regex && rule.pattern !== '')
      .map((rule) => rule.pattern)
    const regexRules = storedRules
      .filter((rule) => rule.is_regex && rule.pattern !== '')
      .map((rule) => rule.pattern)

    updateChunking({
      chunk_strategy: 'general',
      split_rules: storedRules,
      separator: firstEffectiveRule?.pattern ?? '\\n\\n',
      is_regex: firstEffectiveRule?.is_regex ?? false,
      separators: literalRules,
      regex_separators: regexRules,
    })
  }

  const updateHeadingRule = (level: HeadingLevel, pattern: string) => {
    const trimmedPattern = pattern.trim()
    const nextRules = headingRules.filter((rule) => rule.level !== level)
    if (trimmedPattern) {
      nextRules.push({
        name: `${level}级标题`,
        level,
        pattern: trimmedPattern,
        keep_heading: true,
      })
    }
    nextRules.sort((a, b) => a.level - b.level)
    const nextMaxHeadingLevel = Math.min(
      MAX_HEADING_LEVEL,
      Math.max(
        DEFAULT_VISIBLE_HEADING_LEVELS,
        ...nextRules.map((rule) => rule.level ?? 1),
      ),
    )
    updateChunking({
      chunk_strategy: 'rule_based',
      max_heading_level: nextMaxHeadingLevel,
      preserve_headings: true,
      heading_rules: nextRules,
      fallback_separators: chunking.fallback_separators?.length
        ? chunking.fallback_separators
        : ['\n\n', '\n', '。', '；', ' '],
    })
  }

  const getHeadingRulePattern = (level: HeadingLevel) => (
    headingRules.find((rule) => rule.level === level)?.pattern ?? ''
  )

  useEffect(() => {
    setChunkSizeInput(String(effectiveChunkSize))
  }, [effectiveChunkSize])

  const commitChunkSizeInput = () => {
    const fallbackValue = isSmartMode ? 512 : 500
    const parsedValue = parseInt(chunkSizeInput, 10)
    const normalizedValue = Math.min(
      maxChunkSize,
      Math.max(100, Number.isFinite(parsedValue) ? parsedValue : fallbackValue),
    )
    setChunkSizeInput(String(normalizedValue))
    updateChunking({ chunk_size: normalizedValue })
  }

  return (
    <section className='space-y-2.5'>
      <div className='flex items-center gap-2'>
        <Scissors className='h-4 w-4 text-primary' />
        <h3 className='text-sm font-semibold tracking-tight text-foreground'>
          文本分块策略
        </h3>
      </div>

      <div className='flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-sm transition-shadow duration-200 hover:shadow-md'>
        {isTableKB && (
          <div className='rounded-lg border border-primary/10 bg-primary/5 p-3 text-xs leading-relaxed text-primary/80'>
            表格知识库固定使用 `excel_table` 策略，表格专属分块参数已迁移到「结构定义」工作台中配置。
          </div>
        )}

        {!isTableKB && isGeneralKB && (
          <div className='space-y-2'>
            <Label className='text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>分块模式</Label>
            <RadioGroup
              value={mode}
              onValueChange={(v) => setMode(v as 'smart' | 'custom' | 'one')}
              className='grid grid-cols-3 gap-2'
            >
              <label className='relative flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 p-2.5 transition-all hover:bg-muted/50 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5'>
                <RadioGroupItem value='smart' className='pointer-events-none absolute inset-0 opacity-0' />
                <Sparkles className='h-4 w-4 text-primary' />
                <span className='text-xs font-bold'>智能分块</span>
              </label>
              <label className='relative flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 p-2.5 transition-all hover:bg-muted/50 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5'>
                <RadioGroupItem value='custom' className='pointer-events-none absolute inset-0 opacity-0' />
                <Sliders className='h-4 w-4 text-muted-foreground' />
                <span className='text-xs font-bold'>自定义</span>
              </label>
              <label className='relative flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 p-2.5 transition-all hover:bg-muted/50 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5'>
                <RadioGroupItem value='one' className='pointer-events-none absolute inset-0 opacity-0' />
                <FileSearch className='h-4 w-4 text-muted-foreground' />
                <span className='text-xs font-bold'>不分块</span>
              </label>
            </RadioGroup>
          </div>
        )}

        {!isTableKB && isOneMode && (
          <div className='rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-700'>
            <strong>不分块模式</strong>：整个文件将作为一个完整块进行存储和向量化。适合极短的文档或代码片段，内容超限时检索可能丢失信息。
          </div>
        )}

        {!isTableKB && isSmartMode && (
          <div className='rounded-lg border border-primary/10 bg-primary/5 p-3 text-xs leading-relaxed text-primary/80'>
            智能分块会自动选择更合适的切分方式。你可以按文档长短微调切片大小，其它细节由系统自动处理。
          </div>
        )}

        {!isTableKB && (isCustomMode || isSmartMode) && (
          <div className='animate-in space-y-4 fade-in slide-in-from-top-2 duration-300'>
            {isCustomMode && (
              <>
                <div className='space-y-2'>
                  <Label className='text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>自定义方式</Label>
                  <RadioGroup
                    value={customStrategy}
                    onValueChange={(value) => {
                      updateChunking({
                        chunk_strategy: value as 'general' | 'rule_based',
                        max_heading_level: Math.max(chunking.max_heading_level ?? DEFAULT_VISIBLE_HEADING_LEVELS, DEFAULT_VISIBLE_HEADING_LEVELS),
                        preserve_headings: true,
                      })
                    }}
                    className='grid grid-cols-2 gap-2'
                  >
                    <label className='relative flex cursor-pointer flex-col gap-1 rounded-lg border-2 p-2.5 transition-all hover:bg-muted/50 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5'>
                      <RadioGroupItem value='general' className='pointer-events-none absolute inset-0 opacity-0' />
                      <span className='text-xs font-bold'>普通文本</span>
                      <span className='text-[10px] text-muted-foreground'>适合段落、句子、问答等内容</span>
                    </label>
                    <label className='relative flex cursor-pointer flex-col gap-1 rounded-lg border-2 p-2.5 transition-all hover:bg-muted/50 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5'>
                      <RadioGroupItem value='rule_based' className='pointer-events-none absolute inset-0 opacity-0' />
                      <span className='text-xs font-bold'>按标题分块</span>
                      <span className='text-[10px] text-muted-foreground'>适合章节清晰的文档</span>
                    </label>
                  </RadioGroup>
                </div>

                {customStrategy === 'rule_based' ? (
                  <div className='space-y-3 rounded-lg border border-primary/10 bg-primary/5 p-3'>
                <div className='flex items-center justify-between gap-3'>
                  <div className='flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>
                    <Type className='h-3 w-3' />
                    标题识别规则
                  </div>
                  <div className='flex shrink-0 flex-wrap gap-2'>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='h-7 px-2 text-[11px]'
                      onClick={() => updateChunking({ chunk_strategy: 'rule_based', max_heading_level: DEFAULT_VISIBLE_HEADING_LEVELS, preserve_headings: true, heading_rules: CHAPTER_RULES })}
                    >
                      章/节/条示例
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='h-7 px-2 text-[11px]'
                      onClick={() => updateChunking({ chunk_strategy: 'rule_based', max_heading_level: DEFAULT_VISIBLE_HEADING_LEVELS, preserve_headings: true, heading_rules: NUMBERED_RULES })}
                    >
                      1/1.1 示例
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='h-7 px-2 text-[11px]'
                      onClick={() => updateChunking({ chunk_strategy: 'rule_based', max_heading_level: DEFAULT_VISIBLE_HEADING_LEVELS, preserve_headings: true, heading_rules: CN_HEADING_RULES })}
                    >
                      中文序号
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='h-7 px-2 text-[11px]'
                      onClick={() => updateChunking({
                        chunk_strategy: 'rule_based',
                        max_heading_level: visibleHeadingLevelCount,
                        preserve_headings: true,
                        heading_rules: buildMarkdownHeadingRules(visibleHeadingLevelCount),
                      })}
                    >
                      Markdown标题
                    </Button>
                  </div>
                </div>
                {visibleHeadingLevels.map((level) => (
                  <div key={level} className='space-y-1.5'>
                    <Label className='text-[11px] text-muted-foreground'>{level} 级标题规则</Label>
                    <Input
                      value={getHeadingRulePattern(level)}
                      onChange={(e) => updateHeadingRule(level, e.target.value)}
                      placeholder={getHeadingPlaceholder(level)}
                      className='h-9 border-muted-foreground/20 font-mono text-xs'
                    />
                  </div>
                ))}
                <div className='flex flex-wrap items-center justify-between gap-2'>
                  <p className='text-[11px] leading-relaxed text-muted-foreground'>
                    按你填写的标题规则识别章节结构。默认展示 3 级，最多可扩展到 6 级。
                  </p>
                  {visibleHeadingLevelCount < MAX_HEADING_LEVEL && (
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      className='h-7 px-2 text-[11px]'
                      onClick={() => updateChunking({
                        chunk_strategy: 'rule_based',
                        max_heading_level: Math.min(MAX_HEADING_LEVEL, visibleHeadingLevelCount + 1),
                        preserve_headings: true,
                      })}
                    >
                      <Plus className='mr-1 h-3 w-3' />
                      继续添加层级
                    </Button>
                  )}
                </div>
                <div className='rounded-md border border-dashed border-primary/20 bg-background/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground'>
                  建议一条规则对应一整行标题，例如 `^第...章\\s+.+$`、`^\\d+\\.\\d+\\s+.+$`、`^####\\s+.+$`。标题规则适合识别章节，不适合写成句号、换行这类局部边界。
                </div>
                {visibleHeadingLevelCount > 3 && (
                  <div className='rounded-md border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-[11px] leading-relaxed text-amber-700'>
                    已扩展到 {visibleHeadingLevelCount} 级。层级越深，内容越容易被切得更细，建议只在文档结构稳定时继续增加。
                  </div>
                )}
                {!hasHeadingRules && (
                  <div className='flex items-start gap-1.5 rounded border border-amber-200 bg-amber-50 p-2 text-[11px] leading-relaxed text-amber-700'>
                    <AlertTriangle className='mt-0.5 h-3 w-3 shrink-0' />
                    <span>按标题分块至少需要填写 1 条标题规则，建议先使用示例，再按文档格式微调。</span>
                  </div>
                )}
                  </div>
                ) : (
                  <div className='space-y-3 rounded-xl border border-slate-200/70 bg-gradient-to-br from-slate-50 to-background p-3 shadow-sm'>
                <div className='flex flex-wrap items-start justify-between gap-3'>
                  <div className='space-y-1'>
                    <div className='flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>
                      <Type className='h-3 w-3' />
                      切分规则
                    </div>
                    <p className='text-[11px] leading-relaxed text-muted-foreground'>
                      从上到下依次作为拆分优先级。文本未超出切片大小时尽量保持整块；只有超长时才继续使用下一条规则递进拆分，且命中的文本会被保留。
                    </p>
                  </div>
                  <div className='flex items-center gap-2 rounded-full border bg-background px-2.5 py-1 text-[11px] text-muted-foreground shadow-sm'>
                    <span>已配置</span>
                    <span className='font-semibold text-primary'>{activeSplitRuleCount}</span>
                    <span>条规则</span>
                  </div>
                </div>

                <div className='space-y-2 rounded-lg border bg-background/80 p-3'>
                  <div className='flex flex-wrap items-center justify-between gap-2'>
                    <div>
                      <Label className='text-[11px] font-medium text-foreground'>快捷示例</Label>
                      <p className='mt-1 text-[10px] text-muted-foreground'>点击后会直接替换当前规则列表，适合快速起步。</p>
                    </div>
                    <div className='flex flex-wrap gap-2'>
                      {GENERAL_RULE_TEMPLATES.map((template) => (
                        <Button
                          key={template.label}
                          type='button'
                          size='sm'
                          variant='outline'
                          className='h-7 px-2 text-[11px]'
                          onClick={() => updateSplitRules(template.rules)}
                          title={template.description}
                        >
                          {template.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className='space-y-2 rounded-lg border bg-background/80 p-3'>
                  <div className='flex flex-wrap items-center justify-between gap-2'>
                    <div>
                      <Label className='text-[11px] font-medium text-foreground'>规则列表</Label>
                      <p className='mt-1 text-[10px] text-muted-foreground'>每行一条规则。越靠上优先级越高。需要匹配编号、问答、时间等固定格式时，可以使用正则。</p>
                    </div>
                    <div className='flex gap-2'>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        className='h-7 px-2 text-[11px]'
                        onClick={() => updateSplitRules([...splitRules, { pattern: '\\n', is_regex: false }])}
                      >
                        <Plus className='mr-1 h-3 w-3' />
                        添加普通
                      </Button>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        className='h-7 px-2 text-[11px]'
                        onClick={() => updateSplitRules([...splitRules, { pattern: '^\\d+(\\.\\d+)*\\s+.+$', is_regex: true }])}
                      >
                        <Plus className='mr-1 h-3 w-3' />
                        添加正则
                      </Button>
                    </div>
                  </div>
                  {splitRules.length > 0 ? (
                    <div className='space-y-2'>
                      {splitRules.map((rule, index) => (
                        <div key={index} className='flex items-center gap-2 rounded-lg border border-slate-200/70 bg-slate-50/60 p-2'>
                          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${rule.is_regex ? 'bg-violet-100 text-violet-700' : 'bg-primary/10 text-primary'}`}>
                            {index + 1}
                          </span>
                          <Input
                            value={rule.pattern}
                            onChange={(e) => {
                              const nextRules = [...splitRules]
                              nextRules[index] = { ...nextRules[index], pattern: e.target.value }
                              updateSplitRules(nextRules)
                            }}
                            placeholder={rule.is_regex ? '例如：^\\d+(\\.\\d+)*\\s+.+$' : '例如：\\n\\n'}
                            className={`h-9 bg-background font-mono text-xs ${rule.is_regex ? 'border-violet-200/80 focus-visible:ring-violet-300' : 'border-muted-foreground/20'}`}
                          />
                          <div className='flex items-center gap-2 rounded-full bg-background px-2 py-1'>
                            <span className={`text-[11px] ${rule.is_regex ? 'text-violet-700' : 'text-muted-foreground'}`}>正则</span>
                            <Switch
                              checked={rule.is_regex ?? false}
                              onCheckedChange={(checked) => {
                                const nextRules = [...splitRules]
                                nextRules[index] = { ...nextRules[index], is_regex: checked }
                                updateSplitRules(nextRules)
                              }}
                            />
                          </div>
                          <Button
                            type='button'
                            size='icon'
                            variant='ghost'
                            className='h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive'
                            onClick={() => updateSplitRules(splitRules.filter((_, itemIndex) => itemIndex !== index))}
                          >
                            <X className='h-3.5 w-3.5' />
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className='rounded-md border border-dashed border-slate-200 bg-background/70 px-3 py-2 text-[11px] text-muted-foreground'>
                      暂未配置切分规则。建议先插入一个示例，或手动添加一条普通规则。
                    </div>
                  )}
                  <div className='rounded-md border border-dashed border-slate-200 bg-slate-50/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground'>
                    说明：普通规则适合空行、换行、句号这类自然边界；正则适合标题编号、问答前缀、时间格式等固定样式。命中的内容会保留，不会丢失。
                  </div>
                </div>
                  </div>
                )}
              </>
            )}

            <div className='grid grid-cols-2 gap-4'>
              <div className='space-y-2'>
                <div className='flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>
                  <Hash className='h-3 w-3' />
                  切片大小
                </div>
                <div className='relative'>
                  <Input
                    id='chunk_size'
                    type='number'
                    min={100}
                    max={maxChunkSize}
                    value={chunkSizeInput}
                    onChange={(e) => setChunkSizeInput(e.target.value)}
                    onBlur={commitChunkSizeInput}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        commitChunkSizeInput()
                      }
                    }}
                    className={`h-10 border-muted-foreground/20 pl-3 pr-14 text-sm transition-colors ${
                      isOverLimit ? 'border-amber-500 bg-amber-50/10 focus-visible:ring-amber-500' : ''
                    }`}
                  />
                  <span className='pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground'>字符</span>
                </div>
                {isOverLimit && (
                  <div className='flex items-start gap-1.5 rounded border border-amber-200 bg-amber-50 p-2 text-[10px] leading-tight text-amber-700'>
                    <AlertTriangle className='mt-0.5 h-3 w-3 shrink-0' />
                    <div>
                      建议不超过 {modelLimit?.safe_tokens ?? 512} 字符。
                    </div>
                  </div>
                )}
              </div>

              <div className='space-y-2'>
                <div className='flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground'>
                  <Layers className='h-3 w-3' />
                  重叠长度
                </div>
                {customStrategy === 'rule_based' ? (
                  <div className='rounded-lg border border-dashed border-slate-200 bg-slate-50/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground'>
                    按标题分块时，系统会自动处理上下文衔接，无需设置这一项。
                  </div>
                ) : isSmartMode ? (
                  <div className='rounded-lg border border-dashed border-slate-200 bg-slate-50/70 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground'>
                    智能分块会自动处理上下文衔接，无需手动设置。
                  </div>
                ) : (
                  <div className='relative'>
                    <Input
                      id='overlap'
                      type='number'
                      min={0}
                      max={500}
                      value={chunking.overlap || 50}
                      onChange={(e) =>
                        updateChunking({ overlap: parseInt(e.target.value) || 50 })
                      }
                      className='h-10 border-muted-foreground/20 pl-3 pr-14 text-sm'
                    />
                    <span className='pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground'>字符</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
