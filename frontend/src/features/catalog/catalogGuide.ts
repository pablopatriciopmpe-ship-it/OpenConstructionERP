// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
//
// catalogGuide - "Como funciona" para o módulo Catálogo de Insumos (SINAPI).
// Consumido por <ModuleGuideButton content={catalogGuide} /> em CatalogPage.

import type { ModuleGuideContent } from '@/shared/ui';

export const catalogGuide: ModuleGuideContent = {
  titleKey: 'guide.catalog.title',
  titleDefault: 'Catálogo de Insumos',
  introKey: 'guide.catalog.intro',
  introDefault:
    'O catálogo é a sua biblioteca de insumos oficiais da construção civil brasileira: materiais, mão de obra, equipamentos e operadores em reais (R$, padrão SINAPI/CAIXA). Mantenha os preços de referência atualizados aqui e alimente composições, custos unitários e orçamentos em todos os seus projetos.',
  sections: [
    {
      icon: 'Database',
      titleKey: 'guide.catalog.concept.title',
      titleDefault: 'O que compõe o catálogo',
      bodyKey: 'guide.catalog.concept.body',
      bodyDefault:
        'Cada insumo traz seu código oficial SINAPI, unidade e faixa de preço (menor e maior preço entre as 27 UFs do Brasil e o preço de referência). Os insumos estão divididos em quatro tipos: materiais, equipamentos, mão de obra e operadores. O indicador de uso mostra em quantas composições o insumo participa.',
    },
    {
      icon: 'Rocket',
      titleKey: 'guide.catalog.import.title',
      titleDefault: 'Base oficial do Brasil (SINAPI)',
      bodyKey: 'guide.catalog.import.body',
      bodyDefault:
        'Acesse a base oficial SINAPI (CAIXA) com milhares de insumos precificados em reais (R$). Cada importação atualiza os custos oficiais por estado e regime tributário, mantendo o histórico de composições e o Meu Catálogo preservados.',
      spotlightSelector: '[data-guide="catalog-import"]',
    },
    {
      icon: 'ListChecks',
      titleKey: 'guide.catalog.browse.title',
      titleDefault: 'Navegar por tipo e categoria',
      bodyKey: 'guide.catalog.browse.body',
      bodyDefault:
        'Use as abas para filtrar por materiais, equipamentos, mão de obra ou operadores, e visualize categorias como Concreto, Aço, Elétrica, Hidráulica e Alvenaria. Alterne entre a base Brasil (SINAPI) e os itens do seu próprio catálogo.',
      spotlightSelector: '[data-guide="catalog-type-filters"]',
    },
    {
      icon: 'Sparkles',
      titleKey: 'guide.catalog.search.title',
      titleDefault: 'Pesquisa e filtros avançados',
      bodyKey: 'guide.catalog.search.body',
      bodyDefault:
        'Busque rapidamente por código numérico SINAPI ou descrição do insumo. Filtre por categoria técnica ou unidade e clique em qualquer linha para consultar a ficha de especificações, origem do preço e composições que usam o insumo.',
      spotlightSelector: '[data-guide="catalog-search"]',
    },
    {
      icon: 'PencilLine',
      titleKey: 'guide.catalog.add.title',
      titleDefault: 'Cadastre insumos próprios',
      bodyKey: 'guide.catalog.add.body',
      bodyDefault:
        'Precisa de um item específico que não consta no SINAPI? Adicione insumos personalizados informando código, descrição, unidade e preço em reais. Eles ficam salvos no Meu Catálogo e podem ser reajustados por índice (como INCC-M) ou fator manual.',
      spotlightSelector: '[data-guide="catalog-add-resource"]',
    },
    {
      icon: 'Layers',
      titleKey: 'guide.catalog.apply.title',
      titleDefault: 'Usar em composições e orçamentos',
      bodyKey: 'guide.catalog.apply.body',
      bodyDefault:
        'Selecione insumos para copiar seus valores ou clique em Construir Composição para criar uma composição de custo unitário reutilizável que se conecta automaticamente às planilhas orçamentárias.',
      spotlightSelector: '[data-guide="catalog-table"]',
    },
  ],
  ctaKey: 'guide.catalog.cta',
  ctaDefault: 'Explorar insumos SINAPI',
};
