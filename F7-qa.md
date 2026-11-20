# F7 — Integração e regressão

## Integração

Worktree: `/tmp/oce-release` (clone compartilhado permaneceu em
`feat/poda-modulos`). Nenhuma alteração foi feita em `main`.

Branches integradas:

| Origem | Commit validado | Resultado |
|---|---|---|
| `feat/poda-modulos` | `d3cc84a3` | base da release |
| `feat/saas-core` | `7cd44fcc` | integrado com os 3 ajustes da revisão F5 |
| `feat/brasil-dados` | `fd836753` | integrado |
| `feat/brasil-ui` | `388b1ad4` | integrado |

Commits de merge da release:

- `2c9cc16f` — SaaS core inicial;
- `42af8584` — dados Brasil;
- `205db72e` — UI Brasil;
- merge posterior de `7cd44fcc` — correções revisadas de SaaS.

Conflitos resolvidos (2 arquivos, ambos no merge da UI):

- `.github/workflows/preview-build.yml`: preservado o workflow da UI com
  medição `/usr/bin/time -v`, publicação do `dist` e passo de resolução do
  backend; mantidos os parâmetros necessários ao Actions.
- `deploy/preview-backend-url.txt`: escolhido o endpoint fixo
  `https://erp-teste.evolux-erp.workers.dev`, descartando o túnel temporário.

## Regressão backend

Comando principal:

```text
cd backend && PYTHONPATH=. /tmp/oce-venv/bin/python -m pytest \
  tests/unit/test_product_manifest.py tests/integration/test_saas_core.py \
  tests/saas_billing tests/unit/test_brasil_dados.py \
  tests/unit/test_boq*.py tests/unit/test_cost*.py tests/unit/test_schedule*.py -q
```

Resultado no release antes do último ajuste SaaS: **3.542 passed, 7 skipped,
4 warnings**, em 428,09 s.

Após integrar `7cd44fcc`, os testes afetados e os dados Brasil foram repetidos:
**41 passed, 2 warnings**, em 110,69 s. Os warnings são deprecações do
Starlette/TestClient e não falhas funcionais. O encerramento do PostgreSQL
embutido também emitiu logging do fixture após o stream de saída fechar, sem
alterar o resultado dos testes.

## Falhas históricas do baseline

O baseline `ceed6b11` já registra **1 falha e 24 erros** em
`test_tenant_isolation.py`. A causa é a poda F3: o teste importa/espera módulos
removidos do produto, não uma regressão introduzida pela integração. A decisão
é **adaptar o teste à poda** (ou separar seus casos por manifest), mantendo
isolados os testes que exercitam tabelas/rotas ainda mantidas. Não foi
classificado como novo buraco de isolamento: os testes F5 de membership,
claim forjada, projeto/equipe e RLS passaram; `7cd44fcc` também restringe
membership de equipe ao tenant.

## Publicação

Branches publicadas: `release/v0.1` em `17f3ad97` e `preview/release` no mesmo
HEAD. O push foi aceito pelo fork, mas o GitHub Actions exibiu: “Workflows are
not currently being run on this fork due to the scale of GitHub Actions usage”.
Não existe run ID nem resultado de build para `preview/release`; a compilação
fica bloqueada no provedor, não no código. Desbloqueio: um mantenedor deve
reabilitar GitHub Actions/uso de Actions neste fork e então reenviar o push ou
executar manualmente `Preview build (frontend)` em `preview/release`.
