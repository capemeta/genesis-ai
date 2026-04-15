/**
 * 组织表单弹窗（创建/编辑）
 */
import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  createOrganization,
  updateOrganization,
  fetchOrganizationTree,
  type OrganizationListItem,
  type OrganizationCreateRequest,
  type OrganizationUpdateRequest,
} from '@/lib/api/organization'
import { OrganizationTreeSelect } from './organization-tree-select'

// 表单验证 Schema
const formSchema = z.object({
  parent_id: z.string().nullable().optional(),
  name: z.string().min(1, '部门名称不能为空').max(255, '部门名称不能超过255个字符'),
  description: z.string().optional(),
  order_num: z.coerce.number().int().min(0, '排序号不能为负数').default(10),
  status: z.enum(['0', '1']).default('0'),
  leader_name: z.string().max(100, '负责人姓名不能超过100个字符').optional(),
  phone: z
    .string()
    .max(20, '联系电话不能超过20个字符')
    .refine(
      (val) => {
        if (!val || val === '') return true
        // 支持手机号（11位）或座机（区号-号码）
        // 手机号：1[3-9]开头的11位数字
        // 座机：0开头，2-3位区号，可选连字符，7-8位号码
        return /^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$/.test(val)
      },
      { message: '电话格式不正确，请输入正确的手机号或座机号' }
    )
    .optional(),
  email: z.string().email('邮箱格式不正确').max(100, '邮箱不能超过100个字符').optional().or(z.literal('')),
})

type FormInput = z.input<typeof formSchema>
type FormValues = z.infer<typeof formSchema>

/**
 * 统一表单默认值，避免重复创建对象并保持输入类型稳定。
 */
const defaultFormValues: FormInput = {
  parent_id: null,
  name: '',
  description: '',
  order_num: 10,
  status: '0',
  leader_name: '',
  phone: '',
  email: '',
}

interface OrganizationFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit' | 'add-child'
  organization?: OrganizationListItem | null
  parentOrganization?: OrganizationListItem | null  // 新增子部门时的父部门
}

export function OrganizationFormDialog({
  open,
  onOpenChange,
  mode,
  organization,
  parentOrganization,
}: OrganizationFormDialogProps) {
  const queryClient = useQueryClient()
  
  // 确认对话框状态
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [pendingFormValues, setPendingFormValues] = useState<FormValues | null>(null)

  // 获取组织树（用于选择上级部门）
  const { data: treeData = [] } = useQuery({
    queryKey: ['organization-tree'],
    queryFn: () => fetchOrganizationTree({ status: '' }),  // 获取所有状态
    enabled: open,
  })

  // 计算需要排除的节点ID（编辑时排除自己和子部门）
  const excludeIds = useMemo(() => {
    if (mode !== 'edit' || !organization) return []
    
    const ids: string[] = [organization.id]
    
    // 递归查找所有子部门
    const findChildren = (parentId: string) => {
      treeData.forEach((node) => {
        const checkNode = (n: any) => {
          if (n.parent_id === parentId) {
            ids.push(n.id)
            findChildren(n.id)
          }
          if (n.children) {
            n.children.forEach(checkNode)
          }
        }
        checkNode(node)
      })
    }
    
    findChildren(organization.id)
    return ids
  }, [mode, organization, treeData])
  
  // 检查当前部门是否有子部门
  const hasChildren = useMemo(() => {
    if (mode !== 'edit' || !organization) return false
    
    // 从 treeData 中查找当前部门的子部门
    let found = false
    const checkNode = (node: any): boolean => {
      if (node.id === organization.id) {
        return node.children && node.children.length > 0
      }
      if (node.children) {
        for (const child of node.children) {
          if (checkNode(child)) {
            return true
          }
        }
      }
      return false
    }
    
    for (const node of treeData) {
      if (checkNode(node)) {
        found = true
        break
      }
    }
    
    return found
  }, [mode, organization, treeData])

  // 表单
  const form = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultFormValues,
  })

  // 当对话框打开时，重置表单
  useEffect(() => {
    if (open) {
      if (mode === 'edit' && organization) {
        // 编辑模式：填充现有数据
        form.reset({
          parent_id: organization.parent_id || null,
          name: organization.name,
          description: organization.description || '',
          order_num: organization.order_num,
          status: organization.status as FormInput['status'],
          leader_name: organization.leader_name || '',
          phone: organization.phone || '',
          email: organization.email || '',
        })
      } else if (mode === 'add-child' && parentOrganization) {
        // 新增子部门模式：设置父部门
        form.reset({
          ...defaultFormValues,
          parent_id: parentOrganization.id,
        })
      } else {
        // 创建模式：重置为默认值
        form.reset(defaultFormValues)
      }
    }
  }, [open, mode, organization, parentOrganization, form])

  // 创建/更新 Mutation
  const { mutate: handleSubmit, isPending } = useMutation({
    mutationFn: async (values: FormValues & { cascade_disable?: boolean }) => {
      if (mode === 'edit' && organization) {
        const updateData: OrganizationUpdateRequest & { cascade_disable?: boolean } = {
          id: organization.id,
          ...values,
          email: values.email || null,
          leader_name: values.leader_name || null,
          phone: values.phone || null,
          description: values.description || null,
        }
        return updateOrganization(updateData)
      } else {
        const createData: OrganizationCreateRequest = {
          ...values,
          email: values.email || null,
          leader_name: values.leader_name || null,
          phone: values.phone || null,
          description: values.description || null,
        }
        return createOrganization(createData)
      }
    },
    onSuccess: () => {
      toast.success(mode === 'edit' ? '更新成功' : '创建成功')
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      queryClient.invalidateQueries({ queryKey: ['organization-tree'] })
      onOpenChange(false)
      // 重置确认对话框状态
      setShowConfirmDialog(false)
      setPendingFormValues(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || (mode === 'edit' ? '更新失败' : '创建失败'))
      // 重置确认对话框状态
      setShowConfirmDialog(false)
      setPendingFormValues(null)
    },
  })

  const onSubmit = (values: FormValues) => {
    // 检查是否是编辑模式 + 状态改为停用 + 有子部门
    if (mode === 'edit' && organization && values.status === '1' && organization.status !== '1' && hasChildren) {
      // 显示确认对话框
      setPendingFormValues(values)
      setShowConfirmDialog(true)
    } else {
      // 直接提交
      handleSubmit(values)
    }
  }
  
  // 确认级联停用
  const handleConfirmCascadeDisable = () => {
    if (pendingFormValues) {
      handleSubmit({ ...pendingFormValues, cascade_disable: true })
    }
  }
  
  // 取消级联停用
  const handleCancelCascadeDisable = () => {
    setShowConfirmDialog(false)
    setPendingFormValues(null)
  }

  const getTitle = () => {
    if (mode === 'edit') return '编辑部门'
    if (mode === 'add-child') return '新增子部门'
    return '新增部门'
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0">
          <DialogHeader className="px-6 pt-6 pb-4 border-b">
            <DialogTitle>{getTitle()}</DialogTitle>
            <DialogDescription>
              {mode === 'edit' ? '修改部门信息' : '填写部门信息'}
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
              <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {/* 上级部门 */}
            <FormField
              control={form.control}
              name="parent_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>上级部门</FormLabel>
                  <FormControl>
                    <OrganizationTreeSelect
                      value={field.value}
                      onChange={field.onChange}
                      treeData={treeData}
                      excludeIds={excludeIds}
                      disabled={mode === 'add-child'}  // 新增子部门时禁用
                    />
                  </FormControl>
                  <FormDescription>
                    选择上级部门，留空则为根部门
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 部门名称 */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    部门名称 <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input placeholder="请输入部门名称" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 部门描述 */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>部门描述</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="请输入部门描述"
                      className="resize-none"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 显示排序 */}
            <FormField
              control={form.control}
              name="order_num"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>显示排序</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="0"
                      {...field}
                      value={typeof field.value === 'number' ? field.value : ''}
                    />
                  </FormControl>
                  <FormDescription>
                    数字越小越靠前，默认为10
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 负责人 */}
            <FormField
              control={form.control}
              name="leader_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>负责人</FormLabel>
                  <FormControl>
                    <Input placeholder="请输入负责人姓名" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 联系电话 */}
            <FormField
              control={form.control}
              name="phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>联系电话</FormLabel>
                  <FormControl>
                    <Input placeholder="请输入联系电话" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 邮箱 */}
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>邮箱</FormLabel>
                  <FormControl>
                    <Input placeholder="请输入邮箱" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* 部门状态 */}
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>部门状态</FormLabel>
                  <FormControl>
                    <RadioGroup
                      value={field.value}
                      onValueChange={field.onChange}
                      className="flex items-center gap-4"
                    >
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="0" id="status-normal" />
                        <Label htmlFor="status-normal">正常</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="1" id="status-disabled" />
                        <Label htmlFor="status-disabled">停用</Label>
                      </div>
                    </RadioGroup>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="py-4 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isPending}
              >
                取消
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {mode === 'edit' ? '保存' : '创建'}
              </Button>
            </DialogFooter>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
    
    {/* 级联停用确认对话框 */}
    <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
      <AlertDialogContent className="sm:max-w-sm">
        <AlertDialogHeader>
          <AlertDialogTitle>确认停用部门</AlertDialogTitle>
          <AlertDialogDescription>
            当前部门存在子部门，停用将导致所有子部门不可用，是否继续？
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancelCascadeDisable}>
            取消
          </AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirmCascadeDisable}>
            确定
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  )
}
