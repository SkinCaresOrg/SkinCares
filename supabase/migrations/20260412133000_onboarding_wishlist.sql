alter table if exists public.users
add column if not exists onboarding_completed boolean not null default false;

create table if not exists public.wishlist_items (
    id bigserial primary key,
    user_id text not null,
    product_id integer not null,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_wishlist_user_product
on public.wishlist_items (user_id, product_id);

create index if not exists idx_wishlist_user_id
on public.wishlist_items (user_id);

create index if not exists idx_wishlist_product_id
on public.wishlist_items (product_id);
