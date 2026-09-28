-- created in supabase. Left here for reference as the database structure

create table if not exists public.products (
    barcode text primary key,
    name text,
    brand text,
    ingredients_raw text,
    is_hair boolean,
    lookup_status text not null check (lookup_status in ('found', 'not_found')),
    fetched_at timestamptz not null default now(),
    expires_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists products_expires_at_idx
    on public.products (expires_at);

alter table public.products enable row level security;
