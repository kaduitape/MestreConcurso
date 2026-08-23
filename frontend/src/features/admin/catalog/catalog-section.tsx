import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BoardsSection } from './boards-section'
import { OrganizationsSection } from './organizations-section'
import { CompetitionsSection } from './competitions-section'
import { SubjectsSection } from './subjects-section'
import { NoticesSection } from './notices-section'

export function CatalogSection() {
  return (
    <Tabs defaultValue="concursos">
      <TabsList>
        <TabsTrigger value="concursos">Concursos</TabsTrigger>
        <TabsTrigger value="bancas">Bancas</TabsTrigger>
        <TabsTrigger value="orgaos">Órgãos</TabsTrigger>
        <TabsTrigger value="disciplinas">Disciplinas</TabsTrigger>
        <TabsTrigger value="editais">Editais</TabsTrigger>
      </TabsList>
      <TabsContent value="concursos">
        <CompetitionsSection />
      </TabsContent>
      <TabsContent value="bancas">
        <BoardsSection />
      </TabsContent>
      <TabsContent value="orgaos">
        <OrganizationsSection />
      </TabsContent>
      <TabsContent value="disciplinas">
        <SubjectsSection />
      </TabsContent>
      <TabsContent value="editais">
        <NoticesSection />
      </TabsContent>
    </Tabs>
  )
}
