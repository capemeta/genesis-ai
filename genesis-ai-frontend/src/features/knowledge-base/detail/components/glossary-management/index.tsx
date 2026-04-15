import { GlossaryPage } from '../dictionary-center'

interface GlossaryManagementProps {
  kbId: string
}

export function GlossaryManagement({ kbId }: GlossaryManagementProps) {
  return <GlossaryPage kbId={kbId} />
}
