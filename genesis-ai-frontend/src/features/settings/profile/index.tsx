import { ContentSection } from '../components/content-section'
import { ProfileForm } from './profile-form'

export function SettingsProfile() {
  return (
    <ContentSection
      title='个人资料'
      desc='维护你的基础资料、偏好设置和账号安全信息。'
    >
      <ProfileForm />
    </ContentSection>
  )
}
