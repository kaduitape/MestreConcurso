/**
 * Os cargos no Raio-X. Três coisas não podem passar: **cargo sem citação
 * conferida não pode parecer cadastrado**, **a soma de vagas tem de dizer que é
 * soma** (senão 490 parece ser de um cargo só), e **a disciplina tem de dizer
 * de qual cargo é**.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { NoticePositionView, NoticeSubjectView, Radiography } from '@/lib/api/types'
import { RadiographyPanel } from '../radiography-panel'

function cargo(overrides: Partial<NoticePositionView> = {}): NoticePositionView {
  return {
    public_id: 'NP1',
    name: 'Analista Judiciário — Área Administrativa',
    education_level: 'SUPERIOR',
    salary_cents: 1399478,
    vacancies: 150,
    cr_vacancies: null,
    workload_hours: 40,
    questions_count: 120,
    exam_duration_minutes: 240,
    requirements: 'diploma de curso superior em qualquer área',
    evidence_level: 'OFFICIAL',
    page_number: 1,
    quote: 'Analista Judiciario - Area Administrativa: 150 vagas',
    registered: true,
    ...overrides,
  }
}

function disciplina(overrides: Partial<NoticeSubjectView> = {}): NoticeSubjectView {
  return {
    public_id: 'NS1',
    name: 'Língua Portuguesa',
    position_label: null,
    weight: null,
    questions_count: null,
    topics_count: 2,
    topics: ['Crase', 'Ortografia'],
    evidence_level: 'OFFICIAL',
    page_number: 3,
    ...overrides,
  }
}

function radiography(overrides: Partial<Radiography> = {}): Radiography {
  return {
    notice_public_id: 'N1',
    title: 'Edital nº 7/2026',
    status: 'AWAITING_CONFIRMATION',
    exam_date: '2026-04-19',
    days_until_exam: 100,
    page_count: 3,
    positions_count: 1,
    subjects_count: 1,
    topics_count: 2,
    questions_count: 120,
    vacancies: 150,
    salary_cents: 1399478,
    vacancies_all_positions: 150,
    facts: [],
    positions: [cargo()],
    subjects: [disciplina()],
    events: [],
    critical_events: [],
    largest_subjects: [],
    attention_points: [],
    coverage: {},
    ...overrides,
  }
}

describe('RadiographyPanel — cargos', () => {
  it('lista cada cargo com seus próprios números e a citação que o comprova', () => {
    render(
      <RadiographyPanel
        data={radiography({
          positions_count: 3,
          vacancies_all_positions: 490,
          positions: [
            cargo(),
            cargo({
              public_id: 'NP2',
              name: 'Analista Judiciário — Área de Tecnologia',
              vacancies: 40,
              cr_vacancies: 80,
              quote: 'Analista Judiciario - Area de Tecnologia: 40 vagas',
            }),
            cargo({
              public_id: 'NP3',
              name: 'Técnico Judiciário — Área Administrativa',
              education_level: 'MEDIO',
              vacancies: 300,
              salary_cents: 852965,
              quote: 'Tecnico Judiciario - Area Administrativa: 300 vagas',
            }),
          ],
        })}
      />,
    )

    expect(screen.getByText('Cargos do edital')).toBeInTheDocument()
    expect(screen.getByText('Analista Judiciário — Área de Tecnologia')).toBeInTheDocument()
    expect(screen.getByText('Técnico Judiciário — Área Administrativa')).toBeInTheDocument()
    expect(screen.getByText('300 vaga(s)')).toBeInTheDocument()
    // Cadastro de reserva aparece separado, não somado às vagas imediatas.
    expect(screen.getByText('40 vaga(s)')).toBeInTheDocument()
    expect(screen.getByText('CR 80')).toBeInTheDocument()
    // Cada cargo carrega a sua própria citação, não a de um "cargo principal".
    expect(screen.getByText(/Area Administrativa: 150 vagas/)).toBeInTheDocument()
    expect(screen.getByText(/Area de Tecnologia: 40 vagas/)).toBeInTheDocument()
    expect(
      screen.getByText(/Tecnico Judiciario - Area Administrativa: 300 vagas/),
    ).toBeInTheDocument()
  })

  it('cargo sem citação conferida não aparece como cadastrado', () => {
    render(
      <RadiographyPanel
        data={radiography({
          positions: [
            cargo({
              name: 'Oficial de Justiça',
              evidence_level: 'INFERRED',
              page_number: null,
              registered: false,
            }),
          ],
        })}
      />,
    )

    expect(screen.getByText('Oficial de Justiça')).toBeInTheDocument()
    expect(screen.getByText('Inferido')).toBeInTheDocument()
    expect(screen.queryByText('cadastrado')).not.toBeInTheDocument()
    expect(screen.getByText(/não é cadastrado automaticamente/)).toBeInTheDocument()
  })

  it('com vários cargos, o rótulo das vagas diz que é a soma', () => {
    render(
      <RadiographyPanel
        data={radiography({ positions_count: 3, vacancies_all_positions: 490 })}
      />,
    )
    expect(screen.getByText('Vagas (todos os cargos)')).toBeInTheDocument()
    expect(screen.getByText('490')).toBeInTheDocument()
  })

  it('com um cargo só, as vagas são as do cargo e o rótulo não promete soma', () => {
    render(<RadiographyPanel data={radiography()} />)
    expect(screen.getByText('Vagas')).toBeInTheDocument()
    expect(screen.queryByText('Vagas (todos os cargos)')).not.toBeInTheDocument()
  })

  it('a disciplina diz de qual cargo é — ou que vale para todos', () => {
    render(
      <RadiographyPanel
        data={radiography({
          subjects: [
            disciplina(),
            disciplina({
              public_id: 'NS2',
              name: 'Banco de Dados',
              position_label: 'Analista Judiciário — Área de Tecnologia',
            }),
          ],
        })}
      />,
    )

    expect(screen.getByText('todos os cargos')).toBeInTheDocument()
    expect(
      screen.getByText('Analista Judiciário — Área de Tecnologia', { selector: 'span' }),
    ).toBeInTheDocument()
  })
})
