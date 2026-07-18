-- Procede MVP schema. Every table carries company_id (directly or via join)
-- so a future real multi-tenant split does not require a migration.

create extension if not exists vector;
create extension if not exists "pgcrypto";

create table companies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz not null default now()
);

create table sites (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    name text not null,
    address text,
    active boolean not null default true
);

create table users (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    name text not null,
    phone_number text,
    role text,
    site_id uuid references sites(id),
    is_admin boolean not null default false,
    email text unique,
    password_hash text
);
create index users_phone_number_idx on users(phone_number);
create index users_company_id_idx on users(company_id);

create table documents (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references companies(id),
    title text not null,
    category text not null,
    kind text not null check (kind in ('procedimento', 'administrativo')),
    site_id uuid references sites(id),
    file_path text not null,
    version integer not null default 1,
    uploaded_by uuid references users(id),
    uploaded_at timestamptz not null default now(),
    status text not null default 'active' check (status in ('active', 'archived'))
);
create index documents_company_id_idx on documents(company_id);
create index documents_kind_idx on documents(kind);
create index documents_site_id_idx on documents(site_id);

-- 1024 dims = voyage-3 embedding size
create table document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    content text not null,
    embedding vector(1024) not null,
    page_ref integer,
    section_ref text
);
create index document_chunks_document_id_idx on document_chunks(document_id);
create index document_chunks_embedding_idx on document_chunks
    using hnsw (embedding vector_cosine_ops);

create table conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id),
    site_id uuid references sites(id),
    channel text not null check (channel in ('web', 'whatsapp')),
    started_at timestamptz not null default now()
);
create index conversations_user_id_idx on conversations(user_id);

create table messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id),
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    media_type text not null default 'text' check (media_type in ('text', 'audio', 'image')),
    media_url text,
    transcript text,
    chunks_used uuid[],
    document_returned_id uuid references documents(id),
    had_fallback boolean not null default false,
    created_at timestamptz not null default now()
);
create index messages_conversation_id_idx on messages(conversation_id);
create index messages_had_fallback_idx on messages(had_fallback);
