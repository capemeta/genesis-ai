import { createFileRoute } from '@tanstack/react-router'
import { Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

export const Route = createFileRoute('/_top-nav/settings/general')({
  component: GeneralSettings,
})

function GeneralSettings() {
  return (
    <div className='max-w-4xl'>
      {/* Header */}
      <div className='mb-6'>
        <h1 className='text-3xl font-bold tracking-tight mb-2'>General Settings</h1>
        <p className='text-muted-foreground'>
          Configure global platform settings and preferences.
        </p>
      </div>

      <div className='space-y-6'>
        {/* Organization */}
        <Card>
          <CardHeader>
            <CardTitle>Organization</CardTitle>
            <CardDescription>
              Basic information about your organization
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='org-name'>Organization Name</Label>
              <Input id='org-name' defaultValue='RAG AI Platform' />
            </div>
            <div className='space-y-2'>
              <Label htmlFor='org-description'>Description</Label>
              <Textarea
                id='org-description'
                defaultValue='Enterprise AI platform for intelligent document processing'
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        {/* Security */}
        <Card>
          <CardHeader>
            <CardTitle>Security</CardTitle>
            <CardDescription>
              Configure security and authentication settings
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>Two-Factor Authentication</div>
                <div className='text-sm text-muted-foreground'>
                  Require 2FA for all users
                </div>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>Password Expiration</div>
                <div className='text-sm text-muted-foreground'>
                  Force password reset every 90 days
                </div>
              </div>
              <Switch />
            </div>
            <Separator />
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>Session Timeout</div>
                <div className='text-sm text-muted-foreground'>
                  Automatically log out inactive users
                </div>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
            <CardDescription>
              Configure email and system notifications
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>Email Notifications</div>
                <div className='text-sm text-muted-foreground'>
                  Send email for important events
                </div>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>Weekly Reports</div>
                <div className='text-sm text-muted-foreground'>
                  Receive weekly usage reports
                </div>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className='flex items-center justify-between'>
              <div>
                <div className='font-medium'>System Alerts</div>
                <div className='text-sm text-muted-foreground'>
                  Get notified about system issues
                </div>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>

        {/* Save Button */}
        <div className='flex justify-end gap-4'>
          <Button variant='outline'>Cancel</Button>
          <Button>
            <Save className='mr-2 h-4 w-4' />
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  )
}
