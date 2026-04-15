import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useMemo, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  FileText,
  MessageSquare,
  Table as TableIcon,
  Globe,
  Puzzle,
  Mic,
  CheckCircle2,
  Loader2,
  Search,
  Tags,
  X
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useScopedTags } from '@/hooks/use-available-tags'

// 语言配置（未来可扩展为 i18n 系统）
const translations = {
  zh: {
    title: '创建知识库',
    description: '通过选择合适的类型，让 AI 更好地理解和索引您的资料。',
    nameLabel: '知识库名称',
    /** 星号旁读屏说明（界面仅展示 *） */
    fieldRequiredSr: '必录',
    namePlaceholder: '例如：2026年度财报集',
    descLabel: '描述',
    descPlaceholder: '简要介绍此知识库的用途或数据来源...',
    typeLabel: '选择知识库类型',
    comingSoon: '敬请期待',
    cancel: '取消',
    confirm: '确认创建',
    validation: {
      nameRequired: '请输入知识库名称',
      nameTooLong: '名称不能超过 50 个字符',
    },
    types: {
      general: {
        title: '通用文档',
        desc: '支持 PDF, Word, TXT等，侧重文本精准解析。',
      },
      qa: {
        title: 'QA 问答对',
        desc: '适合 Excel/CSV，支持模板导入与手工维护。',
      },
      table: {
        title: '结构化表格',
        desc: '针对 CSV, Excel 优化，支持按行检索。',
      },
      web: {
        title: '网页同步',
        desc: '输入 URL 自动抓取内容，支持定时更新。',
      },
      media: {
        title: '音视频转录',
        desc: '处理录音和视频文件，自动转为语义文本。',
      },
      connector: {
        title: '同步应用',
        desc: '对接 Notion, GitHub, 飞书等第三方数据。',
      },
    },
  }
}

const t = translations.zh

const kbTypes = [
  { id: 'general', title: t.types.general.title, desc: t.types.general.desc, icon: FileText, color: 'text-blue-500', bgColor: 'bg-blue-500/10' },
  { id: 'qa', title: t.types.qa.title, desc: t.types.qa.desc, icon: MessageSquare, color: 'text-green-500', bgColor: 'bg-green-500/10' },
  { id: 'table', title: t.types.table.title, desc: t.types.table.desc, icon: TableIcon, color: 'text-orange-500', bgColor: 'bg-orange-500/10' },
  { id: 'web', title: t.types.web.title, desc: t.types.web.desc, icon: Globe, color: 'text-cyan-500', bgColor: 'bg-cyan-500/10' },
  // 未开发能力：使用灰阶与虚线边框，与可选类型区分
  {
    id: 'media',
    title: t.types.media.title,
    desc: t.types.media.desc,
    icon: Mic,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    disabled: true,
  },
  {
    id: 'connector',
    title: t.types.connector.title,
    desc: t.types.connector.desc,
    icon: Puzzle,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    disabled: true,
  },
] as const

const formSchema = z.object({
  name: z.string().min(1, t.validation.nameRequired).max(50, t.validation.nameTooLong),
  description: z.string().optional(),
  type: z.string().min(1),
  tagIds: z.array(z.string()),
})

interface CreateKnowledgeBaseModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (values: z.infer<typeof formSchema>) => Promise<void>
}

export function CreateKnowledgeBaseModal({
  open,
  onOpenChange,
  onCreate,
}: CreateKnowledgeBaseModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagSearch, setTagSearch] = useState('')

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      type: 'general',
      tagIds: [],
    },
  })

  const { data: publicTags = [], isLoading: isLoadingTags } = useScopedTags(undefined, {
    includeGlobal: true,
    includeKb: false,
    targetType: 'kb',
    enabled: open,
  })

  const filteredTags = useMemo(() => {
    const keyword = tagSearch.trim().toLowerCase()
    if (!keyword) return publicTags
    return publicTags.filter((tag) => {
      const aliases = Array.isArray(tag.aliases) ? tag.aliases.join(' ') : ''
      return [tag.name, tag.description || '', aliases].join(' ').toLowerCase().includes(keyword)
    })
  }, [publicTags, tagSearch])

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setIsSubmitting(true)

    try {
      await onCreate(values)
      onOpenChange(false)
      form.reset()
      setTagSearch('')
    } catch {
      // 错误处理由调用者通过 toast 等方式处理，
      // 这里不重复输出控制台日志，避免产生低价值噪声。
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(open) => !isSubmitting && onOpenChange(open)}>
      <DialogContent
        className='sm:max-w-[680px] max-h-[90vh] p-0 overflow-hidden gap-0 flex flex-col'
        onInteractOutside={(e) => isSubmitting && e.preventDefault()}
      >
        <DialogHeader className='px-6 pt-6 pb-2'>
          <DialogTitle className='text-2xl font-bold tracking-tight'>{t.title}</DialogTitle>
          <DialogDescription className='text-muted-foreground mt-2 text-[13px] leading-relaxed'>
            {t.description}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className='flex min-h-0 flex-1 flex-col'>
            <div className='min-h-0 flex-1 overflow-y-auto px-6 pb-6 space-y-6'>
              {/* Name & Description */}
              <div className='grid gap-4'>
                <FormField
                  control={form.control}
                  name='name'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className='text-sm font-semibold inline-flex flex-wrap items-center gap-0.5'>
                        <span>{t.nameLabel}</span>
                        <span className='text-destructive font-bold leading-none' aria-hidden={true}>
                          *
                        </span>
                        <span className='sr-only'>{`（${t.fieldRequiredSr}）`}</span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          placeholder={t.namePlaceholder}
                          {...field}
                          aria-required
                          className='bg-muted/30 border-muted-foreground/20 focus-visible:border-primary focus-visible:ring-[1px] focus-visible:ring-primary/20 transition-all'
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name='description'
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className='text-sm font-semibold'>{t.descLabel}</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder={t.descPlaceholder}
                          className='resize-none h-20 bg-muted/30 border-muted-foreground/20 focus-visible:border-primary focus-visible:ring-[1px] focus-visible:ring-primary/20 transition-all'
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name='tagIds'
                render={({ field }) => (
                  <FormItem className='space-y-3'>
                    <FormLabel className='text-sm font-semibold inline-flex items-center gap-2'>
                      <Tags className='h-4 w-4 text-blue-600' />
                      知识库标签
                    </FormLabel>
                    <div className='rounded-2xl border border-muted-foreground/15 bg-muted/20 p-4 space-y-3'>
                      <p className='text-xs leading-relaxed text-muted-foreground'>
                        用于知识库分类和后续智能选库。这里只选择已有公共标签，创建后可在知识库内继续调整。
                      </p>

                      {field.value.length > 0 ? (
                        <div className='flex flex-wrap gap-2'>
                          {field.value.map((tagId) => {
                            const tag = publicTags.find(item => item.id === tagId)
                            if (!tag) return null
                            return (
                              <Badge key={tag.id} variant='secondary' className='gap-1.5 px-2 py-1'>
                                {tag.name}
                                <button
                                  type='button'
                                  onClick={() => field.onChange(field.value.filter((id) => id !== tagId))}
                                  className='rounded-full p-0.5 hover:bg-destructive/15'
                                >
                                  <X className='h-3 w-3' />
                                </button>
                              </Badge>
                            )
                          })}
                        </div>
                      ) : null}

                      <div className='relative'>
                        <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
                        <Input
                          value={tagSearch}
                          onChange={(e) => setTagSearch(e.target.value)}
                          placeholder='搜索公共标签'
                          className='pl-9 bg-background'
                        />
                      </div>

                      <div className='max-h-40 overflow-y-auto rounded-xl border bg-background p-2'>
                        {isLoadingTags ? (
                          <div className='flex items-center justify-center py-6 text-sm text-muted-foreground'>
                            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                            加载标签中...
                          </div>
                        ) : filteredTags.length === 0 ? (
                          <div className='py-6 text-center text-sm text-muted-foreground'>暂无可选公共标签</div>
                        ) : (
                          <div className='flex flex-wrap gap-2'>
                            {filteredTags.map((tag) => {
                              const active = field.value.includes(tag.id)
                              return (
                                <button
                                  key={tag.id}
                                  type='button'
                                  onClick={() => {
                                    if (active) {
                                      field.onChange(field.value.filter((id) => id !== tag.id))
                                    } else {
                                      field.onChange([...field.value, tag.id])
                                    }
                                  }}
                                  className={cn(
                                    'rounded-full border px-3 py-1.5 text-xs transition-colors',
                                    active
                                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                                      : 'border-border bg-background text-foreground hover:border-blue-400 hover:bg-blue-50/60'
                                  )}
                                >
                                  {tag.name}
                                </button>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Type Selection */}
              <div className='space-y-4'>
                <FormLabel className='text-sm font-semibold tracking-tight'>{t.typeLabel}</FormLabel>
                <FormField
                  control={form.control}
                  name='type'
                  render={({ field }) => (
                    <div className='grid grid-cols-1 sm:grid-cols-2 gap-3'>
                      {kbTypes.map((type) => {
                        const Icon = type.icon
                        const isDisabled = 'disabled' in type && type.disabled
                        const isSelected = !isDisabled && field.value === type.id
                        return (
                          <div
                            key={type.id}
                            role='button'
                            tabIndex={isDisabled ? -1 : 0}
                            aria-disabled={isDisabled}
                            onClick={() => {
                              if (!isDisabled) field.onChange(type.id)
                            }}
                            onKeyDown={(e) => {
                              if (isDisabled) return
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                field.onChange(type.id)
                              }
                            }}
                            className={cn(
                              'relative flex items-start gap-3 p-3.5 rounded-xl transition-all duration-300 group',
                              isDisabled
                                ? 'border-2 border-dashed border-muted-foreground/20 bg-muted/25 cursor-not-allowed opacity-[0.72]'
                                : isSelected
                                  ? 'cursor-pointer border-2 border-blue-600 bg-blue-500/[0.07] shadow-md shadow-blue-600/15 scale-[1.02] dark:border-blue-500 dark:bg-blue-500/10 dark:shadow-blue-500/20'
                                  : 'cursor-pointer border-2 border-blue-500/45 bg-background hover:border-blue-600 hover:shadow-md hover:shadow-blue-500/15 hover:scale-[1.01] dark:border-blue-500/50 dark:hover:border-blue-400'
                            )}
                          >
                            <div
                              className={cn(
                                'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-sm transition-transform duration-300',
                                !isDisabled && 'group-hover:scale-110',
                                type.bgColor,
                                type.color,
                                isDisabled && 'opacity-90'
                              )}
                            >
                              <Icon className='h-5 w-5' strokeWidth={2.5} />
                            </div>
                            <div className='flex-1 pr-6 min-w-0'>
                              <div className='flex flex-wrap items-center gap-2 mb-1'>
                                <h4
                                  className={cn(
                                    'text-sm font-bold transition-colors tracking-tight',
                                    isDisabled && 'text-muted-foreground',
                                    !isDisabled && isSelected && 'text-blue-700 dark:text-blue-400',
                                    !isDisabled && !isSelected && 'text-foreground'
                                  )}
                                >
                                  {type.title}
                                </h4>
                                {isDisabled ? (
                                  <Badge
                                    variant='outline'
                                    className='h-5 border-muted-foreground/25 bg-muted/60 px-1.5 text-[10px] font-medium text-muted-foreground'
                                  >
                                    {t.comingSoon}
                                  </Badge>
                                ) : null}
                              </div>
                              <p
                                className={cn(
                                  'text-[11px] leading-relaxed line-clamp-2',
                                  isDisabled ? 'text-muted-foreground/55' : 'text-muted-foreground/90'
                                )}
                              >
                                {type.desc}
                              </p>
                            </div>
                            {isSelected ? (
                              <CheckCircle2 className='absolute top-2 right-2 h-4 w-4 text-blue-600 dark:text-blue-500 animate-in zoom-in duration-300' />
                            ) : null}
                          </div>
                        )
                      })}
                    </div>
                  )}
                />
              </div>
            </div>

            <DialogFooter className='px-6 py-4 bg-muted/20 border-t border-muted-foreground/10 gap-3 sm:gap-0 shrink-0'>
              <Button
                type='button'
                variant='outline'
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
                className='min-w-24 hover:bg-muted/60 transition-colors'
              >
                {t.cancel}
              </Button>
              <Button
                type='submit'
                disabled={isSubmitting}
                className='min-w-32 px-8 bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-600/20 hover:shadow-xl hover:shadow-blue-600/30 transition-all'
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                    创建中...
                  </>
                ) : (
                  t.confirm
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
