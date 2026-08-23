import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Download, ShieldCheck, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api/client'
import { usersApi } from '@/lib/api/users'
import { useAuth } from '@/providers/auth-provider'

export function PrivacySection() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')

  const exportData = useMutation({
    mutationFn: usersApi.exportData,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'meus-dados-concurso-mestre-ia.json'
      link.click()
      URL.revokeObjectURL(url)
      toast.success('Exportação concluída.')
    },
    onError: () => toast.error('Não foi possível exportar seus dados agora.'),
  })

  const deleteAccount = useMutation({
    mutationFn: () => usersApi.deleteAccount(password),
    onSuccess: async () => {
      toast.success('Conta excluída. Seus dados pessoais foram anonimizados.')
      await logout()
      navigate('/entrar', { replace: true })
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível excluir a conta.',
      ),
  })

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-success" aria-hidden /> Seus dados
          </CardTitle>
          <CardDescription>
            Você pode baixar tudo o que guardamos sobre sua conta, a qualquer momento.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">
            O arquivo inclui cadastro, perfil, consentimentos registrados, sessões ativas e o
            histórico de atividades da conta.
          </p>
          <Button
            variant="outline"
            onClick={() => exportData.mutate()}
            loading={exportData.isPending}
          >
            <Download /> Exportar meus dados (JSON)
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-danger">
            <Trash2 className="size-4" aria-hidden /> Excluir minha conta
          </CardTitle>
          <CardDescription>Ação definitiva: não é possível desfazer.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Alert tone="warning">
            Seus dados pessoais são anonimizados e todos os acessos são revogados. Registros de
            auditoria exigidos por lei são preservados sem identificar você.
          </Alert>
          <Button variant="danger" onClick={() => setOpen(true)}>
            Excluir conta
          </Button>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir conta definitivamente</DialogTitle>
            <DialogDescription>
              Confirme com sua senha. Ao continuar, sua conta é anonimizada e você é
              desconectado de todos os dispositivos.
            </DialogDescription>
          </DialogHeader>
          <Field label="Sua senha" htmlFor="delete_password">
            <Input
              id="delete_password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              disabled={password.length === 0}
              loading={deleteAccount.isPending}
              onClick={() => deleteAccount.mutate()}
            >
              Excluir minha conta
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
