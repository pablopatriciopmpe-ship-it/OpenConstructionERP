// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { describe, it, expect } from 'vitest';
import { calculateCurvaAbc, getCategoriaLabel } from './curvaAbcCalculations';

describe('calculateCurvaAbc', () => {
  it('retorna resultado vazio seguro quando recebe lista vazia', () => {
    const res = calculateCurvaAbc([]);
    expect(res.grand_total).toBe(0);
    expect(res.total_count).toBe(0);
    expect(res.items).toEqual([]);
    expect(res.summary.A.count).toBe(0);
  });

  it('ignora itens com custo zero ou negativo', () => {
    const res = calculateCurvaAbc([
      { id: '1', description: 'Item 1', total_cost: 0 },
      { id: '2', description: 'Item 2', total_cost: -50 },
      { id: '3', description: 'Item 3', total_cost: 100 },
    ]);
    expect(res.total_count).toBe(1);
    expect(res.grand_total).toBe(100);
    expect(res.items[0]!.id).toBe('3');
    expect(res.items[0]!.abc_class).toBe('A');
  });

  it('classifica corretamente itens conforme limites padrão 80/95', () => {
    const inputs = [
      { id: '1', description: 'Concreto Usinado', total_cost: 50000 }, // 50% -> A
      { id: '2', description: 'Aço CA-50', total_cost: 25000 },        // 25% (acum 75%) -> A
      { id: '3', description: 'Alvenaria', total_cost: 10000 },        // 10% (acum 85%) -> A (cruza 80%)
      { id: '4', description: 'Argamassa', total_cost: 10000 },        // 10% (acum 95%) -> B
      { id: '5', description: 'Pintura', total_cost: 5000 },           // 5% (acum 100%) -> C
    ];

    const res = calculateCurvaAbc(inputs, 80, 95);

    expect(res.grand_total).toBe(100000);
    expect(res.items).toHaveLength(5);

    // Itens 1, 2, 3 na Classe A
    expect(res.items[0]!.abc_class).toBe('A');
    expect(res.items[1]!.abc_class).toBe('A');
    expect(res.items[2]!.abc_class).toBe('A');

    // Item 4 na Classe B
    expect(res.items[3]!.abc_class).toBe('B');

    // Item 5 na Classe C
    expect(res.items[4]!.abc_class).toBe('C');

    // Resumo
    expect(res.summary.A.count).toBe(3);
    expect(res.summary.A.total).toBe(85000);
    expect(res.summary.A.percentage).toBe(85);

    expect(res.summary.B.count).toBe(1);
    expect(res.summary.B.total).toBe(10000);
    expect(res.summary.B.percentage).toBe(10);

    expect(res.summary.C.count).toBe(1);
    expect(res.summary.C.total).toBe(5000);
    expect(res.summary.C.percentage).toBe(5);

    expect(res.items[4]!.cumulative_percentage).toBe(100);
  });

  it('recalcula dinamicamente ao alterar os limites de corte', () => {
    const inputs = [
      { id: '1', description: 'Item 1', total_cost: 60 },
      { id: '2', description: 'Item 2', total_cost: 20 },
      { id: '3', description: 'Item 3', total_cost: 15 },
      { id: '4', description: 'Item 4', total_cost: 5 },
    ];

    // Limites restritos 50/70
    const res = calculateCurvaAbc(inputs, 50, 70);
    expect(res.items[0]!.abc_class).toBe('A'); // 60%
    expect(res.items[1]!.abc_class).toBe('B'); // 60% a 80%
    expect(res.items[2]!.abc_class).toBe('C'); // 80% a 95%
    expect(res.items[3]!.abc_class).toBe('C');
  });

  it('traduz categorias para português', () => {
    expect(getCategoriaLabel('material')).toBe('Material');
    expect(getCategoriaLabel('labor')).toBe('Mão de Obra');
    expect(getCategoriaLabel('machinery')).toBe('Equipamento / Máquina');
    expect(getCategoriaLabel('subcontractor')).toBe('Empreiteiro / Terceirizado');
    expect(getCategoriaLabel('other')).toBe('Outros');
  });
});
