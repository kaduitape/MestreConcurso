import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Pause, Play, Sparkles, Volume2, VolumeX } from 'lucide-react'
import strategistCharacter from '@/assets/game/strategist-character.webp'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { trainingApi } from '@/lib/api/training'
import { ApiError } from '@/lib/api/client'
import type { TrainingScene } from '@/lib/api/types'
import { queryKeys } from '@/lib/query-client'
import { toast } from 'sonner'

function highlight(text: string, keywords: string[], spokenOffset = -1) {
  if (!text) return text
  if (!keywords.length) {
    const start = spokenOffset >= 0 ? Math.max(text.lastIndexOf(' ', spokenOffset) + 1, 0) : -1
    const end = start >= 0 ? (() => {
      const nextSpace = text.indexOf(' ', spokenOffset)
      return nextSpace === -1 ? text.length : nextSpace
    })() : -1
    if (start < 0 || end <= start) return text
    return <>{text.slice(0, start)}<span className="rounded bg-game-cyan/20 text-white">{text.slice(start, end)}</span>{text.slice(end)}</>
  }
  const pattern = new RegExp(`(${keywords.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  let offset = 0
  return text.split(pattern).map((part, index) => {
    const start = offset
    offset += part.length
    const isKeyword = keywords.some((word) => word.toLocaleLowerCase('pt-BR') === part.toLocaleLowerCase('pt-BR'))
    const isBeingRead = spokenOffset >= start && spokenOffset < offset
    if (isKeyword) return <mark key={`${part}-${index}`} className="rounded bg-game-gold/20 px-1 font-bold text-game-gold">{part}</mark>
    return <span key={`${part}-${index}`} className={isBeingRead ? 'rounded bg-game-cyan/20 text-white' : undefined}>{part}</span>
  })
}

export function TrainingPlayerPage() {
  const { publicId = '' } = useParams()
  const training = useQuery({ queryKey: queryKeys.trainingLesson(publicId), queryFn: () => trainingApi.training(publicId) })
  const startProgress = useMutation({ mutationFn: () => trainingApi.startProgress(publicId) })
  const saveProgress = useMutation({ mutationFn: (currentScene: number) => trainingApi.saveProgress(publicId, currentScene) })
  const complete = useMutation({
    mutationFn: () => trainingApi.complete(publicId),
    onSuccess: (progress) => toast.success(progress.xp_awarded ? `Missão concluída: +${progress.xp_awarded} XP.` : 'Missão concluída.'),
    onError: (error: unknown) => toast.error(error instanceof ApiError ? error.message : 'Não foi possível concluir a missão.'),
  })
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [answer, setAnswer] = useState<number | null>(null)
  const [speechEnabled, setSpeechEnabled] = useState(false)
  const [speechActive, setSpeechActive] = useState(false)
  const [spokenOffset, setSpokenOffset] = useState(-1)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [voiceURI, setVoiceURI] = useState('')
  const [rate, setRate] = useState(1)
  const scenes = training.data?.script.scenes ?? []
  const scene = scenes[index]
  const isQuestion = scene?.type === 'question' && Array.isArray(scene.options)

  const stopNarration = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    setSpeechActive(false)
    setSpokenOffset(-1)
  }

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const updateVoices = () => {
      const available = window.speechSynthesis.getVoices()
      setVoices(available)
      setVoiceURI((current) => current || available.find((voice) => voice.lang.toLowerCase().startsWith('pt'))?.voiceURI || available[0]?.voiceURI || '')
    }
    updateVoices()
    window.speechSynthesis.addEventListener('voiceschanged', updateVoices)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', updateVoices)
      window.speechSynthesis.cancel()
    }
  }, [])
  useEffect(() => { setIndex(0); setPlaying(false); setAnswer(null); stopNarration() }, [publicId])
  useEffect(() => {
    if (training.data && !startProgress.data && !startProgress.isPending) startProgress.mutate()
  }, [training.data?.public_id, startProgress.data, startProgress.isPending])
  useEffect(() => {
    if (startProgress.data && scene) saveProgress.mutate(index)
  }, [index, scene, startProgress.data])
  useEffect(() => {
    if (!playing || !startProgress.data) return
    const heartbeat = window.setInterval(() => saveProgress.mutate(index), 15_000)
    return () => window.clearInterval(heartbeat)
  }, [index, playing, startProgress.data])
  useEffect(() => {
    if (!playing || !scene || isQuestion) return
    const timer = window.setTimeout(() => setIndex((value) => Math.min(value + 1, scenes.length - 1)), Math.max(scene.duration ?? 12, 4) * 1000)
    return () => window.clearTimeout(timer)
  }, [isQuestion, playing, scene, scenes.length])
  useEffect(() => { if (index === scenes.length - 1) setPlaying(false) }, [index, scenes.length])
  useEffect(() => {
    if (!speechEnabled || !scene || isQuestion || !('speechSynthesis' in window)) return
    const text = scene.narration || scene.dialogue
    if (!text) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'pt-BR'
    utterance.rate = rate
    utterance.voice = voices.find((voice) => voice.voiceURI === voiceURI) ?? null
    utterance.onstart = () => setSpeechActive(true)
    utterance.onboundary = (event) => setSpokenOffset(event.charIndex)
    utterance.onend = () => { setSpeechActive(false); setSpokenOffset(-1) }
    utterance.onerror = () => { setSpeechActive(false); setSpokenOffset(-1) }
    window.speechSynthesis.speak(utterance)
    return () => window.speechSynthesis.cancel()
  }, [index, isQuestion, rate, scene, speechEnabled, voiceURI, voices])

  const progress = useMemo(() => scenes.length ? ((index + 1) / scenes.length) * 100 : 0, [index, scenes.length])
  if (training.isLoading) return <div className="space-y-4 p-6"><Skeleton className="h-8 w-64" /><Skeleton className="h-96" /></div>
  if (training.isError || !training.data || !scene) return <Alert tone="danger" title="Treinamento indisponível">Este treinamento não foi publicado ou não possui cenas.</Alert>

  return <main className="mx-auto max-w-6xl space-y-5 p-4 pb-24 sm:p-8">
    <Link to="/treinamentos" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"><ChevronLeft className="size-4" /> Biblioteca de treinamentos</Link>
    <header><p className="game-label text-game-purple-light">Dia de treinamento · {training.data.subject}</p><h1 className="mt-1 text-2xl font-extrabold text-white sm:text-3xl">{training.data.title}</h1><p className="mt-2 text-sm text-slate-400">Missão conduzida por {training.data.character_name}</p></header>
    <section className="relative overflow-hidden rounded-3xl border border-game-purple/25 bg-[#080d20] shadow-[0_24px_70px_rgb(0_0_0/0.35)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgb(124_58_237/0.28),transparent_36%)]" />
      <div className="relative grid min-h-[520px] gap-4 p-5 sm:p-8 lg:grid-cols-[280px_1fr]">
        <div className="relative flex min-h-48 items-end justify-center overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-game-purple/15 to-transparent lg:min-h-full">
          <img src={strategistCharacter} alt={training.data.character_name} className={`h-72 object-contain object-bottom drop-shadow-[0_18px_24px_rgb(0_0_0/0.55)] transition duration-500 lg:h-[430px] ${scene.character?.gesture === 'point' ? '-translate-x-4 -rotate-2' : scene.character?.emotion === 'happy' ? 'translate-y-1 scale-[1.03]' : 'animate-[pulse_3s_ease-in-out_infinite]'}`} />
          <span className="absolute bottom-3 rounded-full border border-game-purple/30 bg-[#0d1127]/90 px-3 py-1 text-xs font-bold text-game-purple-light">{training.data.character_name}</span>
        </div>
        <div className="flex min-w-0 flex-col justify-center py-3">
          <span className="w-fit rounded-full border border-game-gold/30 bg-game-gold/10 px-3 py-1 text-[10px] font-bold tracking-wider text-game-gold uppercase">Cena {index + 1} de {scenes.length}</span>
          <h2 className="mt-5 text-balance text-2xl leading-tight font-black text-white sm:text-4xl">{scene.screen_text || training.data.topic}</h2>
          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.045] p-5 text-base leading-relaxed text-slate-200 sm:text-lg">{highlight(scene.dialogue || scene.narration, scene.keywords ?? [], spokenOffset)}</div>
          {(scene.keywords ?? []).length > 0 && <div className="mt-4 flex flex-wrap gap-2">{scene.keywords.map((keyword) => <span key={keyword} className="rounded-lg bg-game-purple/15 px-2.5 py-1 text-xs font-bold text-game-purple-light">{keyword}</span>)}</div>}
          {isQuestion && <Question scene={scene} answer={answer} onAnswer={setAnswer} onContinue={() => { setAnswer(null); setIndex((value) => Math.min(value + 1, scenes.length - 1)) }} />}
        </div>
      </div>
      <div className="relative border-t border-white/10 bg-black/20 p-4 sm:px-8"><div className="h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-gradient-to-r from-game-purple to-game-cyan transition-[width]" style={{ width: `${progress}%` }} /></div><div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2"><Button variant="ghost" size="icon" aria-label="Cena anterior" disabled={index === 0} onClick={() => { setPlaying(false); stopNarration(); setIndex((value) => Math.max(0, value - 1)) }}><ChevronLeft /></Button><Button size="icon" aria-label={playing ? 'Pausar' : 'Reproduzir'} onClick={() => setPlaying((value) => !value)} disabled={isQuestion}><>{playing ? <Pause /> : <Play />}</></Button><Button variant={index === scenes.length - 1 ? 'secondary' : 'ghost'} size={index === scenes.length - 1 ? 'sm' : 'icon'} aria-label={index === scenes.length - 1 ? 'Concluir missão' : 'Próxima cena'} disabled={(isQuestion && answer === null) || complete.isPending || startProgress.isPending} onClick={() => { if (index === scenes.length - 1) { complete.mutate(); return } setPlaying(false); stopNarration(); setAnswer(null); setIndex((value) => Math.min(scenes.length - 1, value + 1)) }}>{index === scenes.length - 1 ? 'Concluir missão' : <ChevronRight />}</Button></div>{voices.length > 0 && <div className="flex items-center gap-2"><Button variant={speechEnabled ? 'secondary' : 'ghost'} size="sm" aria-label={speechEnabled ? 'Desligar narração' : 'Ligar narração'} onClick={() => { if (speechEnabled) stopNarration(); setSpeechEnabled((value) => !value) }}><>{speechEnabled ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}</> {speechActive ? 'Narrando' : 'Narração'}</Button><select aria-label="Voz da narração" className="max-w-36 rounded-md border border-white/15 bg-[#0d1127] px-2 py-1.5 text-xs text-slate-200" value={voiceURI} onChange={(event) => setVoiceURI(event.target.value)}>{voices.map((voice) => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name}</option>)}</select><select aria-label="Velocidade da narração" className="rounded-md border border-white/15 bg-[#0d1127] px-2 py-1.5 text-xs text-slate-200" value={rate} onChange={(event) => setRate(Number(event.target.value))}><option value={0.85}>0,85×</option><option value={1}>1×</option><option value={1.15}>1,15×</option></select></div>}<span className="text-xs text-slate-500">Progresso salvo · XP por conclusão real</span></div></div>
    </section>
  </main>
}

function Question({ scene, answer, onAnswer, onContinue }: { scene: TrainingScene; answer: number | null; onAnswer: (value: number) => void; onContinue: () => void }) {
  const correct = answer !== null && answer === scene.correct_option
  return <div className="mt-5 rounded-2xl border border-game-gold/30 bg-game-gold/10 p-5"><p className="flex items-center gap-2 font-bold text-game-gold"><Sparkles className="size-4" /> Antes de continuar, responda:</p><div className="mt-3 grid gap-2">{scene.options?.map((option, optionIndex) => <button type="button" key={option} onClick={() => onAnswer(optionIndex)} disabled={answer !== null} className={`rounded-xl border p-3 text-left text-sm transition ${answer === optionIndex ? (correct ? 'border-success bg-success/15 text-white' : 'border-danger bg-danger/15 text-white') : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'}`}>{option}</button>)}</div>{answer !== null && <div className="mt-4 text-sm text-slate-200"><p>{correct ? 'Excelente. Os portões estão abertos.' : 'Você caiu em uma pegadinha clássica.'}</p>{scene.feedback && <p className="mt-1 text-slate-400">{scene.feedback}</p>}<Button className="mt-3" size="sm" onClick={onContinue}>Continuar <ChevronRight /></Button></div>}</div>
}
