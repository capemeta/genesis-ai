import { createFileRoute } from '@tanstack/react-router'
import { AgentBuilder } from '@/features/agents'

export const Route = createFileRoute('/_top-nav/agents/$agentId/builder')({
  component: () => <AgentBuilder />,
})
