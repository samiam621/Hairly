-- Safe to re-run: `python -m backend.db.seed` applies this file, then loads the rules.

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

-- Rules. Source of truth is rules.json + aliases.json; the seed script copies them in.
create table if not exists public.concerns (
    id serial primary key,
    slug text unique not null,
    label text not null
);

create table if not exists public.ingredients (
    id serial primary key,
    canonical_name text unique not null
);

create table if not exists public.ingredient_aliases (
    alias text primary key,  -- already normalized
    ingredient_id int not null references public.ingredients (id)
);

create table if not exists public.concern_rules (
    concern_id int not null references public.concerns (id),
    ingredient_id int not null references public.ingredients (id),
    severity text not null check (severity in ('low', 'medium', 'high')),
    reason text not null,
    primary key (concern_id, ingredient_id)
);

-- Rule-curation backlog: ingredients the rules did not recognize
create table if not exists public.unrecognized_ingredients (
    name text primary key,
    seen_count int not null default 1,
    first_seen timestamptz not null default now()
);

alter table public.concerns enable row level security;
alter table public.ingredients enable row level security;
alter table public.ingredient_aliases enable row level security;
alter table public.concern_rules enable row level security;
alter table public.unrecognized_ingredients enable row level security;
