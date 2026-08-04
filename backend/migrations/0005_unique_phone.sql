-- O WhatsApp do Procede é um número central, compartilhado por todos os clientes.
-- Quem identifica a pessoa (e a empresa dela) é o número de QUEM ENVIA a mensagem.
-- Logo, o telefone precisa ser único no sistema inteiro: se o mesmo número existisse
-- em duas empresas, o sistema não saberia qual acervo abrir e o atendimento daquela
-- pessoa quebraria.
--
-- Admins não têm telefone (entram por email+senha), por isso o índice ignora NULL.

-- Antes de aplicar: garanta que não há telefone repetido.
--   select phone_number, count(*) from users
--   where phone_number is not null group by phone_number having count(*) > 1;

-- PIN do login de campo na versão web (o WhatsApp dispensa: o número verificado
-- pela Meta já identifica a pessoa). A coluna acompanha o modelo desde o login de
-- campo, mas faltava no banco.
alter table public.users add column if not exists pin_hash text;

drop index if exists users_phone_number_idx;

create unique index users_phone_number_uniq
    on public.users(phone_number)
    where phone_number is not null;
