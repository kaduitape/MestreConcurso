# 4. Modelagem Inicial MySQL

Convenções: InnoDB, `utf8mb4_0900_ai_ci`, PK `BIGINT UNSIGNED AUTO_INCREMENT`, chave pública `public_id CHAR(26)` (ULID) exposta na API, `created_at/updated_at DATETIME(6)`, soft delete só onde há exigência legal/histórica (`deleted_at`). Enums em `VARCHAR` + CHECK (evita `ALTER` caro de ENUM nativo). Toda FK com `ON DELETE` explícito.

## 4.1 Identidade e acesso — **Fase 1**

```
users(id, public_id, email UNIQUE, email_verified_at, password_hash,
      full_name, status[ACTIVE|PENDING|SUSPENDED|DELETED], is_superuser,
      last_login_at, failed_login_count, locked_until,
      created_at, updated_at, deleted_at)
  IDX (status), (created_at)

profiles(id, user_id UNIQUE→users ON DELETE CASCADE, avatar_url, phone,
         birth_date, city, state, timezone, locale, theme,
         study_goal, bio, preferences JSON, onboarding_completed_at)

roles(id, slug UNIQUE, name, description, is_system)
permissions(id, slug UNIQUE /* "users:read" */, resource, action, description)
role_permissions(role_id→roles, permission_id→permissions) PK composta
user_roles(user_id→users, role_id→roles, granted_at, granted_by) PK composta

user_sessions(id, public_id, user_id→users ON DELETE CASCADE,
      refresh_token_hash UNIQUE /* sha256 */, family_id, parent_id,
      device_label, user_agent, ip_address, expires_at,
      revoked_at, revoked_reason, last_used_at, created_at)
  IDX (user_id, revoked_at), (expires_at), (family_id)

auth_tokens(id, user_id→users, type[EMAIL_VERIFY|PASSWORD_RESET],
      token_hash UNIQUE, expires_at, used_at, created_at)
  IDX (user_id, type), (expires_at)

audit_logs(id, actor_user_id→users NULL ON DELETE SET NULL, actor_ip,
      action, resource_type, resource_id, status, metadata JSON,
      request_id, created_at)
  IDX (actor_user_id, created_at), (resource_type, resource_id), (action, created_at)

consent_logs(id, user_id→users, kind[TOS|PRIVACY|MARKETING|AI_TRAINING],
      version, granted BOOL, ip_address, user_agent, created_at)
  IDX (user_id, kind, created_at)
```

## 4.2 Comercial — Fase 10 (modelado desde já)

```
plans(id, slug UNIQUE, name, description, price_cents, currency, interval,
      trial_days, is_active, sort_order, metadata JSON)
features(id, slug UNIQUE /* "ai.chat", "notice.analysis" */, name, type[BOOL|QUOTA], unit)
plan_features(plan_id, feature_id, enabled, quota_value, period[DAY|MONTH|CYCLE]) PK composta
subscriptions(id, user_id→users, plan_id→plans, status[TRIALING|ACTIVE|PAST_DUE|CANCELED|EXPIRED],
      started_at, trial_ends_at, current_period_start, current_period_end,
      cancel_at_period_end, canceled_at, gateway, gateway_subscription_id UNIQUE)
  IDX (user_id, status), (current_period_end)
payments(id, subscription_id→subscriptions, user_id→users, amount_cents, currency,
      status, gateway, gateway_payment_id UNIQUE, method, paid_at, raw_payload JSON)
coupons(id, code UNIQUE, type[PERCENT|FIXED], value, max_redemptions, redeemed_count,
      valid_from, valid_until, plan_scope JSON, is_active)
coupon_redemptions(id, coupon_id, user_id, subscription_id, redeemed_at)
usage_limits(id, user_id→users, feature_id→features, period_start, period_end,
      used_value, limit_value) UNIQUE (user_id, feature_id, period_start)
```

## 4.3 Catálogo de concursos — Fase 2

```
exam_boards(id, slug UNIQUE, name, aliases JSON, website, logo_url, description)
organizations(id, slug UNIQUE, name, sphere[FEDERAL|ESTADUAL|MUNICIPAL], uf, logo_url)
competitions(id, slug UNIQUE, organization_id→organizations, exam_board_id→exam_boards,
      name, year, status[ANNOUNCED|OPEN|CLOSED|CANCELED|CONCLUDED],
      exam_date, registration_start, registration_end, vacancies_total, is_public)
  IDX (exam_board_id, year), (status, exam_date)
positions(id, competition_id→competitions, name, education_level, salary_cents,
      vacancies, cr_vacancies, workload, requirements TEXT)
subjects(id, slug UNIQUE, name, color_token, area, is_canonical)
topics(id, subject_id→subjects, parent_id→topics NULL, name, slug, depth,
       path VARCHAR(512) /* materialized path */, sort_order)
  IDX (subject_id, parent_id), (path)
position_subjects(position_id, subject_id, weight, questions_count, min_score) PK composta
```

## 4.4 Editais — Fase 3

```
notices(id, public_id, competition_id NULL, created_by_user_id→users,
      title, kind[MAIN|RECTIFICATION|RESULT], number, published_at,
      status[DRAFT|PROCESSING|AWAITING_CONFIRMATION|CONFIRMED|FAILED],
      source_url, confirmed_at, confirmed_by_user_id)
notice_files(id, notice_id→notices ON DELETE CASCADE, storage_key, original_name,
      mime_type, size_bytes, page_count, checksum_sha256, status, ocr_used,
      error_message, uploaded_by_user_id, created_at)
notice_sections(id, notice_id, code, title, kind[DISCIPLINES|SCHEDULE|REQUIREMENTS|…],
      content MEDIUMTEXT, page_start, page_end, order_index)
notice_facts(id, notice_id, field_path /* "position.salary_cents" */, value JSON,
      evidence_level[OFFICIAL|INFERRED|NOT_FOUND], confidence DECIMAL(4,3),
      page_number, quote TEXT, char_start, char_end, extracted_by, prompt_version,
      reviewed_by_user_id, reviewed_at)
  IDX (notice_id, field_path), (evidence_level)
notice_events(id, notice_id, kind, title, date_start, date_end, is_critical, evidence_ref→notice_facts)
notice_subjects(id, notice_id, position_id, subject_id, raw_label, weight, questions_count, evidence_ref)
notice_topics(id, notice_subject_id, topic_id NULL, raw_label, order_index, evidence_ref)
documents(id, owner_type, owner_id, storage_key, kind, status, meta JSON)
document_chunks(id, document_id→documents ON DELETE CASCADE, chunk_index,
      content MEDIUMTEXT, token_count, page_number, char_start, char_end,
      heading_path, vector_id CHAR(36) /* id no Qdrant */, embedding_model, created_at)
  UNIQUE (document_id, chunk_index); IDX (vector_id)
```

## 4.5 Provas e questões — Fase 5

```
exams(id, competition_id, position_id, exam_board_id, year, phase, name,
      questions_count, duration_minutes, source_url, is_official)
questions(id, public_id, exam_id NULL, exam_board_id, subject_id, topic_id, year,
      statement MEDIUMTEXT, kind[MC|TF|DISCURSIVE], difficulty[EASY|MEDIUM|HARD],
      origin[OFFICIAL|AI_GENERATED|EDITORIAL], status, explanation MEDIUMTEXT, source_note,
      tags JSON, ai_suggestion JSON, reviewed_by_user_id, reviewed_at,
      checksum UNIQUE, created_at)
  IDX (subject_id, topic_id), (exam_board_id, year), (status, origin)
  Reservados para a Fase 6 (ainda **não** criados): `difficulty_score` e `trap_pattern_id`,
  que dependem do Radar de Pegadinhas.
  `ai_suggestion` guarda a classificação sugerida pelo modelo **sem aplicá-la**; ela só vira
  classificação quando `reviewed_by_user_id` é preenchido. O gabarito vive em
  `alternatives.is_correct` — não há ponteiro duplicado na questão para sair de sincronia.
alternatives(id, question_id→questions ON DELETE CASCADE, letter, content TEXT, is_correct, feedback TEXT)
question_stats(question_id PK→questions, attempts, correct_attempts, total_time_seconds,
      last_attempt_at, updated_at)
  A taxa de acerto e o tempo médio são derivados na leitura, não guardados: um percentual
  gravado envelhece; abaixo de 20 respostas ele nem é exibido (`accuracy = NULL`).
trap_patterns(id, public_id, slug UNIQUE, name, category, description, detection_hint,
      example, is_active)
  Categorias de técnica de prova, curadas por pessoas. **Não** são afirmações sobre uma
  banca: quantas vezes alguém caiu em cada padrão é conta sobre os erros da própria pessoa.
topic_incidence(id, scope_key UNIQUE, exam_board_id, subject_id, topic_id NULL,
      subject_name, topic_name, period_start_year, period_end_year, exams_count,
      questions_count, board_questions_count, incidence_pct DECIMAL(5,4),
      trend DECIMAL(6,4) NULL, confidence DECIMAL(4,3), computed_at)
  IDX (exam_board_id, subject_id)
  `scope_key` ("banca:12|disciplina:3|assunto:0|2019-2024") dá identidade estável ao
  recorte, evitando o UNIQUE composto com colunas anuláveis — no MySQL, NULL não colide.
  `trend` é nulo quando a amostra não cobre dois anos: gravar zero seria dizer "estável".
  Recorte sem amostra mínima **não é gravado**.
board_profile_metrics(id, scope_key UNIQUE, exam_board_id, subject_id NULL, metric_slug,
      label, value DECIMAL(6,3), unit, detail JSON, sample_exams, sample_questions,
      period_start_year, period_end_year, confidence DECIMAL(4,3), computed_at)
  IDX (exam_board_id, metric_slug)
user_priorities(id, user_id, study_plan_id NULL, scope_key, subject_id NULL, topic_id NULL,
      label, color_token, score SMALLINT /* 0..100 */, contributions JSON,
      coverage DECIMAL(4,3), missing_signals JSON, computed_at)
  UNIQUE (user_id, scope_key) · IDX (user_id, score)
  `contributions` guarda as parcelas que **somam exatamente** `score`; `missing_signals`
  nomeia os sinais que ainda não existem e valeram zero. É o "POR QUÊ?" da interface,
  gravado junto com o número — não um texto montado depois.
```

> `topic_incidence` e `board_profile_metrics` são **sempre** calculadas por Python a partir de `questions`; guardam tamanho da amostra e período — sem amostra, o front exibe "dados insuficientes", nunca um número.

## 4.6 Estudo — Fases 4/6/8

```
study_plans(id, user_id, competition_id NULL, notice_id NULL, position_id NULL,
      name, status, exam_date, weekly_hours_target, started_at, recalculated_at, config JSON)
study_availability(id, study_plan_id, weekday TINYINT, minutes, period[MORNING|AFTERNOON|NIGHT])
study_tasks(id, study_plan_id, user_id, scheduled_for DATE, kind[THEORY|QUESTIONS|REVIEW|FLASHCARDS|SIMULATION|SPRINT],
      subject_id, topic_id, planned_minutes, actual_minutes, status[PENDING|DONE|SKIPPED|RESCHEDULED],
      priority_score DECIMAL(5,2), score_breakdown JSON, source[PLANNER|AI|USER], order_index)
  IDX (user_id, scheduled_for, status)
study_sessions(id, user_id, study_task_id NULL, subject_id, topic_id, started_at, ended_at,
      focus_seconds, pause_seconds, device, notes)
user_subject_progress(id, user_id, subject_key, subject_label, subject_id NULL,
      color_token, planned_minutes, studied_minutes, tasks_done, tasks_skipped,
      completion DECIMAL(5,4), is_weak_point, last_studied_at)
  UNIQUE (user_id, subject_key) · IDX (user_id, last_studied_at)
  A chave é o `subject_key` do plano (`sub:<slug>` ou `ns:<edital>`), porque o plano pode
  nascer de um edital analisado cuja disciplina ainda não existe no catálogo canônico.
  O Priority Score por disciplina vive em `user_priorities` (seção 4.5).
error_analyses(id, public_id, question_attempt_id UNIQUE, user_id, question_id,
      subject_id NULL, cause[UNKNOWN_CONTENT|INTERPRETATION|CONFUSION|FORGETTING|RUSH|
      TRAP|ALTERNATIVE_DOUBT], trap_pattern_id NULL, note MEDIUMTEXT, source[USER|AI],
      model_slug, prompt_version, rationale MEDIUMTEXT, confirmed_at NULL,
      resolved_at NULL, created_at)
  IDX (user_id, cause), (user_id, created_at)
  Sugestão de IA entra com `source=AI` e `confirmed_at` nulo: aparece como sugestão e
  **não entra em estatística alguma** até que a pessoa confirme. Todo agregado do Caderno
  de Erros filtra por `confirmed_at IS NOT NULL`.
flashcards(id, public_id, user_id NULL /* NULL = global */, subject_id, topic_id,
      front MEDIUMTEXT, back MEDIUMTEXT, hint MEDIUMTEXT, tags JSON, extra JSON,
      origin[USER|AI|QUESTION|ERROR|NOTICE|EDITORIAL], source_ref, source_quote MEDIUMTEXT,
      source_page, source_document, model_slug, prompt_version, checksum, is_active)
  IDX (user_id, subject_id), (origin, is_active)
  `origin` governa o selo exibido. Cartão gerado por IA carrega a citação conferida no
  material — o que não se sustenta é descartado na geração e nunca chega a virar linha.
flashcard_states(id, user_id, flashcard_id, state[NEW|LEARNING|REVIEW|RELEARNING],
      ease_factor DECIMAL(4,3), interval_days, repetitions, lapses, step_index,
      due_on DATE, last_reviewed_at, last_rating, last_breakdown JSON, postponed_count)
  UNIQUE (user_id, flashcard_id) · IDX (user_id, due_on)
  Tabela separada do cartão de propósito: um cartão global é revisado por muita gente, e
  cada pessoa tem seu próprio intervalo. `last_breakdown` guarda o cálculo que produziu o
  intervalo atual — é o "por quê?" que a interface mostra.
flashcard_reviews(id, user_id, flashcard_id, rating[AGAIN|HARD|GOOD|EASY], time_seconds,
      previous_interval_days, next_interval_days, ease_factor, due_on DATE, breakdown JSON)
  IDX (user_id, created_at), (flashcard_id)
revision_queue(id, user_id, item_type[TOPIC|FLASHCARD|QUESTION|VOCAB], item_id,
      due_at, priority_score, times_reviewed, last_result, state) IDX (user_id, due_at, state)
  **Ainda não criada.** A Fase 8 entregou a fila de flashcards; unificar tópicos, questões
  e vocabulário na mesma fila exige decidir como um tópico "vence" — trabalho da Fase 9.
simulations(id, public_id, user_id NULL, competition_id NULL,
      kind[OFFICIAL|BOARD|ERRORS|FINAL_STRETCH|FLASH|CUSTOM|ADAPTIVE],
      name, questions_count, duration_minutes, config JSON, is_template, created_by)
  `config` registra a regra que montou o simulado (e as cotas por disciplina, no oficial):
  a composição é auditável depois, não uma caixa preta.
simulation_questions(simulation_id, question_id, order_index) PK composta
simulation_attempts(id, public_id, simulation_id, user_id, started_at, finished_at, paused_at,
      status[IN_PROGRESS|PAUSED|FINISHED|ABANDONED], score DECIMAL(6,2),
      correct_count, wrong_count, blank_count, elapsed_seconds, analysis JSON)
question_attempts(id, public_id, user_id, question_id, simulation_attempt_id NULL,
      selected_alternative_id NULL, selected_letter, is_correct, is_blank, time_seconds,
      confidence, subject_id, created_at) IDX (user_id, created_at), (user_id, question_id)
  Resposta avulsa e resposta dentro de simulado são a mesma tabela: o histórico do candidato
  é um só, e é dele que sai o "simulado dos erros".
mestre_scores(id, user_id, computed_at, score SMALLINT /* 0..1000 */, components JSON,
      estimated_min DECIMAL(6,2), estimated_max DECIMAL(6,2), confidence)
  IDX (user_id, computed_at)
```

## 4.7 IA, mídia e notificações

```
ai_providers(id, slug UNIQUE, name, is_active, config JSON)
ai_models(id, provider_id, slug, display_name, context_window, input_cost_per_1k,
      output_cost_per_1k, supports_tools, supports_json, is_active)
ai_prompts(id, slug, version, role, template MEDIUMTEXT, variables JSON,
      model_hint, is_active, created_by, created_at) UNIQUE (slug, version)
chat_conversations(id, public_id, user_id, title, mode[TUTOR|TEACHER], notice_id NULL,
      subject_id NULL, is_archived, last_message_at, message_count)
  IDX (user_id, last_message_at)
chat_messages(id, public_id, conversation_id, user_id, role[USER|ASSISTANT],
      content MEDIUMTEXT, claims JSON, sources JSON, computed_context JSON,
      is_refusal, refusal_reason MEDIUMTEXT, grounding_ratio DECIMAL(5,4),
      model_slug, prompt_version, input_tokens, output_tokens, latency_ms)
  IDX (conversation_id, id)
  `claims` guarda cada afirmação com sua situação de origem (CITED/COMPUTED/UNSOURCED),
  a citação, o trecho e a página. `sources` guarda os trechos que entraram no contexto.
  Assim qualquer resposta pode ser auditada depois — e a interface mostra de onde cada
  frase veio, ou diz que ficou sem origem. `grounding_ratio` é a fração de afirmações
  factuais conferidas: número, não impressão.
ai_usage(id, user_id NULL, conversation_id NULL, feature_slug, provider_id, model_id,
      input_tokens, output_tokens, cached_tokens, cost_cents DECIMAL(10,4),
      latency_ms, status, error_code, created_at)
  IDX (user_id, created_at), (feature_slug, created_at)
video_resources(id, public_id, title, url UNIQUE, provider, channel, duration_seconds,
      subject_id NULL, topic_id NULL, summary MEDIUMTEXT, is_active,
      verified_by_user_id NULL, verified_at NULL)
  IDX (subject_id, is_active)
  A plataforma não descobre vídeos sozinha nem inventa links: o catálogo é cadastrado por
  pessoas, e **só o item com `verified_at` preenchido é sugerido pelo Mestre**.
vocabulary_terms(id, public_id, user_id, term, term_key, definition MEDIUMTEXT,
      subject_id NULL, message_id NULL, source_quote MEDIUMTEXT, source_page,
      source_document, origin[CITED|GENERATED], times_reviewed, last_reviewed_at)
  UNIQUE (user_id, term_key) · IDX (user_id, created_at)
  `origin` separa o que veio de trecho citado do que é redação do modelo. A interface não
  apresenta uma definição gerada como se fosse texto do edital.
notifications(id, user_id, kind, title, body, action_url, data JSON, read_at, created_at)
  IDX (user_id, read_at, created_at)
```

## 4.8 Índices e decisões relevantes

- Toda tabela "quente" por usuário começa o índice composto por `user_id`.
- `document_chunks.vector_id` mantém a ponte MySQL ↔ Qdrant (fonte de verdade do texto é MySQL).
- `questions.checksum` (SHA-256 do enunciado normalizado) evita duplicata na ingestão.
- `topic_incidence` e `board_profile_metrics` são tabelas materializadas recomputadas por job, nunca escritas por LLM.
- Contadores derivados (`question_stats`, `*_progress`) são atualizados por worker idempotente, não em request path.
