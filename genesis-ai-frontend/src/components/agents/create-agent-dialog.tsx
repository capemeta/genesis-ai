import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { 
  Bot, 
  Sparkles, 
  MessageSquare, 
  FileText, 
  Briefcase,
  GraduationCap,
  HeartPulse,
  ShoppingCart,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ScrollArea } from '@/components/ui/scroll-area'

interface CreateAgentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const agentTemplates = [
  {
    id: 'blank',
    name: '空白 Agent',
    description: '从零开始创建自定义工作流',
    icon: Bot,
    color: 'bg-slate-500/10 text-slate-600',
  },
  {
    id: 'customer-support',
    name: '客户支持助手',
    description: '回答客户问题，提供产品支持',
    icon: MessageSquare,
    color: 'bg-blue-500/10 text-blue-600',
  },
  {
    id: 'document-qa',
    name: '文档问答',
    description: '基于知识库回答问题',
    icon: FileText,
    color: 'bg-green-500/10 text-green-600',
  },
  {
    id: 'business-analyst',
    name: '商业分析师',
    description: '分析数据，生成报告',
    icon: Briefcase,
    color: 'bg-purple-500/10 text-purple-600',
  },
  {
    id: 'education-tutor',
    name: '教育导师',
    description: '帮助学习和解答学术问题',
    icon: GraduationCap,
    color: 'bg-amber-500/10 text-amber-600',
  },
  {
    id: 'health-advisor',
    name: '健康顾问',
    description: '提供健康建议和信息',
    icon: HeartPulse,
    color: 'bg-red-500/10 text-red-600',
  },
  {
    id: 'shopping-assistant',
    name: '购物助手',
    description: '推荐产品，回答购物问题',
    icon: ShoppingCart,
    color: 'bg-orange-500/10 text-orange-600',
  },
]

const avatarPresets = [
  { id: '1', emoji: '🤖', color: 'bg-blue-500' },
  { id: '2', emoji: '🚀', color: 'bg-purple-500' },
  { id: '3', emoji: '💡', color: 'bg-yellow-500' },
  { id: '4', emoji: '🎯', color: 'bg-red-500' },
  { id: '5', emoji: '⚡', color: 'bg-orange-500' },
  { id: '6', emoji: '🌟', color: 'bg-pink-500' },
  { id: '7', emoji: '🔮', color: 'bg-indigo-500' },
  { id: '8', emoji: '🎨', color: 'bg-green-500' },
]

export function CreateAgentDialog({ open, onOpenChange }: CreateAgentDialogProps) {
  const navigate = useNavigate()
  const [step, setStep] = useState<'info' | 'template'>('info')
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    avatar: avatarPresets[0],
    template: 'blank',
  })

  const handleNext = () => {
    if (step === 'info') {
      setStep('template')
    }
  }

  const handleBack = () => {
    if (step === 'template') {
      setStep('info')
    }
  }

  const handleCreate = () => {
    // 创建 Agent 后跳转到工作流构建器
    onOpenChange(false)
    navigate({ to: '/agents/$agentId/builder', params: { agentId: 'new' } })
    // 重置表单
    setTimeout(() => {
      setStep('info')
      setFormData({
        name: '',
        description: '',
        avatar: avatarPresets[0],
        template: 'blank',
      })
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl p-0 gap-0 flex flex-col max-h-[90vh]'>
        <DialogHeader className='p-6 pb-4 shrink-0'>
          <DialogTitle className='flex items-center gap-2 text-2xl'>
            <div className='flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10'>
              <Sparkles className='h-5 w-5 text-primary' />
            </div>
            创建新 Agent
          </DialogTitle>
          <DialogDescription>
            {step === 'info' 
              ? '填写 Agent 的基本信息'
              : '选择一个模板快速开始，或从空白开始'
            }
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className='flex-1 px-6 overflow-y-auto' style={{ maxHeight: 'calc(90vh - 180px)' }}>
          {step === 'info' ? (
            <div className='space-y-6 pb-6'>
              {/* Agent 名称 */}
              <div className='space-y-2'>
                <Label htmlFor='name' className='text-sm font-medium'>
                  Agent 名称 <span className='text-destructive'>*</span>
                </Label>
                <Input
                  id='name'
                  placeholder='例如：客户支持助手'
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className='h-11'
                />
              </div>

              {/* Agent 头像 */}
              <div className='space-y-2'>
                <Label className='text-sm font-medium'>选择头像</Label>
                <div className='grid grid-cols-8 gap-2'>
                  {avatarPresets.map((avatar) => (
                    <button
                      key={avatar.id}
                      type='button'
                      onClick={() => setFormData({ ...formData, avatar })}
                      className={`
                        flex h-12 w-12 items-center justify-center rounded-lg text-2xl
                        transition-all hover:scale-110 hover:shadow-md
                        ${avatar.id === formData.avatar.id 
                          ? 'ring-2 ring-primary ring-offset-2 scale-105' 
                          : ''
                        }
                        ${avatar.color}
                      `}
                    >
                      {avatar.emoji}
                    </button>
                  ))}
                </div>
              </div>

              {/* Agent 描述 */}
              <div className='space-y-2'>
                <Label htmlFor='description' className='text-sm font-medium'>
                  描述
                </Label>
                <Textarea
                  id='description'
                  placeholder='描述这个 Agent 的用途和功能...'
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className='min-h-[100px] resize-none'
                />
                <p className='text-xs text-muted-foreground'>
                  简要说明这个 Agent 的作用，帮助团队成员理解其用途
                </p>
              </div>
            </div>
          ) : (
            <div className='space-y-4 pb-6'>
              <RadioGroup
                value={formData.template}
                onValueChange={(value) => setFormData({ ...formData, template: value })}
                className='grid gap-3'
              >
                {agentTemplates.map((template) => {
                  const Icon = template.icon
                  return (
                    <label
                      key={template.id}
                      htmlFor={template.id}
                      className={`
                        flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer
                        transition-all hover:border-primary/50 hover:shadow-sm
                        ${formData.template === template.id 
                          ? 'border-primary bg-primary/5' 
                          : 'border-border'
                        }
                      `}
                    >
                      <RadioGroupItem value={template.id} id={template.id} className='mt-1' />
                      <div className='flex-1'>
                        <div className='flex items-center gap-3 mb-2'>
                          <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${template.color}`}>
                            <Icon className='h-5 w-5' />
                          </div>
                          <div>
                            <div className='font-semibold'>{template.name}</div>
                            <div className='text-sm text-muted-foreground'>
                              {template.description}
                            </div>
                          </div>
                        </div>
                      </div>
                    </label>
                  )
                })}
              </RadioGroup>
            </div>
          )}
        </ScrollArea>

        <DialogFooter className='p-6 pt-4 border-t bg-muted/30 shrink-0'>
          <div className='flex items-center justify-between w-full'>
            <div className='flex items-center gap-1.5'>
              {[0, 1].map((i) => (
                <div
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    (step === 'info' && i === 0) || (step === 'template' && i === 1)
                      ? 'w-8 bg-primary'
                      : 'w-1.5 bg-muted-foreground/30'
                  }`}
                />
              ))}
            </div>
            <div className='flex gap-3'>
              {step === 'template' && (
                <Button variant='outline' onClick={handleBack}>
                  上一步
                </Button>
              )}
              <Button variant='outline' onClick={() => onOpenChange(false)}>
                取消
              </Button>
              {step === 'info' ? (
                <Button onClick={handleNext} disabled={!formData.name.trim()}>
                  下一步
                </Button>
              ) : (
                <Button onClick={handleCreate}>
                  <Sparkles className='mr-2 h-4 w-4' />
                  创建 Agent
                </Button>
              )}
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
