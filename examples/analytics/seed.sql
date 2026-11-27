-- Demo dataset for the analytics task: a small, fully deterministic sales
-- warehouse. Every value is computed, so report numbers can be re-verified
-- by re-running the same query. Safe to re-run (idempotent).
--
--   psql "$AGENT0_DATABASE_URL" -f examples/analytics/seed.sql

create schema if not exists analytics;

drop table if exists analytics.orders;
drop table if exists analytics.products;
drop table if exists analytics.regions;

create table analytics.regions (name text primary key);
create table analytics.products (name text primary key, category text not null, unit_price numeric not null);
create table analytics.orders (
    order_id   int primary key,
    order_month date not null,
    region     text not null references analytics.regions(name),
    product    text not null references analytics.products(name),
    units      int not null,
    revenue    numeric not null
);

insert into analytics.regions (name) values
    ('north'), ('south'), ('east'), ('west');

insert into analytics.products (name, category, unit_price) values
    ('aurora-blender',  'kitchen',   89.00),
    ('boreal-kettle',   'kitchen',   64.50),
    ('cedar-cutting',   'outdoor',  129.00),
    ('delta-dryer',     'laundry',   42.00),
    ('ember-heater',    'home',      75.25),
    ('falcon-fan',      'home',      38.00);

-- 4 regions x 6 products x 12 months = 288 orders. units and revenue are pure
-- functions of the indexes, so the data is identical on every seed.
insert into analytics.orders (order_id, order_month, region, product, units, revenue)
select
    g                                        as order_id,
    date '2025-01-01' + ((m - 1) || ' months')::interval as order_month,
    (array['north','south','east','west'])[r]  as region,
    (array['aurora-blender','boreal-kettle','cedar-cutting',
           'delta-dryer','ember-heater','falcon-fan'])[p]        as product,
    1 + ((r * 5 + p * 3 + m * 7) % 19)       as units,
    round((1 + ((r * 5 + p * 3 + m * 7) % 19)) *
          (array[89.00,64.50,129.00,42.00,75.25,38.00])[p], 2)   as revenue
from generate_series(1, 4) r,
     generate_series(1, 6) p,
     generate_series(1, 12) m,
     lateral (select (r - 1) * 72 + (p - 1) * 12 + m as g) ids;
