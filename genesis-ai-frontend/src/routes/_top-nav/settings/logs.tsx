import { createFileRoute } from '@tanstack/react-router'
import { FileText } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export const Route = createFileRoute('/_top-nav/settings/logs')({
  component: LogsPage,
})

function LogsPage() {
  return (
    <div>
      <div className='mb-8'>
        <h1 className='text-3xl font-bold tracking-tight mb-2'>Logs & Audit</h1>
        <p className='text-muted-foreground'>
          View system logs and audit trails for security and compliance.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className='flex items-center gap-3'>
            <FileText className='h-8 w-8 text-primary' />
            <div>
              <CardTitle>System Logs</CardTitle>
              <CardDescription>
                Monitor system activity and audit trails
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className='text-muted-foreground'>Logs & Audit interface coming soon...</p>
        </CardContent>
      </Card>
    </div>
  )
}
