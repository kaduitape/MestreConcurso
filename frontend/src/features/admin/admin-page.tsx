import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/feedback/page-header'
import { OverviewSection } from './overview-section'
import { UsersSection } from './users-section'
import { AuditSection } from './audit-section'
import { useAuth } from '@/providers/auth-provider'

export function AdminPage() {
  const { hasPermission } = useAuth()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administração"
        description="Gestão de contas, papéis e trilha de auditoria da plataforma."
      />
      <Tabs defaultValue="visao-geral">
        <TabsList>
          <TabsTrigger value="visao-geral">Visão geral</TabsTrigger>
          {hasPermission('users:read') && <TabsTrigger value="usuarios">Usuários</TabsTrigger>}
          {hasPermission('audit:read') && <TabsTrigger value="auditoria">Auditoria</TabsTrigger>}
        </TabsList>
        <TabsContent value="visao-geral">
          <OverviewSection />
        </TabsContent>
        <TabsContent value="usuarios">
          <UsersSection />
        </TabsContent>
        <TabsContent value="auditoria">
          <AuditSection />
        </TabsContent>
      </Tabs>
    </div>
  )
}
