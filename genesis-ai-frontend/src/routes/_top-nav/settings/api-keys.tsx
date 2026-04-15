import { createFileRoute } from '@tanstack/react-router'
import { Key } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export const Route = createFileRoute('/_top-nav/settings/api-keys')({
  component: ApiKeysPage,
})

function ApiKeysPage() {
  return (
    <div>
      <div className='mb-8'>
        <h1 className='text-3xl font-bold tracking-tight mb-2'>API Keys</h1>
        <p className='text-muted-foreground'>
          Manage API keys for external integrations and services.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className='flex items-center gap-3'>
            <Key className='h-8 w-8 text-primary' />
            <div>
              <CardTitle>API Key Management</CardTitle>
              <CardDescription>
                Create and manage your API keys
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className='text-muted-foreground'>API Keys management coming soon...</p>
        </CardContent>
      </Card>
    </div>
  )
}
