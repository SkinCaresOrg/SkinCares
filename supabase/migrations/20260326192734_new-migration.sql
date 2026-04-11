create table if not exists public.swipe_events (
	id bigserial primary key,
	user_id text not null,
	product_id integer not null,
	has_tried boolean not null,
	reaction text,
	skipped_questionnaire boolean not null default false,
	created_at timestamptz not null default now()
);

create index if not exists idx_swipe_events_user_id on public.swipe_events (user_id);
create index if not exists idx_swipe_events_product_id on public.swipe_events (product_id);

create table if not exists public.questionnaire_responses (
	id bigserial primary key,
	swipe_event_id bigint not null references public.swipe_events(id) on delete cascade,
	user_id text not null,
	product_id integer not null,
	reaction text not null,
	reason_tags jsonb not null default '[]'::jsonb,
	free_text text not null default '',
	created_at timestamptz not null default now()
);

create index if not exists idx_questionnaire_swipe_event_id on public.questionnaire_responses (swipe_event_id);
create index if not exists idx_questionnaire_user_id on public.questionnaire_responses (user_id);
create index if not exists idx_questionnaire_product_id on public.questionnaire_responses (product_id);
