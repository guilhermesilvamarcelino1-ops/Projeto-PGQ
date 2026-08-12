-- Documento enviado, classificado, aguardando a confirmação de um toque.
--
-- Existe porque nada é arquivado sem confirmação: classificar errado em silêncio é
-- pior do que não classificar — um laudo salvo como ata é um documento que ninguém
-- encontra no dia da auditoria. Entre "enviei a foto" e "confirmei", o arquivo fica
-- aqui, fora do acervo.

create table public.pending_filings (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references public.companies(id),
    -- A família decide quem pode ver e confirmar esta pendência.
    family text not null check (family in (
        'qualidade_gestao', 'projetos_obra', 'suprimentos', 'comercial_cliente', 'pessoas_seguranca'
    )),
    document_type_id uuid references public.document_types(id),
    created_by uuid references public.users(id),

    -- Proposta completa (nome, caminho, campos extraídos, validade, confiança):
    -- guardada como veio para o log mostrar depois o que foi proposto e o que a
    -- pessoa confirmou ou corrigiu.
    proposal jsonb not null,

    -- Arquivo aguardando decisão, ainda fora do acervo do cliente.
    staged_path text not null,
    original_filename text,
    content_type text,

    status text not null default 'aguardando'
        check (status in ('aguardando', 'confirmado', 'recusado', 'expirado')),
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    -- Documento gerado quando confirmado.
    document_id uuid references public.documents(id)
);

create index pending_filings_company_idx on public.pending_filings(company_id);
create index pending_filings_status_idx on public.pending_filings(status);

alter table public.pending_filings enable row level security;
create policy tenant_isolation on public.pending_filings
    for all to app_tenant
    using (company_id = public.current_company_id() and family = any(public.current_families()))
    with check (company_id = public.current_company_id() and family = any(public.current_families()));
