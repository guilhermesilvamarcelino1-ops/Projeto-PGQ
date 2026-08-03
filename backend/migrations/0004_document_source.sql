-- Prepara o sistema para documentos que vivem FORA da nossa plataforma
-- (SharePoint, Google Drive), sem construir o conector ainda.
--
-- Motivo: o índice de busca é sempre nosso, mas o ARQUIVO pode continuar sendo do
-- cliente, no sistema onde ele já revisa os procedimentos hoje. Registrar a origem
-- desde já evita ter que reescrever a ingestão e os links quando o conector existir
-- (mesma lógica do company_id, que poupou uma migração dolorosa).

alter table public.documents
    add column source_type text not null default 'upload'
        check (source_type in ('upload', 'sharepoint', 'google_drive')),
    -- identificador do arquivo no sistema de origem (ex.: driveItem id do Graph)
    add column external_id text,
    -- endereço para abrir o documento na origem; quando presente, é ele que vai
    -- no link enviado ao usuário, em vez de servirmos uma cópia nossa
    add column external_url text,
    -- data da última modificação registrada na origem: base para detectar revisão
    add column external_modified_at timestamptz,
    add column last_synced_at timestamptz;

-- Documento vindo de conector não tem cópia local obrigatória.
alter table public.documents alter column file_path drop not null;

create index documents_source_type_idx on public.documents(source_type);

-- Um mesmo arquivo de origem não pode ser indexado duas vezes para a mesma empresa.
create unique index documents_external_uniq
    on public.documents(company_id, source_type, external_id)
    where external_id is not null;
