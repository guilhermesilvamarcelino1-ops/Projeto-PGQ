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
