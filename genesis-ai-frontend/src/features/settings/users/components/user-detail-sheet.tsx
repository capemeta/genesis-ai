/**
 * 用户详情抽屉组件
 */
import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { fetchUser, type UserListItem } from '@/lib/api/user'
import { formatDate } from '@/lib/utils'

interface UserDetailSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: UserListItem
}

function getStatusBadge(status: 'active' | 'disabled' | 'locked') {
  switch (status) {
    case 'active':
      return <Badge variant='default'>正常</Badge>
    case 'disabled':
      return <Badge variant='secondary'>禁用</Badge>
    case 'locked':
      return <Badge variant='destructive'>锁定</Badge>
    default:
      return <Badge variant='outline'>{status}</Badge>
  }
}

function DetailItem({
  label,
  value,
}: {
  label: string
  value?: string | null
}) {
  return (
    <div className='space-y-1'>
      <div className='text-xs font-medium tracking-wide text-muted-foreground'>{label}</div>
      <div className='text-sm leading-6 text-foreground'>{value || '-'}</div>
    </div>
  )
}

export function UserDetailSheet({
  open,
  onOpenChange,
  user,
}: UserDetailSheetProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['user-detail', user?.id],
    queryFn: () => fetchUser(user!.id),
    enabled: open && !!user?.id,
  })

  const detail = data
  const displayName = detail?.nickname || detail?.username || user?.nickname || user?.username || '-'
  const avatarFallback = displayName.slice(0, 1).toUpperCase()

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side='right' className='w-full max-w-2xl gap-0 p-0 sm:max-w-2xl'>
        <SheetHeader className='border-b px-6 py-5'>
          <SheetTitle>用户详情</SheetTitle>
          <SheetDescription>查看用户资料、账号状态、角色分配和审计信息。</SheetDescription>
        </SheetHeader>

        <div className='flex-1 overflow-y-auto px-6 py-5'>
          {isLoading || !detail ? (
            <div className='py-12 text-center text-sm text-muted-foreground'>正在加载用户详情...</div>
          ) : (
            <div className='space-y-8'>
              <section className='rounded-xl border bg-muted/20 p-5'>
                <div className='flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between'>
                  <div className='flex items-center gap-4'>
                    <Avatar className='size-16 border'>
                      <AvatarImage src={detail.avatar_url} alt={displayName} />
                      <AvatarFallback className='text-lg font-semibold'>{avatarFallback}</AvatarFallback>
                    </Avatar>
                    <div className='space-y-2'>
                      <div>
                        <div className='text-xl font-semibold'>{displayName}</div>
                        <div className='text-sm text-muted-foreground'>@{detail.username}</div>
                      </div>
                      <div className='flex flex-wrap items-center gap-2'>
                        {getStatusBadge(detail.status)}
                        <Badge variant={detail.email_verified_at ? 'default' : 'outline'}>
                          邮箱{detail.email_verified_at ? '已验证' : '未验证'}
                        </Badge>
                        <Badge variant={detail.phone_verified_at ? 'default' : 'outline'}>
                          手机{detail.phone_verified_at ? '已验证' : '未验证'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                  <div className='text-sm text-muted-foreground'>
                    创建于 {formatDate(detail.created_at)}
                  </div>
                </div>
              </section>

              <section className='space-y-4'>
                <h3 className='text-sm font-semibold'>基础资料</h3>
                <div className='grid gap-4 rounded-xl border p-5 md:grid-cols-2'>
                  <DetailItem label='昵称' value={detail.nickname} />
                  <DetailItem label='邮箱' value={detail.email} />
                  <DetailItem label='手机号' value={detail.phone} />
                  <DetailItem label='职位' value={detail.job_title} />
                  <DetailItem label='工号' value={detail.employee_no} />
                  <DetailItem label='所属部门' value={detail.organization_name} />
                  <div className='space-y-1 md:col-span-2'>
                    <div className='text-xs font-medium tracking-wide text-muted-foreground'>个人简介</div>
                    <div className='text-sm leading-6 text-foreground whitespace-pre-wrap'>
                      {detail.bio || '-'}
                    </div>
                  </div>
                </div>
              </section>

              <section className='space-y-4'>
                <h3 className='text-sm font-semibold'>角色与登录</h3>
                <div className='grid gap-4 rounded-xl border p-5 md:grid-cols-2'>
                  <div className='space-y-2 md:col-span-2'>
                    <div className='text-xs font-medium tracking-wide text-muted-foreground'>角色</div>
                    <div className='flex flex-wrap gap-2'>
                      {detail.role_names && detail.role_names.length > 0 ? (
                        detail.role_names.map((roleName) => (
                          <Badge key={roleName} variant='secondary'>
                            {roleName}
                          </Badge>
                        ))
                      ) : (
                        <span className='text-sm text-muted-foreground'>未分配角色</span>
                      )}
                    </div>
                  </div>
                  <DetailItem label='最近登录时间' value={detail.last_login_at ? formatDate(detail.last_login_at) : '-'} />
                  <DetailItem label='最近登录 IP' value={detail.last_login_ip} />
                  <DetailItem label='最近活跃时间' value={detail.last_active_at ? formatDate(detail.last_active_at) : '-'} />
                  <DetailItem label='最近修改密码' value={detail.password_changed_at ? formatDate(detail.password_changed_at) : '-'} />
                </div>
              </section>

              <section className='space-y-4'>
                <h3 className='text-sm font-semibold'>安全状态</h3>
                <div className='grid gap-4 rounded-xl border p-5 md:grid-cols-2'>
                  <DetailItem
                    label='邮箱验证时间'
                    value={detail.email_verified_at ? formatDate(detail.email_verified_at) : '-'}
                  />
                  <DetailItem
                    label='手机验证时间'
                    value={detail.phone_verified_at ? formatDate(detail.phone_verified_at) : '-'}
                  />
                  <DetailItem
                    label='失败登录次数'
                    value={String(detail.failed_login_count ?? 0)}
                  />
                  <DetailItem
                    label='锁定截止时间'
                    value={detail.locked_until ? formatDate(detail.locked_until) : '-'}
                  />
                </div>
              </section>

              <section className='space-y-4'>
                <h3 className='text-sm font-semibold'>审计信息</h3>
                <div className='grid gap-4 rounded-xl border p-5 md:grid-cols-2'>
                  <DetailItem label='创建人' value={detail.created_by_name} />
                  <DetailItem label='最后修改人' value={detail.updated_by_name} />
                  <DetailItem label='创建时间' value={formatDate(detail.created_at)} />
                  <DetailItem label='最后更新时间' value={formatDate(detail.updated_at)} />
                  <DetailItem label='激活时间' value={detail.activated_at ? formatDate(detail.activated_at) : '-'} />
                </div>
              </section>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
