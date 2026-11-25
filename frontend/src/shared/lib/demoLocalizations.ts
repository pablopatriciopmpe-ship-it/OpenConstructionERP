/**
 * Presentation-layer localisations for persisted demo/default records that were
 * seeded before the pt-BR UI work. They are keyed by the exact canonical English
 * text stored in the database, so user edits (which change the stored text) are
 * preserved and never overwritten.
 *
 * These maps are intentionally conservative: only the demo identifiers that the
 * QA prints call out are translated. Prices, currencies and units are untouched.
 */

export type DemoLocalizableKind =
  | 'resource'
  | 'assembly'
  | 'waste_factor_label'
  | 'waste_factor_note'
  | 'price_index_series'
  | 'price_index_region';

const DEMO_RESOURCE_NAMES: Record<string, string> = {
  'Project Manager': 'Gerente de projetos',
  'Site Manager': 'Encarregado de obra',
  'Quantity Surveyor': 'Orçamentista',
  'Tower crane': 'Guindaste de torre',
  'Excavator': 'Escavadeira',
};

const DEMO_ASSEMBLY_NAMES: Record<string, string> = {
  'Reinforced concrete wall C25/30 d=20cm':
    'Parede de concreto armado C25/30, espessura 20 cm',
  'Reinforced concrete wall C30/37 d=24cm':
    'Parede de concreto armado C30/37, espessura 24 cm',
  'KSL sand-lime brick wall 11.5cm':
    'Parede de tijolo sílico-calcário KSL, 11,5 cm',
  'KSL sand-lime brick wall 17.5cm':
    'Parede de tijolo sílico-calcário KSL, 17,5 cm',
  'Drywall partition W111 single-stud single-board':
    'Divisória de drywall W111, montante e chapa simples',
  'Drywall partition W112 single-stud double-board':
    'Divisória de drywall W112, montante simples e chapa dupla',
  'In-situ concrete slab d=20cm': 'Laje de concreto moldada in loco, 20 cm',
  'In-situ concrete slab d=25cm': 'Laje de concreto moldada in loco, 25 cm',
  'Flat roof bitumen 2-layer with insulation':
    'Cobertura plana com duas camadas de manta asfáltica e isolamento',
  'ETICS facade insulation EPS 160mm':
    'Isolamento de fachada ETICS com EPS de 160 mm',
  'Interior wood door 90x210cm': 'Porta interna de madeira 90 × 210 cm',
  'Exterior steel door 100x210cm': 'Porta externa de aço 100 × 210 cm',
  'uPVC window double-glazed 120x140cm':
    'Janela de PVC com vidro duplo 120 × 140 cm',
  'Aluminum window triple-glazed 120x140cm':
    'Janela de alumínio com vidro triplo 120 × 140 cm',
  'Ceramic tile floor finish': 'Piso de revestimento cerâmico',
  'Vinyl LVT floor finish': 'Piso vinílico LVT',
  'Engineered parquet floor finish': 'Piso de madeira engenheirada',
  'Copper pipe DN20 installed': 'Tubulação de cobre DN20 instalada',
  'Sanitary WC complete with cistern':
    'Vaso sanitário completo com caixa de descarga',
  'Wall-mounted radiator type 22 600x1000mm':
    'Radiador de parede tipo 22, 600 × 1000 mm',
  'Reinforced concrete column 30x30cm':
    'Pilar de concreto armado 30 × 30 cm',
  'Steel beam HEB200': 'Viga de aço HEB200',
  'Open cut excavation up to 2m depth':
    'Escavação a céu aberto até 2 m de profundidade',
  'Cement screed floor d=5cm': 'Contrapiso cimentício de 5 cm',
  'Backfill with compaction': 'Reaterro com compactação',
};

const DEMO_WASTE_FACTOR_LABELS: Record<string, string> = {
  'Blockwork (breakage + cuts)': 'Alvenaria de blocos (quebras e cortes)',
  'Brickwork (breakage + cuts)': 'Alvenaria de tijolos (quebras e cortes)',
  'Concrete (over-pour + spillage)': 'Concreto (excesso de concretagem e derramamento)',
  'Insulation (cuts + fitting)': 'Isolamento (recortes e instalação)',
  'Plaster / render (mixing + spillage)':
    'Reboco e revestimento argamassado (mistura e perdas)',
  'Reinforcement bar (laps + offcuts)':
    'Aço para armadura (transpasses e sobras)',
  'Floor screed (spillage)': 'Contrapiso (perdas na aplicação)',
  'Structural steel (offcuts)': 'Aço estrutural (sobras de corte)',
  'Tiling (cuts + breakage)': 'Revestimento cerâmico (recortes e quebras)',
  'Timber / carpentry (offcuts)': 'Madeira e carpintaria (sobras de corte)',
};

const DEMO_WASTE_FACTOR_NOTES: Record<string, string> = {
  'Breakage and cutting waste on masonry blockwork.':
    'Perdas por quebras e cortes de blocos de alvenaria.',
  'Breakage and cutting waste on facing and common brickwork.':
    'Perdas por quebras e cortes de tijolos comuns e de fachada.',
  'Allowance for over-pour, spillage and surface irregularity.':
    'Reserva para excesso de concretagem, derramamento e irregularidades da superfície.',
  'Cutting and fitting waste on board and roll insulation.':
    'Perdas por recortes e ajustes de placas e mantas de isolamento.',
  'Mixing loss and spillage on wet plaster and render.':
    'Perdas na mistura e aplicação da argamassa.',
  'Covers lap lengths and bar offcuts beyond the net scheduled steel.':
    'Considera transpasses e sobras de corte além do aço previsto em projeto.',
  'Spillage and level tolerance on sand-cement screed.':
    'Perdas na aplicação e tolerância de nivelamento do contrapiso.',
  'Small offcut allowance on fabricated structural steel.':
    'Pequena reserva para sobras no corte do aço estrutural.',
  'Edge cuts and breakage on wall and floor tiling.':
    'Recortes de borda e quebras em pisos e paredes.',
  'Offcuts and defect cutting on structural and joinery timber.':
    'Sobras de corte e descarte de peças de madeira com defeito.',
};

const DEMO_PRICE_INDEX_SERIES: Record<string, string> = {
  'General Construction Cost Index': 'Índice Geral de Custo da Construção',
};

const DEMO_PRICE_INDEX_REGIONS: Record<string, string> = {
  'High-cost metro area': 'Área metropolitana de custo elevado',
  'Low-cost rural area': 'Área rural de custo reduzido',
  'National average': 'Média nacional',
};

const MAPS: Record<DemoLocalizableKind, Record<string, string>> = {
  resource: DEMO_RESOURCE_NAMES,
  assembly: DEMO_ASSEMBLY_NAMES,
  waste_factor_label: DEMO_WASTE_FACTOR_LABELS,
  waste_factor_note: DEMO_WASTE_FACTOR_NOTES,
  price_index_series: DEMO_PRICE_INDEX_SERIES,
  price_index_region: DEMO_PRICE_INDEX_REGIONS,
};

export function isPortugueseLocale(locale: string | undefined): boolean {
  if (!locale) return false;
  const base = locale.toLowerCase().replace(/_/g, '-').split('-')[0];
  return base === 'pt';
}

export function getDemoDisplayName(
  kind: DemoLocalizableKind,
  raw: string | null | undefined,
  locale: string | undefined,
): string {
  if (!raw || !isPortugueseLocale(locale)) return raw;
  return MAPS[kind][raw] ?? raw;
}
