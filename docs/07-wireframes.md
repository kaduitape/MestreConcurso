# 7–9. Wireframes Textuais

Grid base: 12 colunas, gutter 24 px, container 1440 px, sidebar 264 px (colapsa em 72 px), topbar 64 px.
Radius 14 px, sombra suave em 2 níveis, glass discreto só em topbar e command palette.

## 7. Dashboard "HOJE"

```
┌─ SIDEBAR 264 ─┐┌──────────────────────── TOPBAR 64 ─────────────────────────┐
│ ⬢ Mestre IA   ││ [⌘K Buscar…]        🔔3  🌗  [ Avatar ▾ ]                  │
│               │└────────────────────────────────────────────────────────────┘
│ ▸ Hoje        │┌────────────────────────────────────────────────────────────┐
│   Plano       ││ Bom dia, Carlos.            PCDF · Agente · CESPE          │
│   Calendário  ││ ┌──────────┬──────────┬──────────┬──────────┬───────────┐  │
│   Questões    ││ │ 87 dias  │ Mestre   │ 12h/sem  │ Acertos  │ Sequência │  │
│   Simulados   ││ │ p/ prova │ 742/1000 │ ▁▃▅▆▇    │ 71,4%    │ 🔥 12 dias│  │
│   Flashcards  ││ └──────────┴──────────┴──────────┴──────────┴───────────┘  │
│   Meus Erros  ││                                                            │
│   Edital      ││ ┌───────────── SUA MISSÃO DE HOJE ─── 1h45 ──────────────┐ │
│   Mestre IA ✦ ││ │ ● Direito Penal · Crimes contra a pessoa      25 min   │ │
│   Analytics   ││ │   por quê? ▸ incidência 18% · revisão vencida há 2d    │ │
│ ─────────────  ││ │ ● Português · Crase                           30 min   │ │
│   Perfil      ││ │ ● LEP · Regime disciplinar                     25 min   │ │
│   Assinatura  ││ │ ● 14 flashcards vencidos                       10 min   │ │
│               ││ │ ● 20 questões dirigidas                        15 min   │ │
│ [FREE ▸ PRO]  ││ │                                                        │ │
└───────────────┘│ │            ┏━━━━━━━━━━━━━━━━━━━━━━━┓                    │ │
                 │ │            ┃  ▶ COMEÇAR ESTUDO     ┃  [Tenho 30 min ▾] │ │
                 │ │            ┗━━━━━━━━━━━━━━━━━━━━━━━┛                    │ │
                 │ └────────────────────────────────────────────────────────┘ │
                 │ ┌────────── 7 col ──────────┐┌─────── 5 col ─────────────┐ │
                 │ │ CAMINHO DA APROVAÇÃO      ││ REVISÕES PENDENTES (17)   │ │
                 │ │ ●──●──●──○──○──○──🏁      ││ LEP · Português · Const.  │ │
                 │ │ cobertura do edital 46%   ││ [Revisar agora]           │ │
                 │ ├───────────────────────────┤├───────────────────────────┤ │
                 │ │ SE A PROVA FOSSE HOJE     ││ PONTOS FRACOS             │ │
                 │ │ 68–74 pts (IC 80%)        ││ Crase        38% ▁▂       │ │
                 │ │ maior ganho: LEP +4       ││ Prazos LEP   41% ▁▃       │ │
                 │ │ ⓘ estimativa, não garantia││ [Treinar pontos fracos]   │ │
                 │ └───────────────────────────┘└───────────────────────────┘ │
                 └────────────────────────────────────────────────────────────┘
```

Estados: **sem plano** → hero único "Envie seu edital / Escolha um concurso"; **plano sem dados de desempenho** → missão baseada só em edital + incidência, com selo `ESTIMATIVA`; **offline** → missão do dia em cache, cronômetro local.

## 8. RAIO-X DO EDITAL

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Editais    RAIO-X · PCDF 2025 · Agente de Polícia   [OFICIAL] [Ver PDF] │
│ Banca CESPE/CEBRASPE · 1 200 vagas · R$ 8.157,00 · Prova 15/03/2026      │
├──────────────────────────────────────────────────────────────────────────┤
│ ┌──────┬──────┬───────┬───────┬───────┬────────┬────────┬──────────────┐ │
│ │ 87   │ 14   │ 120   │ 1200  │ R$8,1k│ Difi-  │ 12h    │ Preparação   │ │
│ │ dias │ disc.│ quest.│ vagas │ salár.│ culdade│ /sem   │ 46% ▓▓▓▓░░░  │ │
│ └──────┴──────┴───────┴───────┴───────┴────────┴────────┴──────────────┘ │
│                                                                          │
│ DISCIPLINAS MAIS IMPORTANTES          │ PONTOS DE ATENÇÃO                │
│ ▸ Direito Penal      peso 3 · 20q ███ │ ⚠ Nota mínima 50% por bloco      │
│ ▸ LEP                peso 3 · 15q ███ │ ⚠ TAF eliminatório (03/05)       │
│ ▸ Português          peso 2 · 20q ██  │ ⚠ Investigação social            │
│ ▸ Constitucional     peso 2 · 15q ██  │ ⚠ Discursiva peso 40%            │
│                                       │                                  │
│ CONTEÚDOS MAIS EXTENSOS               │ DATAS CRÍTICAS                   │
│ Penal · Parte especial   38 subtópicos│ 10/01 fim das inscrições         │
│ Português · Sintaxe      21 subtópicos│ 15/03 prova objetiva             │
│                                       │ 03/05 TAF                        │
│ POSSÍVEIS GARGALOS (seu perfil)       │                                  │
│ Informática 0% estudado · 8 questões  │ REGRAS ELIMINATÓRIAS             │
│ Estatística marcada como "difícil"    │ art. 9.4 · p. 12 [ver no PDF]    │
├──────────────────────────────────────────────────────────────────────────┤
│ Cobertura da extração: 92% OFICIAL · 6% INFERIDO · 2% NÃO LOCALIZADO     │
│ [Revisar 4 campos inferidos]                    [GERAR MEU PLANO ▸]      │
└──────────────────────────────────────────────────────────────────────────┘
```

Cada valor tem badge de origem e, ao clicar, abre drawer com a citação e a página do PDF (`OFICIAL`, `INFERIDO`, `NÃO LOCALIZADO`, `ESTIMATIVA`). Campo não localizado nunca vira número — vira convite a preencher.

**Durante o processamento** (WebSocket), a tela mostra checklist progressivo, não spinner:

```
Analisando seu edital…
✓ PDF recebido (84 páginas)   ✓ Banca identificada: CESPE
✓ Texto extraído (sem OCR)    ✓ 14 disciplinas · 187 assuntos
→ Cruzando incidência histórica…                     [ 68% ]
```

## 9. MESTRE IA

```
┌── Contexto ──────┐┌──────────────── CONVERSA ────────────────┐┌ Evidências ─┐
│ Edital PCDF ▾    ││ Você: por que errei a 47 do simulado?    ││ 📄 Edital   │
│ Banca CESPE      ││                                          ││  p.34 §2    │
│ Foco: LEP        ││ Mestre ✦                                 ││  "regime…"  │
│                  ││ Você marcou C. O erro foi de REGRA ×     ││ 📊 Incidên- │
│ Sugestões        ││ EXCEÇÃO: o art. 112 admite…              ││  cia 12%    │
│ • Explique crase ││ ┌ 🎣 PEGADINHA ─────────────────────┐    ││  (48 provas)│
│ • Como a CESPE   ││ │ "sempre" invalida a alternativa   │    ││ ❓ Questão  │
│   cobra isso?    ││ └───────────────────────────────────┘    ││  47 CESPE   │
│ • Crie 10 quest. ││ [Criar flashcards] [10 questões] [Revisar]│  2023       │
│ • Revisão 5 min  ││                                          ││             │
│                  ││ ┌──────────────────────────────────────┐ ││ Tokens 1,2k │
│ Histórico ▾      ││ │ Pergunte ao Mestre…      [✦ Enviar] │ ││ Plano: PRO  │
└──────────────────┘└──────────────────────────────────────────┘└─────────────┘
```

Regras de UI: streaming token a token; toda afirmação factual traz chip de citação clicável; ação que escreve no plano do aluno abre confirmação; sem evidência suficiente, o Mestre responde "não encontrei isso no seu edital" e oferece busca ampliada.
