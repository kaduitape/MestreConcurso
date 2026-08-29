import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/feedback/page-header'
import { OverviewSection } from './overview-section'
import { UsersSection } from './users-section'
import { AuditSection } from './audit-section'
import { CatalogSection } from './catalog/catalog-section'
import { AiSection } from './ai/ai-section'
import { QuestionsSection } from './questions/questions-section'
import { IntelligenceSection } from './intelligence-section'
import { VideosSection } from './videos-section'
import { GameRulesSection } from './game-rules-section'
import { TrainingStudioSection } from './training/training-studio-section'
import { useAuth } from '@/providers/auth-provider'

export function AdminPage() {
  const { hasPermission } = useAuth()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administração"
        description="Contas, catálogo de concursos, provedores de IA e trilha de auditoria."
      />
      <Tabs defaultValue="visao-geral">
        <TabsList className="flex-wrap">
          <TabsTrigger value="visao-geral">Visão geral</TabsTrigger>
          {hasPermission('catalog:read') && (
            <TabsTrigger value="catalogo">Catálogo</TabsTrigger>
          )}
          {hasPermission('questions:read') && (
            <TabsTrigger value="questoes">Questões</TabsTrigger>
          )}
          {hasPermission('ai_settings:read') && (
            <TabsTrigger value="inteligencia">Inteligência</TabsTrigger>
          )}
          {hasPermission('training:read') && <TabsTrigger value="estudio">Estúdio</TabsTrigger>}
          {hasPermission('users:read') && <TabsTrigger value="usuarios">Usuários</TabsTrigger>}
          {hasPermission('audit:read') && (
            <TabsTrigger value="auditoria">Auditoria</TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="visao-geral">
          <OverviewSection />
        </TabsContent>
        <TabsContent value="catalogo">
          <CatalogSection />
        </TabsContent>
        <TabsContent value="questoes">
          <div className="space-y-6">
            <QuestionsSection />
            {hasPermission('intelligence:write') && <IntelligenceSection />}
            {hasPermission('catalog:write') && <VideosSection />}
            {hasPermission('intelligence:write') && <GameRulesSection />}
          </div>
        </TabsContent>
        <TabsContent value="inteligencia">
          <AiSection />
        </TabsContent>
        <TabsContent value="estudio">
          <TrainingStudioSection />
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
