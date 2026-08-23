import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/feedback/page-header'
import { ProfileSection } from './profile-section'
import { SecuritySection } from './security-section'
import { DevicesSection } from './devices-section'
import { PrivacySection } from './privacy-section'

export function AccountPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Minha conta"
        description="Dados pessoais, segurança, dispositivos conectados e privacidade."
      />
      <Tabs defaultValue="perfil">
        <TabsList>
          <TabsTrigger value="perfil">Perfil</TabsTrigger>
          <TabsTrigger value="seguranca">Segurança</TabsTrigger>
          <TabsTrigger value="dispositivos">Dispositivos</TabsTrigger>
          <TabsTrigger value="privacidade">Privacidade</TabsTrigger>
        </TabsList>
        <TabsContent value="perfil">
          <ProfileSection />
        </TabsContent>
        <TabsContent value="seguranca">
          <SecuritySection />
        </TabsContent>
        <TabsContent value="dispositivos">
          <DevicesSection />
        </TabsContent>
        <TabsContent value="privacidade">
          <PrivacySection />
        </TabsContent>
      </Tabs>
    </div>
  )
}
