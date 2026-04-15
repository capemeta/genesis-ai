import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tag, Lock, Globe, Fingerprint, Database, FileText, MessageSquare, Mic, Puzzle, Search, Tags, X } from 'lucide-react'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import type { Tag as KBTag } from '@/lib/api/folder.types'
import { cn } from '@/lib/utils'

/** 与标签管理页保持一致的颜色映射表 */
const COLOR_MAP: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  blue: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', dot: 'bg-blue-400' },
  green: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', dot: 'bg-emerald-400' },
  purple: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', dot: 'bg-purple-400' },
  red: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', dot: 'bg-red-400' },
  yellow: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', dot: 'bg-amber-400' },
  gray: { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200', dot: 'bg-slate-400' },
}

/** 根据标签颜色名获取样式，未知颜色回退到 blue */
function getTagColors(color?: string) {
  return COLOR_MAP[color ?? 'blue'] ?? COLOR_MAP.blue
}

interface BasicInfoSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
  kbTags?: KBTag[]
  selectedTagIds?: string[]
  tagSearch?: string
  onTagSearchChange?: (value: string) => void
  onTagIdsChange?: (tagIds: string[]) => void
  onOpenTagManagement?: () => void
}

export function BasicInfoSection({
  config,
  onConfigChange,
  kbTags = [],
  selectedTagIds = [],
  tagSearch = '',
  onTagSearchChange,
  onTagIdsChange,
  onOpenTagManagement,
}: BasicInfoSectionProps) {
  const typeMap = {
    general: { label: '通用文档', icon: FileText, color: 'text-blue-500/70' },
    qa: { label: 'QA 问答对', icon: MessageSquare, color: 'text-green-500/70' },
    table: { label: '结构化表格', icon: Database, color: 'text-orange-500/70' },
    web: { label: '网页同步', icon: Globe, color: 'text-cyan-500/70' },
    media: { label: '音视频转录', icon: Mic, color: 'text-slate-400' },
    connector: { label: '同步应用', icon: Puzzle, color: 'text-slate-400' },
  }

  const currentType = typeMap[config.type as keyof typeof typeMap] || typeMap.general
  const Icon = currentType.icon
  const filteredTags = kbTags.filter((tag) => {
    const keyword = tagSearch.trim().toLowerCase()
    if (!keyword) return true
    const aliases = Array.isArray(tag.aliases) ? tag.aliases.join(' ') : ''
    return [tag.name, tag.description || '', aliases].join(' ').toLowerCase().includes(keyword)
  })

  return (
    <div className='space-y-6'>
      <div className='space-y-2'>
        <Label className='text-sm font-semibold text-foreground'>
          知识库类型
        </Label>
        <div className='flex h-10 cursor-not-allowed items-center gap-3 rounded-md border border-border bg-muted/40 px-3.5'>
          <Icon className={`h-4 w-4 shrink-0 ${currentType.color}`} />
          <span className='text-sm font-medium text-foreground'>
            {currentType.label}
          </span>
          <span className='ml-auto text-xs text-muted-foreground/50'>不可修改</span>
        </div>
      </div>

      <div className='space-y-2'>
        <Label htmlFor='name' className='text-sm font-semibold text-foreground'>
          知识库名称
        </Label>
        <div className='group relative'>
          <Fingerprint className='absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40 transition-colors group-focus-within:text-primary/60' />
          <Input
            id='name'
            value={config.name}
            onChange={(e) => onConfigChange({ ...config, name: e.target.value })}
            placeholder='为您的知识库起一个直观的名称'
            className='h-10 pl-10 text-sm'
          />
        </div>
      </div>

      <div className='space-y-2'>
        <Label htmlFor='description' className='text-sm font-semibold text-foreground'>
          描述信息
        </Label>
        <div className='group relative'>
          <Tag className='absolute left-3.5 top-3 h-4 w-4 text-muted-foreground/40 transition-colors group-focus-within:text-primary/60' />
          <Textarea
            id='description'
            value={config.description || ''}
            onChange={(e) => onConfigChange({ ...config, description: e.target.value })}
            placeholder='描述该知识库的内容，有助于 AI 更好地检索相关信息'
            rows={3}
            className='min-h-[88px] py-2.5 pl-10 text-sm leading-relaxed'
          />
        </div>
      </div>

      <div className='border-t border-border/50' />

      <div className='space-y-2'>
        <div className='flex items-center justify-between'>
          <Label className='inline-flex items-center gap-2 text-sm font-semibold text-foreground'>
            <Tags className='h-4 w-4 text-muted-foreground/60' />
            知识库标签
          </Label>
          <Button type='button' variant='outline' size='sm' className='h-8 gap-1.5 px-3 text-sm' onClick={onOpenTagManagement}>
            管理标签
          </Button>
        </div>
        <div className='space-y-3 rounded-lg border border-border bg-muted/10 p-4'>
          <p className='text-xs leading-relaxed text-muted-foreground'>
            标签用于知识库分类与智能选库。可选择“公共标签”和“当前知识库标签”。
          </p>

          {selectedTagIds.length > 0 ? (
            <div className='flex flex-wrap gap-2'>
              {selectedTagIds.map((tagId) => {
                const tag = kbTags.find((item) => item.id === tagId)
                if (!tag) return null
                const isScoped = Boolean(tag.kb_id)
                const colors = getTagColors(tag.color)
                return (
                  <span
                    key={tag.id}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm font-medium',
                      colors.bg,
                      colors.text,
                      colors.border
                    )}
                  >
                    <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', colors.dot)} />
                    {tag.name}
                    <span className='text-[11px] font-normal opacity-60'>
                      {isScoped ? '·本库' : '·公共'}
                    </span>
                    <button
                      type='button'
                      onClick={() => onTagIdsChange?.(selectedTagIds.filter((id) => id !== tagId))}
                      className='ml-0.5 rounded-full p-0.5 opacity-60 transition-all hover:bg-black/10 hover:opacity-100'
                    >
                      <X className='h-3 w-3' />
                    </button>
                  </span>
                )
              })}
            </div>
          ) : (
            <div className='rounded-md border border-dashed border-border bg-background/50 px-3 py-4 text-center text-sm text-muted-foreground'>
              当前未设置知识库标签
            </div>
          )}

          <div className='relative'>
            <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50' />
            <Input
              value={tagSearch}
              onChange={(e) => onTagSearchChange?.(e.target.value)}
              placeholder='搜索标签名称'
              className='h-9 pl-9 text-sm'
            />
          </div>

          <div className='max-h-40 overflow-y-auto rounded-md border border-border bg-background p-2'>
            {filteredTags.length === 0 ? (
              <div className='py-5 text-center text-sm text-muted-foreground'>暂无可选标签，请先到标签管理页创建</div>
            ) : (
              <div className='flex flex-wrap gap-2'>
                {filteredTags.map((tag) => {
                  const active = selectedTagIds.includes(tag.id)
                  const colors = getTagColors(tag.color)
                  return (
                    <button
                      key={tag.id}
                      type='button'
                      onClick={() => {
                        if (!onTagIdsChange) return
                        if (active) {
                          onTagIdsChange(selectedTagIds.filter((id) => id !== tag.id))
                        } else {
                          onTagIdsChange([...selectedTagIds, tag.id])
                        }
                      }}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-all',
                        active
                          ? cn(colors.bg, colors.text, colors.border, 'font-medium shadow-sm')
                          : 'border-border/60 bg-muted/20 text-muted-foreground hover:border-border hover:bg-muted/50 hover:text-foreground'
                      )}
                    >
                      {active && <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', colors.dot)} />}
                      {tag.name}
                      <span className='text-xs opacity-40'>{tag.kb_id ? '·本库' : '·公共'}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className='space-y-2'>
        <Label htmlFor='visibility' className='text-sm font-semibold text-foreground'>
          公开权限
        </Label>
        <Select
          value={config.visibility}
          onValueChange={(value: 'private' | 'tenant_public') =>
            onConfigChange({ ...config, visibility: value })
          }
        >
          <SelectTrigger id='visibility' className='h-10 text-sm'>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='private' className='py-2.5'>
              <div className='flex items-center gap-3'>
                <div className='flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-amber-50 text-amber-500 dark:bg-amber-950/40'>
                  <Lock className='h-3.5 w-3.5' />
                </div>
                <div className='flex flex-col gap-0.5'>
                  <span className='text-sm font-medium'>私人授权</span>
                  <span className='text-xs text-muted-foreground'>仅限自己使用</span>
                </div>
              </div>
            </SelectItem>
            <SelectItem value='tenant_public' className='py-2.5'>
              <div className='flex items-center gap-3'>
                <div className='flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-500 dark:bg-blue-950/40'>
                  <Globe className='h-3.5 w-3.5' />
                </div>
                <div className='flex flex-col gap-0.5'>
                  <span className='text-sm font-medium'>组织共享</span>
                  <span className='text-xs text-muted-foreground'>租户内成员可见</span>
                </div>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
