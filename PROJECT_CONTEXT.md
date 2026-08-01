Lotofácil Prediction — Contexto do Projeto
Resumo

Projeto: plataforma em Django para armazenar resultados históricos da Lotofácil, analisar estatísticas e expor previsões/insights.
Objetivo: ingestão reprodutível de dados, análise estatística auditável e UIs/APIs para visualização das métricas e previsões geradas por algoritmos simples e verificáveis.
Stack principal

Linguagem: Python 3.x
Framework web: Django (usar DRF quando precisar de API)
Banco: PostgreSQL (produção); SQLite para dev/testes
Bibliotecas analíticas: pandas, numpy, scikit-learn (apenas quando necessário)
Testes/qualidade: pytest, factory_boy, black, isort, ruff
Entidades e dados

Entidade chave: Sorteio (concurso, data, dezenas, observações, idempotência).
Regras de ingestão: parser robusto para CSV/XLS/JSON com validação, logs, idempotência e testes.
Modelagem: histórico imutável preferível; soft-delete/desativação quando necessário; versionamento mínimo de metadados se alterar formatos importados.
Princípios de implementação (essenciais)

Minimalismo seguro: escrever o mínimo de código necessário; preferir soluções padrão do Django e bibliotecas consolidadas.
Não inventar hipóteses: se faltar dado ou formato, pedir exemplos; não assumir formatos, campos ou regras de negócio.
Separação de responsabilidades:
Regras de domínio e queries reutilizáveis: models.py / managers.py.
Lógica de orquestração e integrações: services/ (ex.: services).
Apresentação e controle: views.py / serializers.py / templates.
Tipagem: usar type hints em interfaces públicas e funções complexas.
Segurança: usar ORM (evitar SQL raw), validação de entrada, templates escapados, CSRF habilitado.
Performance: evitar N+1 com select_related/prefetch_related, paginar conjuntos grandes e criar índices DB para filtros frequentes.
Testes: cada feature com testes unitários e testes básicos de integração; dados de teste determinísticos.
Padrões de projeto recomendados

Managers para queries complexas e reutilizáveis.
Services para lógica que não pertence a models/views.
Tasks (Celery/async) para processamento longo (ingestão grande, análise batch).
Parsers idempotentes com validação explícita e relatórios de erros.
Migrations exigidas para todo change de modelo; documentar impacto no banco.
Fluxo recomendado para implementar uma feature

Definir escopo e critérios de aceitação (entrada/saída/UX).
Escrever testes que especifiquem comportamento esperado.
Alterar/adição de modelos se necessário e gerar migrations.
Implementar lógica em models/managers/services.
Expor via views/serializers/templates ou endpoint API.
Revisar queries e aplicar otimizações (select_related, índices).
Atualizar docs/README com comandos necessários.
Garantir CI: testes e linters passam antes do merge.
Checklist mínimo de PR

Descrição clara do que muda e por quê.
Testes adicionados/atualizados cobrindo comportamento.
Migrations incluídas quando houve mudanças de modelo.
Impacto em performance/segurança documentado.
Linters/formatadores OK e CI verde.
Como formatar pedidos de novas features (para humanos/IA)

Forneça:
Objetivo curto.
Exemplos concretos de entrada (ex.: linhas de CSV ou JSON).
Saída esperada (ex.: esquema JSON, mock de tela).
Indicação se afeta modelos (sim/não).
Critérios de aceitação automatizáveis (ex.: testes esperados).
Se não souber algo, indique explicitamente "não sei" e forneça 1–2 opções preferidas.
Boas práticas operacionais

PRs pequenos e iterativos.
Documentar suposições; quando suposições existirão, registre e solicite validação.
Preferir bibliotecas consolidadas; evitar soluções custom desnecessárias.
Automatizar: testes, lint e formatação em CI.
Monitoramento mínimo em produção para erros de ingestão e jobs agendados.
Observações importantes

Nunca inventar formatos ou regras de negócio não fornecidas.
Priorizar auditabilidade e reprodutibilidade das análises.
Manter código legível, testável e o mais simples possível.
Notas rápidas para desenvolvedores/IA

Local provável para parsers: excel_parser.py
Lógica de API: views.py e urls.py
Tests existentes: analyzer/tests/\*.py — siga o estilo e fixtures já presentes.
