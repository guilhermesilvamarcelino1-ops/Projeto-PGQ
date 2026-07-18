-- O backend acessa o banco pela conexão direta (role postgres, que ignora RLS).
-- Habilitar RLS sem policies bloqueia o acesso anônimo via API REST (PostgREST/anon key),
-- que não é usada por este produto. Fecha os avisos rls_disabled_in_public do Supabase.
--
-- Quando o produto virar multi-tenant real (Fase 3), estas tabelas ganham policies
-- baseadas em company_id em vez de dependerem só da conexão de serviço.

alter table public.companies enable row level security;
alter table public.sites enable row level security;
alter table public.users enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
