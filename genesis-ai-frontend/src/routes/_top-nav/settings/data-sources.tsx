import { createFileRoute } from '@tanstack/react-router'
import { Plus, CheckCircle2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export const Route = createFileRoute('/_top-nav/settings/data-sources')({
  component: DataSources,
})

function DataSources() {
  const dataSources = [
    {
      name: 'PostgreSQL',
      type: 'Database',
      status: 'Connected',
      lastSync: '2 mins ago',
      icon: '🐘',
    },
    {
      name: 'MongoDB',
      type: 'Database',
      status: 'Connected',
      lastSync: '5 mins ago',
      icon: '🍃',
    },
    {
      name: 'AWS S3',
      type: 'Storage',
      status: 'Connected',
      lastSync: '10 mins ago',
      icon: '☁️',
    },
    {
      name: 'Elasticsearch',
      type: 'Search',
      status: 'Error',
      lastSync: '1 hour ago',
      icon: '🔍',
    },
  ]

  return (
    <div>
      {/* Header */}
      <div className='mb-6'>
        <div className='flex items-center justify-between mb-4'>
          <div>
            <h1 className='text-3xl font-bold tracking-tight mb-2'>Data Sources</h1>
            <p className='text-muted-foreground'>
              Connect and manage external data sources and integrations.
            </p>
          </div>
          <Button>
            <Plus className='mr-2 h-4 w-4' />
            Add Data Source
          </Button>
        </div>
      </div>

      {/* Data Sources Grid */}
      <div className='grid gap-6 md:grid-cols-2 lg:grid-cols-3'>
        {dataSources.map((source, index) => (
          <Card key={index} className='hover:shadow-md transition-all'>
            <CardHeader>
              <div className='flex items-start justify-between'>
                <div className='flex items-center gap-3'>
                  <div className='text-4xl'>{source.icon}</div>
                  <div>
                    <CardTitle className='text-lg'>{source.name}</CardTitle>
                    <CardDescription>{source.type}</CardDescription>
                  </div>
                </div>
                <Badge
                  variant={source.status === 'Connected' ? 'default' : 'destructive'}
                  className='gap-1'
                >
                  {source.status === 'Connected' ? (
                    <CheckCircle2 className='h-3 w-3' />
                  ) : (
                    <AlertCircle className='h-3 w-3' />
                  )}
                  {source.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className='text-sm text-muted-foreground mb-4'>
                Last sync: {source.lastSync}
              </div>
              <div className='flex gap-2'>
                <Button variant='outline' size='sm' className='flex-1'>
                  Configure
                </Button>
                <Button
                  variant='outline'
                  size='sm'
                  className='flex-1'
                  disabled={source.status === 'Error'}
                >
                  Test Connection
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Add New Card */}
        <Card className='border-dashed cursor-pointer hover:border-primary hover:bg-muted/50 transition-all'>
          <CardContent className='flex flex-col items-center justify-center h-full min-h-[200px] p-6'>
            <div className='flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-4'>
              <Plus className='h-8 w-8 text-primary' />
            </div>
            <h3 className='font-semibold text-lg mb-2'>Add Data Source</h3>
            <p className='text-sm text-muted-foreground text-center'>
              Connect a new data source
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
