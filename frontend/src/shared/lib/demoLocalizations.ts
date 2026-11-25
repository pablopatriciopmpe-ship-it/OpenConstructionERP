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
  | 'price_index_series';

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

const DEMO_PRICE_INDEX_SERIES: Record<string, string> = {
  'General Construction Cost Index': 'Índice Geral de Custo da Construção',
};

const MAPS: Record<DemoLocalizableKind, Record<string, string>> = {
  resource: DEMO_RESOURCE_NAMES,
  assembly: DEMO_ASSEMBLY_NAMES,
  waste_factor_label: DEMO_WASTE_FACTOR_LABELS,
  price_index_series: DEMO_PRICE_INDEX_SERIES,
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
