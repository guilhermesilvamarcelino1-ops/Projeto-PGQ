-- Isolamento multi-tenant forçado pelo banco (defesa em profundidade).
-- Contexto: o papel `postgres` do Supabase tem BYPASSRLS, então o backend NÃO pode
-- conectar como postgres — ele conecta como o papel `app_tenant` (sem bypass de RLS)
-- e define `app.current_company_id` por transação. As policies abaixo garantem que
-- uma empresa nunca alcance dados de outra, mesmo que o código da aplicação erre.
--
-- IMPORTANTE: troque a senha do app_tenant antes de qualquer uso além do piloto e
-- injete-a por variável de ambiente (não deixe hardcoded em ambientes reais).

-- 1) Desnormaliza company_id nas tabelas que só tinham vínculo indireto,
--    para policies simples e busca vetorial mais rápida.
alter table public.document_chunks add column company_id uuid references public.companies(id);
update public.document_chunks dc
  set company_id = d.company_id from public.documents d where d.id = dc.document_id;
alter table public.document_chunks alter column company_id set not null;
create index document_chunks_company_id_idx on public.document_chunks(company_id);

alter table public.conversations add column company_id uuid references public.companies(id);
update public.conversations cv
  set company_id = u.company_id from public.users u where u.id = cv.user_id;
alter table public.conversations alter column company_id set not null;
create index conversations_company_id_idx on public.conversations(company_id);

alter table public.messages add column company_id uuid references public.companies(id);
update public.messages m
  set company_id = cv.company_id from public.conversations cv where cv.id = m.conversation_id;
alter table public.messages alter column company_id set not null;
create index messages_company_id_idx on public.messages(company_id);

-- 2) Papel de aplicação do backend, sujeito a RLS (NOBYPASSRLS é o default).
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_tenant') then
    create role app_tenant login password 'TROQUE_ESTA_SENHA';
  end if;
end$$;

grant usage on schema public to app_tenant;
grant select, insert, update, delete on all tables in schema public to app_tenant;
alter default privileges in schema public grant select, insert, update, delete on tables to app_tenant;

-- 3) Helper: company_id do contexto atual (NULL durante a resolução de identidade).
create or replace function public.current_company_id() returns uuid
language sql stable as $$
  select nullif(current_setting('app.current_company_id', true), '')::uuid
$$;

-- 4) Policies das tabelas de conteúdo: estritamente escopadas por empresa.
--    Sem contexto (NULL), current_company_id() = NULL => nenhuma linha (fail-closed).
create policy tenant_isolation on public.sites
  for all to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy tenant_isolation on public.documents
  for all to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy tenant_isolation on public.document_chunks
  for all to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy tenant_isolation on public.conversations
  for all to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy tenant_isolation on public.messages
  for all to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

-- 5) Tabelas de identidade (users, companies): a resolução de login/telefone acontece
--    ANTES de haver contexto de empresa. Permite leitura durante o bootstrap
--    (contexto NULL) e, definido o contexto, restringe à própria empresa.
--    Escrita sempre exige contexto da empresa.
create policy identity_users_select on public.users
  for select to app_tenant
  using (public.current_company_id() is null or company_id = public.current_company_id());
create policy identity_users_write on public.users
  for insert to app_tenant
  with check (company_id = public.current_company_id());
create policy identity_users_update on public.users
  for update to app_tenant
  using (company_id = public.current_company_id())
  with check (company_id = public.current_company_id());

create policy identity_companies_select on public.companies
  for select to app_tenant
  using (public.current_company_id() is null or id = public.current_company_id());
