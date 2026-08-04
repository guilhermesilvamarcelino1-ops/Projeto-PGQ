-- Permissão por família de documento, imposta pelo banco.
--
-- Motivo: 31 dos 86 tipos da taxonomia carregam dado pessoal (RH, funcionário,
-- cliente). Sem esta restrição, o mestre de obra perguntando no chat alcançaria
-- ficha de funcionário e ASO — o assistente viraria canal de vazamento (LGPD).
--
-- Mesmo princípio do isolamento por empresa: o backend fixa as famílias permitidas
-- na transação e as policies recusam o resto. Sem contexto, nenhuma linha aparece.

-- 1) Todo documento passa a declarar a que família pertence.
alter table public.documents
    add column document_type_id uuid references public.document_types(id),
    add column family text check (family in (
        'qualidade_gestao', 'projetos_obra', 'suprimentos', 'comercial_cliente', 'pessoas_seguranca'
    ));

-- Documentos já existentes: procedimento é material do SGQ; administrativo
-- (alvará, ART, contrato de obra) pertence à família de obra na taxonomia.
update public.documents
   set family = case kind when 'procedimento' then 'qualidade_gestao' else 'projetos_obra' end
 where family is null;

alter table public.documents alter column family set not null;
create index documents_family_idx on public.documents(family);

-- 2) Mesma marcação nos trechos, para a busca vetorial filtrar sem join.
alter table public.document_chunks add column family text;
update public.document_chunks dc
   set family = d.family from public.documents d where d.id = dc.document_id;
alter table public.document_chunks alter column family set not null;
create index document_chunks_family_idx on public.document_chunks(family);

-- 3) Quem pode ver o quê. Ausência de linha = sem acesso (nunca o contrário).
create table public.user_family_access (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references public.companies(id),
    user_id uuid not null references public.users(id) on delete cascade,
    family text not null check (family in (
        'qualidade_gestao', 'projetos_obra', 'suprimentos', 'comercial_cliente', 'pessoas_seguranca'
    )),
    -- ler é o padrão; enviar documento novo é permissão separada
    can_upload boolean not null default false,
    created_at timestamptz not null default now(),
    unique (user_id, family)
);
create index user_family_access_user_idx on public.user_family_access(user_id);

alter table public.user_family_access enable row level security;
create policy tenant_isolation on public.user_family_access
    for all to app_tenant
    using (company_id = public.current_company_id())
    with check (company_id = public.current_company_id());

-- 4) Famílias permitidas na requisição atual. Vazio quando não definido —
--    array vazio faz `family = any(...)` ser falso, ou seja, fail-closed.
create or replace function public.current_families() returns text[]
language sql stable as $$
  select coalesce(
    string_to_array(nullif(current_setting('app.current_families', true), ''), ','),
    array[]::text[]
  )
$$;

-- 5) Policies passam a exigir empresa E família permitida.
drop policy tenant_isolation on public.documents;
create policy tenant_isolation on public.documents
    for all to app_tenant
    using (company_id = public.current_company_id() and family = any(public.current_families()))
    with check (company_id = public.current_company_id() and family = any(public.current_families()));

drop policy tenant_isolation on public.document_chunks;
create policy tenant_isolation on public.document_chunks
    for all to app_tenant
    using (company_id = public.current_company_id() and family = any(public.current_families()))
    with check (company_id = public.current_company_id() and family = any(public.current_families()));

-- A taxonomia em si não é sigilosa (é a régua de arquivamento), mas listar tipos
-- de família que a pessoa não acessa não serve para nada — e evita revelar a
-- estrutura de RH para quem não deve vê-la.
drop policy tenant_isolation on public.document_types;
create policy tenant_isolation on public.document_types
    for all to app_tenant
    using (company_id = public.current_company_id() and family = any(public.current_families()))
    with check (company_id = public.current_company_id() and family = any(public.current_families()));
