# Procede — Assistente de Procedimentos de Execução

Piloto interno da Persa (incorporadora). O time de campo tira dúvidas sobre os procedimentos de
execução da obra e recebe respostas baseadas **exclusivamente** nos documentos cadastrados da
empresa, sempre com citação da fonte. Quando a resposta não está no material, o sistema **não
inventa** — ele indica o responsável técnico. Todo histórico de perguntas vira insumo para melhorar
os próprios procedimentos.

## Arquitetura

- **backend/** — API FastAPI (Python). RAG com Postgres + `pgvector`, embeddings Voyage-3, respostas
  via Claude (Anthropic). Transcrição de áudio via Whisper.
- **web/** — App Next.js (TypeScript) com duas áreas:
  - `/chat` — chat do time de campo (texto, áudio ou foto).
  - `/admin` — painel de qualidade/planejamento (login, upload de documentos, log de perguntas).

### Como o Procede fala

Assistente de conversa (sem menus): o time de campo pergunta em linguagem natural, por texto, áudio
ou foto. O tom é português de canteiro de obra — frases curtas, tratamento por "você", trata a pessoa
pelo primeiro nome, e não dá opinião própria: repassa o que o procedimento diz.

**Quando encontra a resposta**, sempre nesta ordem: resposta curta → trecho **literal** do documento
entre aspas → link que abre o PDF direto na página citada.

```
Valdir, a superfície deve ser mantida úmida por no mínimo 7 dias.

📄 POP de Concretagem, item 4.3:
“a cura deve garantir a superfície permanentemente úmida por período não inferior a 7 dias”

🔗 Abrir o procedimento (página 12):
https://…/documents/<id>/file?t=<token>#page=12
```

**Quando não encontra**, nunca inventa nem complementa com conhecimento geral:

```
Valdir, não encontrei essa informação nos procedimentos cadastrados.

⚠️ Não posso responder por conta própria. Fale com o responsável técnico: Eng. Marcos, (11) 98888-7777
```

O formato da mensagem é montado em Python (`format_answer` / `format_fallback` em
`app/services/rag.py`), não deixado a cargo do modelo — assim ele nunca varia. O modelo só devolve
dados estruturados (resposta, trecho literal, qual trecho usou).

O link carrega um token assinado com validade na própria URL, porque o WhatsApp não envia cabeçalho
de autenticação; ele é restrito a um documento de uma empresa.

### De onde vêm os documentos

O **índice de busca é sempre nosso** (é o que permite responder por significado, coisa que a busca por
palavra-chave do SharePoint não faz). Mas o **arquivo** não precisa ser: cada documento registra sua
origem em `source_type`.

- `upload` — enviado pelo painel. Guardamos a cópia e servimos o arquivo pelo nosso link assinado.
- `sharepoint` / `google_drive` — o arquivo continua no sistema do cliente, com as permissões e o
  versionamento que ele já usa. Guardamos só o índice, e o link da resposta aponta para `external_url`.

Os conectores em si ainda não existem (Fase 2/3), mas o modelo já está preparado: `external_id`,
`external_url`, `external_modified_at` e `last_synced_at` permitem detectar revisão na origem e
reindexar sozinho — que é o que resolve o risco de responder com um POP desatualizado. `file_path` é
opcional, porque documento de conector não tem cópia local.

O upload continua sendo o piso: garante que qualquer cliente entra no dia 1, inclusive quem não usa
SharePoint.

### Dois tipos de documento ("pasta mãe")

- `procedimento` — POP, FVS, memoriais. É quebrado em trechos, indexado e pesquisado via RAG.
  **Exigido em PDF**: é o formato que preserva a paginação, o que permite abrir o documento na página
  citada (e, adiante, destacar o trecho na imagem).
- `administrativo` — alvará, habite-se, ART, contratos. Indexado só por metadado (obra + tipo) e
  devolvido como arquivo inteiro quando o usuário pede ("me manda o alvará do empreendimento X").

## Rodando o backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # preencha as chaves (Anthropic, Voyage, DATABASE_URL, JWT_SECRET)

# aplique as migrations no Postgres/Supabase (na ordem), com uma conexão privilegiada:
psql "$ADMIN_DATABASE_URL_PSQL" -f migrations/0001_init.sql
psql "$ADMIN_DATABASE_URL_PSQL" -f migrations/0002_enable_rls.sql
psql "$ADMIN_DATABASE_URL_PSQL" -f migrations/0003_tenant_isolation.sql   # troque a senha do app_tenant

# onboarding: cria empresa, obra, admin (email+senha) e usuário de campo (telefone+PIN):
python -m scripts.seed --company "Persa" \
    --admin-email qualidade@persa.com --admin-password 'senha-forte' --field-pin 1234

uvicorn app.main:app --reload
```

> As URLs usam o driver async (`postgresql+asyncpg://...`). Para rodar migrations com `psql`
> use a URL padrão `postgresql://...`.

### Taxonomia documental e permissão por família

Cada empresa tem a própria taxonomia (`document_types`) — o "RQ 15" dela: código, nome, pasta,
chave de recuperação, meio (eletrônico/físico/ambos/sistema), retenção e descarte. Ela vive no
**banco**, não no prompt: assim cada cliente tem a sua, o modelo escolhe entre linhas que existem
em vez de recordar uma tabela, e "documento não mapeado" vira fato verificável. A taxonomia da
Persa (86 tipos) está em `data/taxonomia_persa_rq15.json`; `scripts/load_taxonomy.py` carrega a de
qualquer cliente e pode ser rodado de novo sem duplicar.

A retenção é **regra computável** (`retention_rule` + `retention_months`), não prosa — é o que
permitirá calcular alertas de vencimento e de descarte.

Todo documento pertence a uma das cinco **famílias** (qualidade/gestão, projetos/obra, suprimentos,
comercial/cliente, pessoas/segurança), e o acesso é concedido por família em `user_family_access`.
Isso não é conveniência: 31 dos 86 tipos carregam dado pessoal. Sem essa barreira, o mestre de obra
perguntando no chat poderia receber trecho de ficha de funcionário ou ASO — o assistente viraria
canal de vazamento (LGPD).

A restrição é imposta pelo banco, como o isolamento por empresa: `tenant_session` fixa
`app.current_families` na transação e as policies recusam qualquer família fora da lista. Lista
vazia não devolve nada (fail-closed) — quem nunca foi liberado não vê documento algum, em vez de ver
tudo. Um usuário de campo recém-cadastrado recebe apenas qualidade e obra; RH e cliente exigem
liberação explícita. Ler e arquivar são permissões separadas (`can_upload`).

### Isolamento entre empresas (multi-tenant)

O isolamento é garantido pelo **banco**, não só pelo código:

- O backend conecta com o papel **`app_tenant`** (sem `BYPASSRLS`) e fixa `app.current_company_id`
  por transação (`tenant_session` em `app/db.py`). O papel `postgres` do Supabase ignora RLS, por
  isso **nunca** deve ser usado pelo backend.
- Todas as tabelas de conteúdo têm **RLS com policy por `company_id`** (migration 0003). Sem contexto
  de empresa, as queries retornam zero linhas (fail-closed).
- A **identidade é confiável**: o `company_id` vem sempre do token JWT assinado (login de admin por
  email+senha; login de campo por telefone+PIN — no WhatsApp o número verificado pela Meta cumpre esse
  papel). Nenhum endpoint aceita `company_id` vindo do cliente.
- **Onboarding** (criar empresa nova) é operação privilegiada do operador, feita com `ADMIN_DATABASE_URL`
  (papel postgres) — não pelo backend.

### Variáveis de ambiente (backend)

| Var | Uso |
|-----|-----|
| `DATABASE_URL` | Conexão do backend — papel **app_tenant** (`postgresql+asyncpg://app_tenant:...`) |
| `ADMIN_DATABASE_URL` | Conexão privilegiada (postgres), só para onboarding/seed |
| `ANTHROPIC_API_KEY` | Geração da resposta e classificação de intenção (Claude) |
| `VOYAGE_API_KEY` | Embeddings de busca (voyage-3) |
| `OPENAI_API_KEY` | Opcional — transcrição de áudio (Whisper) |
| `JWT_SECRET` | Assinatura dos tokens (admin e campo) |
| `STORAGE_DIR` | Pasta local dos arquivos enviados (default `./storage`) |

## Rodando o web

```bash
cd web
npm install
cp .env.example .env.local   # ajuste NEXT_PUBLIC_API_BASE se necessário
npm run dev
```

## Testes

```bash
cd backend && source .venv/bin/activate
pytest        # testes unitários (chunking + fallback do RAG) rodam sem banco.
              # tests/test_isolation.py prova o RLS entre empresas quando você define
              # ADMIN_DATABASE_URL (postgres) e DATABASE_URL (app_tenant); pula sem eles.
```

O teste mais importante é `tests/test_rag_fallback.py`: garante que o assistente nunca responde com
conhecimento geral e cai no fallback (indicando o responsável técnico) quando o material não cobre a
pergunta.

## Fora do escopo deste MVP (roadmap)

- Canal WhatsApp (Meta Cloud API direto) — o fluxo de RAG já é agnóstico de canal; falta só a camada
  de webhook.
- **Print do trecho destacado**: além do link para a página, gerar uma imagem da página do PDF com a
  frase marcada em amarelo e enviá-la junto da resposta. O passo seguinte natural, já que os
  procedimentos são exigidos em PDF e a resposta já sabe a página e o trecho literal.
- Análise visual da foto (comparar imagem com o procedimento via Claude) — hoje a foto só é anexada
  como registro.
- Multi-tenant real (o schema já carrega `company_id` em tudo), cobrança/assinatura, e a frente de
  rastreamento de concretagem com fotos.
