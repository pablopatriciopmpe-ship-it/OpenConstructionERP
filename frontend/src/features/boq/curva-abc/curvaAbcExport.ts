// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
/**
 * Exportadores da Curva ABC para Excel (.xlsx) e PDF (.pdf).
 *
 * Atende às especificações:
 * - Excel com 3 abas: Resumo, Categorias (Insumos) e Serviços, com cores por classe.
 * - PDF executivo completo contendo as 3 visões (Resumo, Serviços e Insumos).
 * - Formatação integral em pt-BR (R$, percentuais com duas casas decimais, datas).
 * - Cores e identidade visual dos tokens Evolux Obras.
 */

import type * as ExcelJSType from 'exceljs';
import type { jsPDF as JsPDFType } from 'jspdf';
import type { CurvaAbcResult } from './curvaAbcCalculations';
import { getCategoriaLabel } from './curvaAbcCalculations';

export interface ExportCurvaAbcOptions {
  projectName: string;
  boqName: string;
  servicesResult: CurvaAbcResult;
  resourcesResult: CurvaAbcResult;
  currencySymbol?: string;
  date?: Date;
}

/** Formata número no padrão monetário brasileiro R$ 1.234.567,89 */
export function formatMoneyPtBr(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** Formata percentual no padrão brasileiro 80,00% */
export function formatPercentPtBr(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + '%';
}

/** Formata data no padrão brasileiro DD/MM/AAAA */
export function formatDatePtBr(d: Date = new Date()): string {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(d);
}

/** Dispara download de blob no navegador */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Cores dos tokens Evolux Obras para estilos de planilhas e relatórios.
 */
const TOKENS = {
  ink: '163953',        // Azul primário (#163953)
  action: '156D61',     // Verde ação (#156D61)
  canvas: 'F6F6EF',     // Fundo papel (#F6F6EF)
  line: 'CED8D5',       // Divisores (#CED8D5)
  classA_bg: 'E2F2EC',  // Fundo verde claro para Classe A (#E2F2EC)
  classA_ink: '12594D', // Texto verde escuro para Classe A (#12594D)
  classB_bg: 'DCEEE9',  // Fundo azul/verde suave para Classe B (#DCEEE9)
  classB_ink: '163953', // Texto azul escuro para Classe B (#163953)
  classC_bg: 'F6F6EF',  // Fundo neutro papel para Classe C (#F6F6EF)
  classC_ink: '465C69', // Texto neutro para Classe C (#465C69)
};

/**
 * Gera e baixa o arquivo Excel (.xlsx) da Curva ABC com 3 abas:
 * 1. Resumo: Visão executiva das classes A, B e C com totais e percentuais.
 * 2. Categorias: Insumos agregados por tipo com classificação e cores por classe.
 * 3. Serviços: Itens e etapas da planilha orçamentária com cores por classe.
 */
export async function exportCurvaAbcToExcel(options: ExportCurvaAbcOptions): Promise<void> {
  const ExcelJsMod = await import('exceljs');
  const WorkbookCtor = (ExcelJsMod.Workbook ?? ExcelJsMod.default.Workbook) as typeof ExcelJSType.Workbook;
  const wb = new WorkbookCtor();

  wb.creator = 'Evolux Obras';
  wb.created = options.date ?? new Date();

  const formattedDate = formatDatePtBr(options.date);
  const safeProjectName = options.projectName || 'Projeto';

  // ─────────────────────────────────────────────────────────────────────────────
  // 1ª ABA: Resumo
  // ─────────────────────────────────────────────────────────────────────────────
  const wsResumo = wb.addWorksheet('Resumo', {
    views: [{ showGridLines: true }],
  });

  wsResumo.columns = [
    { width: 14 }, // Classe
    { width: 22 }, // Faixa %
    { width: 16 }, // Qtd Serviços
    { width: 24 }, // Total Serviços (R$)
    { width: 16 }, // % Serviços
    { width: 16 }, // Qtd Insumos
    { width: 24 }, // Total Insumos (R$)
    { width: 16 }, // % Insumos
  ];

  // Cabeçalho de Identificação
  const titleRow = wsResumo.addRow(['Evolux Obras · Relatório de Curva ABC e Análise de Pareto']);
  titleRow.font = { name: 'Arial', size: 14, bold: true, color: { argb: 'FFFFFFFF' } };
  titleRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.ink}` } };
  titleRow.alignment = { vertical: 'middle', indent: 1 };
  wsResumo.mergeCells(1, 1, 1, 8);
  wsResumo.getRow(1).height = 32;

  wsResumo.addRow([]);
  wsResumo.addRow(['Projeto:', safeProjectName]);
  wsResumo.addRow(['Orçamento:', options.boqName || 'Planilha Orçamentária']);
  wsResumo.addRow(['Data de Emissão:', formattedDate]);
  wsResumo.addRow(['Critério de Corte:', `Classe A: 0% a ${options.servicesResult.cutoff_a}% | Classe B: ${options.servicesResult.cutoff_a}% a ${options.servicesResult.cutoff_b}% | Classe C: acima de ${options.servicesResult.cutoff_b}%`]);
  wsResumo.addRow(['Total do Orçamento:', formatMoneyPtBr(options.servicesResult.grand_total)]);

  for (let r = 3; r <= 7; r++) {
    const row = wsResumo.getRow(r);
    row.getCell(1).font = { bold: true, color: { argb: `FF${TOKENS.ink}` } };
  }

  wsResumo.addRow([]);

  // Tabela Resumo Executivo
  const tableHeader = wsResumo.addRow([
    'Classe',
    'Faixa Percentual',
    'Qtd. Serviços',
    'Total Serviços (R$)',
    '% Serviços',
    'Qtd. Insumos',
    'Total Insumos (R$)',
    '% Insumos',
  ]);
  tableHeader.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  tableHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.ink}` } };
  tableHeader.alignment = { horizontal: 'center', vertical: 'middle' };
  tableHeader.height = 24;

  const sSum = options.servicesResult.summary;
  const rSum = options.resourcesResult.summary;

  const classesConfig: Array<{
    label: string;
    faixa: string;
    sMetrics: typeof sSum.A;
    rMetrics: typeof rSum.A;
    bg: string;
    ink: string;
  }> = [
    {
      label: 'Classe A',
      faixa: `0,00% a ${options.servicesResult.cutoff_a},00%`,
      sMetrics: sSum.A,
      rMetrics: rSum.A,
      bg: TOKENS.classA_bg,
      ink: TOKENS.classA_ink,
    },
    {
      label: 'Classe B',
      faixa: `${options.servicesResult.cutoff_a},00% a ${options.servicesResult.cutoff_b},00%`,
      sMetrics: sSum.B,
      rMetrics: rSum.B,
      bg: TOKENS.classB_bg,
      ink: TOKENS.classB_ink,
    },
    {
      label: 'Classe C',
      faixa: `${options.servicesResult.cutoff_b},00% a 100,00%`,
      sMetrics: sSum.C,
      rMetrics: rSum.C,
      bg: TOKENS.classC_bg,
      ink: TOKENS.classC_ink,
    },
  ];

  for (const c of classesConfig) {
    const row = wsResumo.addRow([
      c.label,
      c.faixa,
      c.sMetrics.count,
      c.sMetrics.total,
      c.sMetrics.percentage / 100,
      c.rMetrics.count,
      c.rMetrics.total,
      c.rMetrics.percentage / 100,
    ]);
    row.height = 22;
    row.getCell(1).font = { bold: true, color: { argb: `FF${c.ink}` } };
    row.getCell(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${c.bg}` } };
    row.getCell(3).alignment = { horizontal: 'right' };
    row.getCell(4).numFmt = 'R$ #,##0.00';
    row.getCell(5).numFmt = '0.00%';
    row.getCell(6).alignment = { horizontal: 'right' };
    row.getCell(7).numFmt = 'R$ #,##0.00';
    row.getCell(8).numFmt = '0.00%';
  }

  // Linha Total Geral
  const totalRow = wsResumo.addRow([
    'Total Geral',
    '100,00%',
    options.servicesResult.total_count,
    options.servicesResult.grand_total,
    1,
    options.resourcesResult.total_count,
    options.resourcesResult.grand_total,
    1,
  ]);
  totalRow.height = 24;
  totalRow.font = { bold: true };
  totalRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE5E7EB' } };
  totalRow.getCell(4).numFmt = 'R$ #,##0.00';
  totalRow.getCell(5).numFmt = '0.00%';
  totalRow.getCell(7).numFmt = 'R$ #,##0.00';
  totalRow.getCell(8).numFmt = '0.00%';

  // ─────────────────────────────────────────────────────────────────────────────
  // 2ª ABA: Categorias (Insumos da Planilha)
  // ─────────────────────────────────────────────────────────────────────────────
  const wsCategorias = wb.addWorksheet('Categorias', {
    views: [{ state: 'frozen', ySplit: 1, showGridLines: true }],
  });

  wsCategorias.columns = [
    { header: '#', key: 'index', width: 8 },
    { header: 'Classe', key: 'class', width: 10 },
    { header: 'Insumo', key: 'description', width: 45 },
    { header: 'Categoria / Tipo', key: 'category', width: 22 },
    { header: 'Unidade', key: 'unit', width: 10 },
    { header: 'Qtd. Total', key: 'quantity', width: 14 },
    { header: 'Preço Médio (R$)', key: 'unit_rate', width: 18 },
    { header: 'Valor Total (R$)', key: 'total_cost', width: 20 },
    { header: '% Individual', key: 'percentage', width: 14 },
    { header: '% Acumulado', key: 'cumulative_percentage', width: 14 },
  ];

  const catHeader = wsCategorias.getRow(1);
  catHeader.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  catHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.ink}` } };
  catHeader.height = 24;
  catHeader.alignment = { vertical: 'middle', horizontal: 'center' };

  let lastResClass = 'A';
  for (const item of options.resourcesResult.items) {
    // Insere linha divisória de corte se a classe mudar
    if (item.abc_class !== lastResClass) {
      const cutLabel = lastResClass === 'A'
        ? `━━ Limite Classe A (${options.resourcesResult.cutoff_a}%) ━━`
        : `━━ Limite Classe B (${options.resourcesResult.cutoff_b}%) ━━`;
      const cutRow = wsCategorias.addRow({
        index: '',
        class: '',
        description: cutLabel,
      });
      cutRow.font = { bold: true, italic: true, color: { argb: `FF${TOKENS.action}` } };
      cutRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.canvas}` } };
      wsCategorias.mergeCells(cutRow.number, 3, cutRow.number, 10);
      lastResClass = item.abc_class;
    }

    const row = wsCategorias.addRow({
      index: item.index,
      class: item.abc_class,
      description: item.description,
      category: getCategoriaLabel(item.category),
      unit: item.unit,
      quantity: item.quantity,
      unit_rate: item.unit_rate,
      total_cost: item.total_cost,
      percentage: item.percentage / 100,
      cumulative_percentage: item.cumulative_percentage / 100,
    });

    row.getCell(1).alignment = { horizontal: 'center' };
    row.getCell(2).alignment = { horizontal: 'center' };
    row.getCell(5).alignment = { horizontal: 'center' };
    row.getCell(6).numFmt = '#,##0.00';
    row.getCell(7).numFmt = 'R$ #,##0.00';
    row.getCell(8).numFmt = 'R$ #,##0.00';
    row.getCell(9).numFmt = '0.00%';
    row.getCell(10).numFmt = '0.00%';

    // Cor por classe
    const colorBg = item.abc_class === 'A' ? TOKENS.classA_bg : item.abc_class === 'B' ? TOKENS.classB_bg : TOKENS.classC_bg;
    const colorInk = item.abc_class === 'A' ? TOKENS.classA_ink : item.abc_class === 'B' ? TOKENS.classB_ink : TOKENS.classC_ink;
    row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${colorBg}` } };
    row.getCell(2).font = { bold: true, color: { argb: `FF${colorInk}` } };
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // 3ª ABA: Serviços (Serviços e Etapas da Planilha)
  // ─────────────────────────────────────────────────────────────────────────────
  const wsServicos = wb.addWorksheet('Serviços', {
    views: [{ state: 'frozen', ySplit: 1, showGridLines: true }],
  });

  wsServicos.columns = [
    { header: '#', key: 'index', width: 8 },
    { header: 'Classe', key: 'class', width: 10 },
    { header: 'Item / Código', key: 'code', width: 14 },
    { header: 'Descrição do Serviço', key: 'description', width: 45 },
    { header: 'Unidade', key: 'unit', width: 10 },
    { header: 'Quantidade', key: 'quantity', width: 14 },
    { header: 'Preço Unitário (R$)', key: 'unit_rate', width: 18 },
    { header: 'Valor Total (R$)', key: 'total_cost', width: 20 },
    { header: '% Individual', key: 'percentage', width: 14 },
    { header: '% Acumulado', key: 'cumulative_percentage', width: 14 },
  ];

  const servHeader = wsServicos.getRow(1);
  servHeader.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  servHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.ink}` } };
  servHeader.height = 24;
  servHeader.alignment = { vertical: 'middle', horizontal: 'center' };

  let lastServClass = 'A';
  for (const item of options.servicesResult.items) {
    // Insere linha divisória de corte se a classe mudar
    if (item.abc_class !== lastServClass) {
      const cutLabel = lastServClass === 'A'
        ? `━━ Limite Classe A (${options.servicesResult.cutoff_a}%) ━━`
        : `━━ Limite Classe B (${options.servicesResult.cutoff_b}%) ━━`;
      const cutRow = wsServicos.addRow({
        index: '',
        class: '',
        description: cutLabel,
      });
      cutRow.font = { bold: true, italic: true, color: { argb: `FF${TOKENS.action}` } };
      cutRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${TOKENS.canvas}` } };
      wsServicos.mergeCells(cutRow.number, 4, cutRow.number, 10);
      lastServClass = item.abc_class;
    }

    const row = wsServicos.addRow({
      index: item.index,
      class: item.abc_class,
      code: item.code,
      description: item.description,
      unit: item.unit,
      quantity: item.quantity,
      unit_rate: item.unit_rate,
      total_cost: item.total_cost,
      percentage: item.percentage / 100,
      cumulative_percentage: item.cumulative_percentage / 100,
    });

    row.getCell(1).alignment = { horizontal: 'center' };
    row.getCell(2).alignment = { horizontal: 'center' };
    row.getCell(3).alignment = { horizontal: 'center' };
    row.getCell(5).alignment = { horizontal: 'center' };
    row.getCell(6).numFmt = '#,##0.00';
    row.getCell(7).numFmt = 'R$ #,##0.00';
    row.getCell(8).numFmt = 'R$ #,##0.00';
    row.getCell(9).numFmt = '0.00%';
    row.getCell(10).numFmt = '0.00%';

    // Cor por classe
    const colorBg = item.abc_class === 'A' ? TOKENS.classA_bg : item.abc_class === 'B' ? TOKENS.classB_bg : TOKENS.classC_bg;
    const colorInk = item.abc_class === 'A' ? TOKENS.classA_ink : item.abc_class === 'B' ? TOKENS.classB_ink : TOKENS.classC_ink;
    row.getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${colorBg}` } };
    row.getCell(2).font = { bold: true, color: { argb: `FF${colorInk}` } };
  }

  // Gera buffer e dispara o download
  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const cleanName = (options.projectName || 'Curva_ABC').replace(/[^a-zA-Z0-9_\-]/g, '_');
  downloadBlob(blob, `Curva_ABC_${cleanName}.xlsx`);
}

/**
 * Gera e baixa o relatório em PDF com as 3 visões (Resumo, Serviços e Insumos)
 * formatado conforme o padrão de engenharia brasileira.
 */
export async function exportCurvaAbcToPdf(options: ExportCurvaAbcOptions): Promise<void> {
  const { default: JsPdfCtor } = await import('jspdf');
  const pdf: JsPdfType = new JsPdfCtor({ orientation: 'landscape', unit: 'mm', format: 'a4' });

  const pageWidth = 297;
  const pageHeight = 210;
  const margin = 12;
  const contentWidth = pageWidth - margin * 2;

  let y = margin;

  const drawHeader = (sectionTitle: string) => {
    // Top banner
    pdf.setFillColor(22, 57, 83); // #163953
    pdf.rect(margin, y, contentWidth, 16, 'F');

    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(14);
    pdf.setTextColor(255, 255, 255);
    pdf.text('EVOLUX OBRAS · CURVA ABC E ANÁLISE DE PARETO', margin + 6, y + 10);

    pdf.setFontSize(10);
    pdf.setFont('helvetica', 'normal');
    pdf.text(formatDatePtBr(options.date), pageWidth - margin - 30, y + 10);

    y += 20;

    // Subtítulo do projeto
    pdf.setTextColor(22, 57, 83);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(12);
    pdf.text(`Projeto: ${options.projectName || 'Edifício Residencial Jardins - São Paulo'}`, margin, y);
    y += 5;

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(10);
    pdf.setTextColor(70, 92, 105);
    pdf.text(`Orçamento: ${options.boqName || 'Orçamento Sintético - Padrão SINAPI'} | Total: ${formatMoneyPtBr(options.servicesResult.grand_total)}`, margin, y);
    y += 7;

    // Seção atual
    pdf.setFillColor(21, 109, 97); // #156D61
    pdf.rect(margin, y, contentWidth, 6, 'F');
    pdf.setTextColor(255, 255, 255);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(9);
    pdf.text(sectionTitle.toUpperCase(), margin + 4, y + 4.5);
    y += 9;
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // PÁGINA 1: VISÃO 1 (RESUMO) + INÍCIO DA VISÃO 2 (SERVIÇOS)
  // ─────────────────────────────────────────────────────────────────────────────
  drawHeader('1. Resumo Executivo das Classes A, B e C');

  // Tabela Resumo
  const rCols = [
    { title: 'Classe', w: 30 },
    { title: 'Faixa %', w: 40 },
    { title: 'Qtd. Serviços', w: 30 },
    { title: 'Total Serviços (R$)', w: 45 },
    { title: '% Serviços', w: 25 },
    { title: 'Qtd. Insumos', w: 30 },
    { title: 'Total Insumos (R$)', w: 45 },
    { title: '% Insumos', w: 28 },
  ];

  // Header da tabela resumo
  pdf.setFillColor(246, 246, 239);
  pdf.rect(margin, y, contentWidth, 6, 'F');
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(8);
  pdf.setTextColor(22, 57, 83);

  let rx = margin;
  for (const c of rCols) {
    pdf.text(c.title, rx + 2, y + 4.2);
    rx += c.w;
  }
  y += 7;

  const sSum = options.servicesResult.summary;
  const rSum = options.resourcesResult.summary;

  const resRows = [
    { label: 'Classe A', faixa: `0% a ${options.servicesResult.cutoff_a}%`, s: sSum.A, r: rSum.A, rColor: [226, 242, 236] },
    { label: 'Classe B', faixa: `${options.servicesResult.cutoff_a}% a ${options.servicesResult.cutoff_b}%`, s: sSum.B, r: rSum.B, rColor: [220, 238, 233] },
    { label: 'Classe C', faixa: `${options.servicesResult.cutoff_b}% a 100%`, s: sSum.C, r: rSum.C, rColor: [246, 246, 239] },
  ];

  pdf.setFont('helvetica', 'normal');
  for (const row of resRows) {
    pdf.setFillColor(row.rColor[0]!, row.rColor[1]!, row.rColor[2]!);
    pdf.rect(margin, y, contentWidth, 5.5, 'F');

    let cx = margin;
    pdf.setFont('helvetica', 'bold');
    pdf.text(row.label, cx + 2, y + 4); cx += rCols[0]!.w;
    pdf.setFont('helvetica', 'normal');
    pdf.text(row.faixa, cx + 2, y + 4); cx += rCols[1]!.w;
    pdf.text(String(row.s.count), cx + 2, y + 4); cx += rCols[2]!.w;
    pdf.text(formatMoneyPtBr(row.s.total), cx + 2, y + 4); cx += rCols[3]!.w;
    pdf.text(formatPercentPtBr(row.s.percentage), cx + 2, y + 4); cx += rCols[4]!.w;
    pdf.text(String(row.r.count), cx + 2, y + 4); cx += rCols[5]!.w;
    pdf.text(formatMoneyPtBr(row.r.total), cx + 2, y + 4); cx += rCols[6]!.w;
    pdf.text(formatPercentPtBr(row.r.percentage), cx + 2, y + 4);

    y += 6;
  }

  // Total resumo
  pdf.setFillColor(206, 216, 213);
  pdf.rect(margin, y, contentWidth, 5.5, 'F');
  pdf.setFont('helvetica', 'bold');
  let tx = margin;
  pdf.text('Total Geral', tx + 2, y + 4); tx += rCols[0]!.w;
  pdf.text('100,00%', tx + 2, y + 4); tx += rCols[1]!.w;
  pdf.text(String(options.servicesResult.total_count), tx + 2, y + 4); tx += rCols[2]!.w;
  pdf.text(formatMoneyPtBr(options.servicesResult.grand_total), tx + 2, y + 4); tx += rCols[3]!.w;
  pdf.text('100,00%', tx + 2, y + 4); tx += rCols[4]!.w;
  pdf.text(String(options.resourcesResult.total_count), tx + 2, y + 4); tx += rCols[5]!.w;
  pdf.text(formatMoneyPtBr(options.resourcesResult.grand_total), tx + 2, y + 4); tx += rCols[6]!.w;
  pdf.text('100,00%', tx + 2, y + 4);
  y += 12;

  // ─────────────────────────────────────────────────────────────────────────────
  // VISÃO 2: SERVIÇOS E ETAPAS
  // ─────────────────────────────────────────────────────────────────────────────
  pdf.setFillColor(21, 109, 97);
  pdf.rect(margin, y, contentWidth, 6, 'F');
  pdf.setTextColor(255, 255, 255);
  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(9);
  pdf.text('2. CURVA ABC POR SERVIÇOS E ETAPAS DA PLANILHA', margin + 4, y + 4.5);
  y += 8;

  const servCols = [
    { title: '#', w: 10 },
    { title: 'Cls', w: 12 },
    { title: 'Item', w: 18 },
    { title: 'Descrição do Serviço', w: 105 },
    { title: 'Un.', w: 12 },
    { title: 'Qtd.', w: 20 },
    { title: 'Preço Un. (R$)', w: 28 },
    { title: 'Total (R$)', w: 32 },
    { title: '% Indiv.', w: 18 },
    { title: '% Acum.', w: 18 },
  ];

  const drawServHeader = () => {
    pdf.setFillColor(246, 246, 239);
    pdf.rect(margin, y, contentWidth, 5.5, 'F');
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(8);
    pdf.setTextColor(22, 57, 83);
    let sx = margin;
    for (const c of servCols) {
      pdf.text(c.title, sx + 1.5, y + 3.8);
      sx += c.w;
    }
    y += 6;
  };

  drawServHeader();

  let servClassTrack = 'A';
  for (const item of options.servicesResult.items) {
    if (y > pageHeight - 15) {
      pdf.addPage('a4', 'landscape');
      y = margin;
      drawHeader('2. Curva ABC por Serviços e Etapas (continuação)');
      drawServHeader();
    }

    // Linha de corte
    if (item.abc_class !== servClassTrack) {
      const cutLabel = servClassTrack === 'A'
        ? `━━━ LIMITE CLASSE A (${options.servicesResult.cutoff_a}%) ━━━`
        : `━━━ LIMITE CLASSE B (${options.servicesResult.cutoff_b}%) ━━━`;
      pdf.setFillColor(246, 246, 239);
      pdf.rect(margin, y, contentWidth, 5, 'F');
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(8);
      pdf.setTextColor(21, 109, 97);
      pdf.text(cutLabel, margin + 40, y + 3.5);
      y += 5.5;
      servClassTrack = item.abc_class;
    }

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7.5);
    pdf.setTextColor(30, 41, 59);

    let sx = margin;
    pdf.text(String(item.index), sx + 1.5, y + 3.5); sx += servCols[0]!.w;
    pdf.setFont('helvetica', 'bold');
    if (item.abc_class === 'A') pdf.setTextColor(18, 89, 77);
    else if (item.abc_class === 'B') pdf.setTextColor(22, 57, 83);
    else pdf.setTextColor(70, 92, 105);
    pdf.text(item.abc_class, sx + 3, y + 3.5); sx += servCols[1]!.w;
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(30, 41, 59);
    pdf.text(item.code, sx + 1.5, y + 3.5); sx += servCols[2]!.w;
    const desc = item.description.length > 60 ? item.description.slice(0, 58) + '...' : item.description;
    pdf.text(desc, sx + 1.5, y + 3.5); sx += servCols[3]!.w;
    pdf.text(item.unit, sx + 1.5, y + 3.5); sx += servCols[4]!.w;
    pdf.text(item.quantity.toLocaleString('pt-BR', { maximumFractionDigits: 2 }), sx + 1.5, y + 3.5); sx += servCols[5]!.w;
    pdf.text(formatMoneyPtBr(item.unit_rate), sx + 1.5, y + 3.5); sx += servCols[6]!.w;
    pdf.text(formatMoneyPtBr(item.total_cost), sx + 1.5, y + 3.5); sx += servCols[7]!.w;
    pdf.text(formatPercentPtBr(item.percentage), sx + 1.5, y + 3.5); sx += servCols[8]!.w;
    pdf.text(formatPercentPtBr(item.cumulative_percentage), sx + 1.5, y + 3.5);

    y += 4.5;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // VISÃO 3: INSUMOS E CATEGORIAS (EM NOVA PÁGINA)
  // ─────────────────────────────────────────────────────────────────────────────
  pdf.addPage('a4', 'landscape');
  y = margin;
  drawHeader('3. Curva ABC por Insumos e Categorias');

  const resCols = [
    { title: '#', w: 10 },
    { title: 'Cls', w: 12 },
    { title: 'Insumo', w: 110 },
    { title: 'Categoria / Tipo', w: 32 },
    { title: 'Un.', w: 12 },
    { title: 'Qtd.', w: 20 },
    { title: 'Preço Médio (R$)', w: 25 },
    { title: 'Total (R$)', w: 30 },
    { title: '% Indiv.', w: 18 },
    { title: '% Acum.', w: 18 },
  ];

  const drawResHeader = () => {
    pdf.setFillColor(246, 246, 239);
    pdf.rect(margin, y, contentWidth, 5.5, 'F');
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(8);
    pdf.setTextColor(22, 57, 83);
    let rx = margin;
    for (const c of resCols) {
      pdf.text(c.title, rx + 1.5, y + 3.8);
      rx += c.w;
    }
    y += 6;
  };

  drawResHeader();

  let resClassTrack = 'A';
  for (const item of options.resourcesResult.items) {
    if (y > pageHeight - 15) {
      pdf.addPage('a4', 'landscape');
      y = margin;
      drawHeader('3. Curva ABC por Insumos e Categorias (continuação)');
      drawResHeader();
    }

    // Linha de corte
    if (item.abc_class !== resClassTrack) {
      const cutLabel = resClassTrack === 'A'
        ? `━━━ LIMITE CLASSE A (${options.resourcesResult.cutoff_a}%) ━━━`
        : `━━━ LIMITE CLASSE B (${options.resourcesResult.cutoff_b}%) ━━━`;
      pdf.setFillColor(246, 246, 239);
      pdf.rect(margin, y, contentWidth, 5, 'F');
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(8);
      pdf.setTextColor(21, 109, 97);
      pdf.text(cutLabel, margin + 40, y + 3.5);
      y += 5.5;
      resClassTrack = item.abc_class;
    }

    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7.5);
    pdf.setTextColor(30, 41, 59);

    let rx = margin;
    pdf.text(String(item.index), rx + 1.5, y + 3.5); rx += resCols[0]!.w;
    pdf.setFont('helvetica', 'bold');
    if (item.abc_class === 'A') pdf.setTextColor(18, 89, 77);
    else if (item.abc_class === 'B') pdf.setTextColor(22, 57, 83);
    else pdf.setTextColor(70, 92, 105);
    pdf.text(item.abc_class, rx + 3, y + 3.5); rx += resCols[1]!.w;
    pdf.setFont('helvetica', 'normal');
    pdf.setTextColor(30, 41, 59);
    const desc = item.description.length > 60 ? item.description.slice(0, 58) + '...' : item.description;
    pdf.text(desc, rx + 1.5, y + 3.5); rx += resCols[2]!.w;
    pdf.text(getCategoriaLabel(item.category), rx + 1.5, y + 3.5); rx += resCols[3]!.w;
    pdf.text(item.unit, rx + 1.5, y + 3.5); rx += resCols[4]!.w;
    pdf.text(item.quantity.toLocaleString('pt-BR', { maximumFractionDigits: 2 }), rx + 1.5, y + 3.5); rx += resCols[5]!.w;
    pdf.text(formatMoneyPtBr(item.unit_rate), rx + 1.5, y + 3.5); rx += resCols[6]!.w;
    pdf.text(formatMoneyPtBr(item.total_cost), rx + 1.5, y + 3.5); rx += resCols[7]!.w;
    pdf.text(formatPercentPtBr(item.percentage), rx + 1.5, y + 3.5); rx += resCols[8]!.w;
    pdf.text(formatPercentPtBr(item.cumulative_percentage), rx + 1.5, y + 3.5);

    y += 4.5;
  }

  // Numeração de páginas
  const pageCount = (pdf.internal as { getNumberOfPages?: () => number }).getNumberOfPages
    ? (pdf.internal as { getNumberOfPages: () => number }).getNumberOfPages()
    : 1;

  for (let i = 1; i <= pageCount; i++) {
    pdf.setPage(i);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(100, 116, 139);
    pdf.text(
      `Evolux Obras · Página ${i} de ${pageCount}`,
      pageWidth - margin - 35,
      pageHeight - 6,
    );
  }

  const cleanName = (options.projectName || 'Curva_ABC').replace(/[^a-zA-Z0-9_\-]/g, '_');
  pdf.save(`Curva_ABC_${cleanName}.pdf`);
}
