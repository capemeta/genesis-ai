/**
 * 权限表单弹窗（创建/编辑/新增子权限）
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
  createPermission,
  updatePermission,
  fetchPermissionTree,
  type PermissionListItem,
  type PermissionCreateRequest,
  type PermissionUpdateRequest,
} from '@/lib/api/permission'
import { PermissionTreeSelect } from './permission-tree-select'
import { IconPicker } from '@/components/icon-picker'
import axiosInstance from '@/lib/api/axios-instance'

// 表单验证 Schema
const formSchema = z.object({
  parent_id: z.string().nullable().optional(),
  type: z.enum(['directory', 'menu', 'function']).default('directory'),
  code: z.string().min(1, '权限代码不能为空').max(100, '权限代码不能超过100个字符'),
  name: z.string().min(1, '权限名称不能为空').max(100, '权限名称不能超过100个字符'),
  module: z.string().min(1, '所属模块不能为空').max(50, '所属模块不能超过50个字符'),
  path: z.string().max(255, '路由路径不能超过255个字符').optional(),
  icon: z.string().max(100, '图标不能超过100个字符').optional(),
  component: z.string().max(255, '组件路径不能超过255个字符').optional(),
  sort_order: z.coerce.number().int().min(0, '排序号不能为负数').default(0),
  is_hidden: z.enum(['0', '1']).default('0'),
  description: z.string().optional(),
  status: z.enum(['0', '1']).default('0'),
})

type FormValues = z.infer<typeof formSchema>

interface PermissionFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit' | 'add-child'
  permission?: PermissionListItem | null
  parentPermission?: PermissionListItem | null  // 新增子权限时的父权限
}

export function PermissionFormDialog({
  open,
  onOpenChange,
  mode,
  permission,
  parentPermission,
}: PermissionFormDialogProps) {
  const queryClient = useQueryClient()
  
  // 确认对话框状态
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [childCount, setChildCount] = useState(0)
  const [pendingFormValues, setPendingFormValues] = useState<any>(null)

  // 获取权限树（用于选择上级权限）
  const { data: treeData = [] } = useQuery({
    queryKey: ['permission-tree'],
    queryFn: () => fetchPermissionTree({ status: '' }),  // 获取所有状态
    enabled: open,
  })

  // 计算需要排除的节点ID（编辑时排除自己和子权限）
  const excludeIds = useMemo(() => {
    if (mode !== 'edit' || !permission) return []
    
    const ids: string[] = [permission.id]
    
    // 递归查找所有子权限
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
    
    findChildren(permission.id)
    return ids
  }, [mode, permission, treeData])

  // 表单
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema) as any,
    defaultValues: {
      parent_id: null,
      type: 'directory',
      code: '',
      name: '',
      module: '',
      path: '',
      icon: '',
      component: '',
      sort_order: 0,
      is_hidden: '0',
      description: '',
      status: '0',
    },
  })

  // 当对话框打开时，重置表单
  useEffect(() => {
    if (open) {
      if (mode === 'edit' && permission) {
        // 编辑模式：填充现有数据
        // 注意：PermissionListItem 不包含 component 和 is_hidden，需要从完整的 Permission 对象获取
        form.reset({
          parent_id: permission.parent_id || null,
          type: permission.type as 'directory' | 'menu' | 'function',
          code: permission.code,
          name: permission.name,
          module: permission.module,
          path: permission.path || '',
          icon: permission.icon || '',
          component: '',  // PermissionListItem 不包含此字段
          sort_order: permission.sort_order,
          is_hidden: '0',  // PermissionListItem 不包含此字段，默认为否
          description: permission.description || '',
          status: permission.status === 0 ? '0' : '1',
        })
      } else if (mode === 'add-child' && parentPermission) {
        // 新增子权限模式：设置父权限和模块
        form.reset({
          parent_id: parentPermission.id,
          type: 'directory',
          code: '',
          name: '',
          module: parentPermission.module,
          path: '',
          icon: '',
          component: '',
          sort_order: 0,
          is_hidden: '0',
          description: '',
          status: '0',
        })
      } else {
        // 创建模式：重置为默认值
        form.reset({
          parent_id: null,
          type: 'directory',
          code: '',
          name: '',
          module: '',
          path: '',
          icon: '',
          component: '',
          sort_order: 0,
          is_hidden: '0',
          description: '',
          status: '0',
        })
      }
    }
  }, [open, mode, permission, parentPermission, form])

  // 创建/更新 Mutation
  const { mutate: handleSubmit, isPending } = useMutation({
    mutationFn: async (values: FormValues) => {
      if (mode === 'edit' && permission) {
        const updateData: PermissionUpdateRequest = {
          id: permission.id,
          ...values,
          parent_id: values.parent_id || undefined,
          is_hidden: values.is_hidden === '1',
          status: values.status === '0' ? 0 : 1,
          path: values.path || undefined,
          icon: values.icon || undefined,
          component: values.component || undefined,
          description: values.description || undefined,
        }
        return updatePermission(updateData)
      } else {
        const createData: PermissionCreateRequest = {
          ...values,
          parent_id: values.parent_id || undefined,
          is_hidden: values.is_hidden === '1',
          status: values.status === '0' ? 0 : 1,
          path: values.path || undefined,
          icon: values.icon || undefined,
          component: values.component || undefined,
          description: values.description || undefined,
        }
        return createPermission(createData)
      }
    },
    onSuccess: () => {
      toast.success(mode === 'edit' ? '更新成功' : '创建成功')
      queryClient.invalidateQueries({ queryKey: ['permissions'] })
      queryClient.invalidateQueries({ queryKey: ['permission-tree'] })
      onOpenChange(false)
      // 重置确认对话框状态
      setShowConfirmDialog(false)
      setPendingFormValues(null)
      setChildCount(0)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || (mode === 'edit' ? '更新失败' : '创建失败'))
      // 重置确认对话框状态
      setShowConfirmDialog(false)
      setPendingFormValues(null)
      setChildCount(0)
    },
  })

  const onSubmit = async (values: any) => {
    // 检查是否将状态改为停用且有子权限
    if (mode === 'edit' && permission && values.status === '1' && permission.status === 0) {
      try {
        // 调用 API 检查子权限数量
        const response = await axiosInstance.get(
          `/api/v1/permissions/check-children`,
          { params: { id: permission.id } }
        )
        
        if (response.data.data.has_children) {
          // 显示确认对话框
          setChildCount(response.data.data.child_count)
          setPendingFormValues(values)
          setShowConfirmDialog(true)
          return  // 等待用户确认
        }
      } catch (error) {
        console.error('检查子权限失败:', error)
        // 即使检查失败也允许继续提交
      }
    }
    
    // 直接提交
    handleSubmit(values)
  }
  
  // 确认级联停用
  const handleConfirmCascadeDisable = () => {
    if (pendingFormValues) {
      handleSubmit(pendingFormValues)
    }
  }
  
  // 取消级联停用
  const handleCancelCascadeDisable = () => {
    setShowConfirmDialog(false)
    setPendingFormValues(null)
    setChildCount(0)
  }

  const getTitle = () => {
    if (mode === 'edit') return '编辑权限'
    return '创建权限'
  }
  
  const getDescription = () => {
    if (mode === 'edit') return '修改权限信息'
    // if (mode === 'add-child') return `为"${parentPermission?.name}"创建子权限`
    return '填写权限信息'
  }
  
  // 监听权限类型变化，动态显示字段
  const selectedType = form.watch('type')

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <DialogTitle>{getTitle()}</DialogTitle>
          <DialogDescription>
            {getDescription()}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {/* 上级权限 */}
              <FormField
                control={form.control}
                name="parent_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>上级权限</FormLabel>
                    <FormControl>
                      <PermissionTreeSelect
                        value={field.value}
                        onChange={field.onChange}
                        treeData={treeData}
                        excludeIds={excludeIds}
                        disabled={mode === 'add-child'}  // 新增子权限时禁用
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 权限类型 */}
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      权限类型 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <RadioGroup
                        value={field.value}
                        onValueChange={field.onChange}
                        className="flex items-center gap-4"
                      >
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="directory" id="type-directory" />
                          <Label htmlFor="type-directory">目录</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="menu" id="type-menu" />
                          <Label htmlFor="type-menu">菜单</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="function" id="type-function" />
                          <Label htmlFor="type-function">功能</Label>
                        </div>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 权限代码 */}
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      权限代码 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="请输入权限代码" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 权限名称 */}
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      权限名称 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="请输入权限名称" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 所属模块 */}
              <FormField
                control={form.control}
                name="module"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      所属模块 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="请输入所属模块" {...field} disabled={mode === 'add-child'} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 路由路径 - 仅菜单类型显示 */}
              {selectedType === 'menu' && (
                <FormField
                  control={form.control}
                  name="path"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>路由路径</FormLabel>
                      <FormControl>
                        <Input placeholder="请输入路由路径" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* 图标 - 仅菜单和目录类型显示 */}
              {(selectedType === 'menu' || selectedType === 'directory') && (
                <FormField
                  control={form.control}
                  name="icon"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>图标</FormLabel>
                      <FormControl>
                        <IconPicker
                          value={field.value || null}
                          onChange={field.onChange}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* 组件路径 - 仅菜单类型显示 */}
              {selectedType === 'menu' && (
                <FormField
                  control={form.control}
                  name="component"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>组件路径</FormLabel>
                      <FormControl>
                        <Input placeholder="请输入组件路径" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* 显示排序 */}
              <FormField
                control={form.control}
                name="sort_order"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>显示排序</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        placeholder="0"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 是否隐藏 */}
              {(selectedType === 'menu' || selectedType === 'directory') && (
                  <FormField
                    control={form.control}
                    name="is_hidden"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>是否隐藏</FormLabel>
                        <FormControl>
                          <RadioGroup
                            value={field.value}
                            onValueChange={field.onChange}
                            className="flex items-center gap-4"
                          >
                            <div className="flex items-center space-x-2">
                              <RadioGroupItem value="0" id="hidden-no" />
                              <Label htmlFor="hidden-no">否</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <RadioGroupItem value="1" id="hidden-yes" />
                              <Label htmlFor="hidden-yes">是</Label>
                            </div>
                          </RadioGroup>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
              )}

              {/* 权限描述 */}
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>权限描述</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="请输入权限描述"
                        className="resize-none"
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* 权限状态 */}
              <FormField
                control={form.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>权限状态</FormLabel>
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
            </div>

            <DialogFooter className="px-6 py-4 border-t">
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
          </form>
        </Form>
      </DialogContent>
    </Dialog>
    
    {/* 级联停用确认对话框 */}
    <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
      <AlertDialogContent className="sm:max-w-sm">
        <AlertDialogHeader>
          <AlertDialogTitle>确认停用权限</AlertDialogTitle>
          <AlertDialogDescription>
            该权限有 {childCount} 个子权限，停用后将同时停用所有子权限。是否继续？
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
