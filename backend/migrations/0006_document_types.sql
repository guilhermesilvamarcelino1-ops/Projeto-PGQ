-- Taxonomia documental POR EMPRESA (a "tabela do RQ 15" da Persa é da Persa).
--
-- Por que dado e não prompt: se a tabela vivesse dentro do prompt, cada cliente
-- exigiria um prompt customizado, o modelo poderia "lembrar errado" um código que
-- não existe, e a revisão do SGQ obrigaria a editar código. Como dado, a IA não
-- recorda a tabela — ela escolhe uma linha que existe, e "não está no RQ 15" vira
-- fato verificável em vez de julgamento.
--
-- A retenção deixa de ser prosa ("Fim de obra", "24 meses") e vira regra computável:
-- é isso que permite, adiante, o sistema avisar sobre vencimento e descarte.

create table public.document_types (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references public.companies(id),

    code text,                    -- 'RQ 30', 'PES', 'PQO'... nulo quando o documento não tem código
    name text not null,           -- nome oficial na tabela da empresa
    family text not null check (family in (
        'qualidade_gestao', 'projetos_obra', 'suprimentos', 'comercial_cliente', 'pessoas_seguranca'
    )),

    -- Onde o documento vive. 'sistema' = mora em ERP de terceiro (Sienge, Cândido).
    medium text not null check (medium in ('eletronico', 'fisico', 'ambos', 'sistema')),
    storage_path text,            -- caminho eletrônico (ex.: '01. SGQ/11. Projetos')
    physical_location text,       -- onde a via em papel deve ser arquivada
    external_system text,         -- nome do ERP, quando medium = 'sistema'

    recovery_key text,            -- chave pela qual o documento é procurado depois

    -- Retenção computável: regra + prazo, em vez de texto livre.
    retention_rule text not null check (retention_rule in (
        'permanente',                 -- guarda indefinida
        'ate_proxima_atualizacao',    -- vive até ser substituído por revisão nova
        'fim_de_obra',                -- depende da data de encerramento da obra
        'meses',                      -- retention_months a partir da data do documento
        'ate_validade',               -- depende da validade impressa no próprio documento
        'tempo_contratacao'           -- enquanto a pessoa estiver contratada
    )),
    retention_months integer,     -- preenchido quando retention_rule = 'meses'

    disposal text not null check (disposal in (
        'arquivo_permanente', 'substituir', 'destruir', 'acervo_tecnico'
    )),

    -- Documento versionado leva REV no nome; registro de evento único, não.
    has_revisions boolean not null default false,
    -- Marca LGPD: restringe quem pode consultar e impede que apareça no chat de campo.
    contains_personal_data boolean not null default false,

    active boolean not null default true,
    created_at timestamptz not null default now()
);

create index document_types_company_id_idx on public.document_types(company_id);
create index document_types_family_idx on public.document_types(family);

-- Código é único dentro da empresa (quando existe).
create unique index document_types_company_code_uniq
    on public.document_types(company_id, code)
    where code is not null;

alter table public.document_types enable row level security;

create policy tenant_isolation on public.document_types
    for all to app_tenant
    using (company_id = public.current_company_id())
    with check (company_id = public.current_company_id());
