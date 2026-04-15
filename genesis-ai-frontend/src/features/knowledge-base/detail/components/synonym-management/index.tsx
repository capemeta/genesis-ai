import { SynonymPage } from '../dictionary-center'

interface SynonymManagementProps {
  kbId: string
}

export function SynonymManagement({ kbId }: SynonymManagementProps) {
  return <SynonymPage kbId={kbId} />
}
