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

### Dois tipos de documento ("pasta mãe")

- `procedimento` — POP, FVS, memoriais. É quebrado em trechos, indexado e pesquisado via RAG.
- `administrativo` — alvará, habite-se, ART, contratos. Indexado só por metadado (obra + tipo) e
  devolvido como arquivo inteiro quando o usuário pede ("me manda o alvará do empreendimento X").

## Rodando o backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # preencha as chaves (Anthropic, Voyage, DATABASE_URL, JWT_SECRET)

# aplique o schema no Postgres/Supabase (precisa da extensão pgvector):
psql "$DATABASE_URL_PSQL" -f migrations/0001_init.sql

# crie empresa, obra e admin:
python -m scripts.seed --admin-email qualidade@persa.com --admin-password 'senha-forte'

uvicorn app.main:app --reload
```

> `DATABASE_URL` usa o driver async (`postgresql+asyncpg://...`). Para rodar a migration com `psql`
> use a URL padrão `postgresql://...`.

### Variáveis de ambiente (backend)

| Var | Uso |
|-----|-----|
| `DATABASE_URL` | Postgres async (`postgresql+asyncpg://...`) |
| `ANTHROPIC_API_KEY` | Geração da resposta e classificação de intenção (Claude) |
| `VOYAGE_API_KEY` | Embeddings de busca (voyage-3) |
| `OPENAI_API_KEY` | Opcional — transcrição de áudio (Whisper) |
| `JWT_SECRET` | Assinatura do token do painel admin |
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
pytest        # testes unitários (chunking + fallback do RAG) rodam sem banco;
              # os testes de lookup pulam sozinhos se não houver Postgres.
```

O teste mais importante é `tests/test_rag_fallback.py`: garante que o assistente nunca responde com
conhecimento geral e cai no fallback (indicando o responsável técnico) quando o material não cobre a
pergunta.

## Fora do escopo deste MVP (roadmap)

- Canal WhatsApp (Meta Cloud API direto) — o fluxo de RAG já é agnóstico de canal; falta só a camada
  de webhook.
- Análise visual da foto (comparar imagem com o procedimento via Claude) — hoje a foto só é anexada
  como registro.
- Multi-tenant real (o schema já carrega `company_id` em tudo), cobrança/assinatura, e a frente de
  rastreamento de concretagem com fotos.
