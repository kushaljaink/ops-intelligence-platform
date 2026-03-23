create extension if not exists pgcrypto;

create table if not exists platform_metrics (
    id uuid primary key default gen_random_uuid(),
    metric_name text not null unique,
    metric_value int not null default 0,
    updated_at timestamptz not null default now()
);

create index if not exists idx_platform_metrics_metric_name
    on platform_metrics (metric_name);
