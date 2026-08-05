-- Conexão da empresa com o drive dela (OneDrive/SharePoint via Microsoft Graph).
--
-- O acervo continua sendo do cliente: o arquivo é gravado na pasta dele, com a
-- estrutura do RQ 15 dele. Guardamos apenas a autorização para escrever lá.
--
-- Quem entrega o arquivo ao time de campo somos nós, pelo link assinado: o mestre
-- de obra normalmente não tem licença Microsoft 365 e receberia "acesso negado" se
-- o link apontasse direto para o drive.

create table public.drive_connections (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references public.companies(id),

    provider text not null check (provider in ('onedrive', 'sharepoint', 'google_drive')),

    -- Identificação da conta/drive autorizado, para exibir no painel e para as chamadas.
    account_email text,
    drive_id text,
    -- Pasta raiz do acervo dentro do drive; os caminhos do RQ 15 pendem daqui.
    root_path text not null default 'Procede',

    -- O refresh token é a credencial de longa duração: com ele o sistema renova o
    -- acesso sozinho. Nunca é exposto em resposta de API.
    refresh_token text not null,
    access_token text,
    access_token_expires_at timestamptz,

    connected_by uuid references public.users(id),
    connected_at timestamptz not null default now(),
    last_error text,
    active boolean not null default true
);

create index drive_connections_company_idx on public.drive_connections(company_id);
-- Uma conexão ativa por provedor, por empresa.
create unique index drive_connections_company_provider_uniq
    on public.drive_connections(company_id, provider) where active;

alter table public.drive_connections enable row level security;
create policy tenant_isolation on public.drive_connections
    for all to app_tenant
    using (company_id = public.current_company_id())
    with check (company_id = public.current_company_id());
