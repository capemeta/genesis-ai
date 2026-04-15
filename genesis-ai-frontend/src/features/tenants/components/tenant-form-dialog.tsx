import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useEffect } from 'react'

import { createTenant, updateTenant, type Tenant } from '@/lib/api/tenant'
import { useAuthStore } from '@/stores/auth-store'
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
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

const tenantSchema = z.object({
  name: z.string().min(1, '请输入租户名称').max(255, '名称不能超过255个字符'),
  description: z.string().optional(),
  max_users: z.number().int().positive('请输入正整数').optional().nullable(),
  max_storage_gb: z.number().int().positive('请输入正整数').optional().nullable(),
})

type TenantFormData = z.infer<typeof tenantSchema>

interface TenantFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tenant?: Tenant | null
  onSuccess: () => void
}

export function TenantFormDialog({
  open,
  onOpenChange,
  tenant,
  onSuccess,
}: TenantFormDialogProps) {
  const isEdit = !!tenant
  const { user } = useAuthStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<TenantFormData>({
    resolver: zodResolver(tenantSchema),
    defaultValues: {
      name: '',
      description: '',
      max_users: null,
      max_storage_gb: null,
    },
  })

  // 当 tenant 变化时，重置表单值
  useEffect(() => {
    if (tenant) {
      reset({
        name: tenant.name,
        description: tenant.description || '',
        max_users: tenant.limits.max_users || null,
        max_storage_gb: tenant.limits.max_storage_gb || null,
      })
    } else {
      reset({
        name: '',
        description: '',
        max_users: null,
        max_storage_gb: null,
      })
    }
  }, [tenant, reset])

  const { mutate: handleCreate, isPending: isCreating } = useMutation({
    mutationFn: createTenant,
    onSuccess: () => {
      toast.success('租户创建成功')
      reset()
      onSuccess()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '创建失败')
    },
  })

  const { mutate: handleUpdate, isPending: isUpdating } = useMutation({
    mutationFn: updateTenant,
    onSuccess: () => {
      toast.success('租户更新成功')
      onSuccess()
    },
    onError: () => {
      // toast.error(error.response?.data?.detail || '更新失败')
    },
  })

  const onSubmit = (data: TenantFormData) => {
    const limits: any = {}
    
    // 处理数字字段（过滤掉 null 和 undefined）
    if (data.max_users != null && !isNaN(data.max_users)) {
      limits.max_users = data.max_users
    }
    if (data.max_storage_gb != null && !isNaN(data.max_storage_gb)) {
      limits.max_storage_gb = data.max_storage_gb
    }

    if (isEdit && tenant) {
      handleUpdate({
        id: tenant.id,
        name: data.name,
        description: data.description,
        limits: Object.keys(limits).length > 0 ? limits : undefined,
      })
    } else {
      if (!user?.id) {
        toast.error('无法获取当前用户信息')
        return
      }

      handleCreate({
        owner_id: user.id,
        name: data.name,
        description: data.description,
        limits: Object.keys(limits).length > 0 ? limits : undefined,
      })
    }
  }

  const isPending = isCreating || isUpdating

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑租户' : '创建租户'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '修改租户信息和配额限制' : '填写租户信息并设置配额限制'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">
              租户名称 <span className="text-destructive">*</span>
            </Label>
            <Input id="name" placeholder="输入租户名称" {...register('name')} />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">描述</Label>
            <Textarea
              id="description"
              placeholder="输入租户描述（可选）"
              rows={3}
              {...register('description')}
            />
          </div>

          <div className="space-y-4">
            <Label>配额限制</Label>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max_users" className="text-sm">
                  最大用户数
                </Label>
                <Input
                  id="max_users"
                  type="number"
                  placeholder="不限制"
                  {...register('max_users', { valueAsNumber: true })}
                />
                {errors.max_users && (
                  <p className="text-sm text-destructive">{errors.max_users.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="max_storage_gb" className="text-sm">
                  最大存储空间（GB）
                </Label>
                <Input
                  id="max_storage_gb"
                  type="number"
                  placeholder="不限制"
                  {...register('max_storage_gb', { valueAsNumber: true })}
                />
                {errors.max_storage_gb && (
                  <p className="text-sm text-destructive">
                    {errors.max_storage_gb.message}
                  </p>
                )}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              取消
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? (isEdit ? '保存中...' : '创建中...') : isEdit ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
