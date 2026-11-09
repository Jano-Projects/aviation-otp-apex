--------------------------------------------------------------------------------
-- Indicator views of the application layer (schema OTP_APP).
--
-- Every view keeps ADDITIVE measures (flights, cancelled, measurable, on_time):
-- sums can be added across months, airlines or airports, while percentages
-- cannot (the average of monthly percentages is not the percentage of the
-- period). Consumers compute
--   on_time_pct   = 100 * sum(on_time)   / sum(measurable)
--   cancelled_pct = 100 * sum(cancelled) / sum(flights)
-- after filtering. The *_pct columns here are for one row as it stands.
--------------------------------------------------------------------------------

create or replace view v_months as
select d.month_start,
       to_char(d.month_start, 'YYYY-MM') as month_label
  from (select distinct month_start from otp.fact_flight) d;

comment on table v_months is 'Months available in the star schema (for lists of values).';

create or replace view v_otp_month as
select f.month_start,
       to_char(f.month_start, 'YYYY-MM')                                   as month_label,
       count(*)                                                            as flights,
       sum(f.is_flown)                                                     as flown,
       sum(f.is_cancelled)                                                 as cancelled,
       sum(f.is_measurable)                                                as measurable,
       sum(f.on_time_15)                                                   as on_time,
       round(100 * sum(f.on_time_15) / nullif(sum(f.is_measurable), 0), 1) as on_time_pct,
       round(100 * sum(f.is_cancelled) / count(*), 1)                      as cancelled_pct,
       round(avg(case when f.is_measurable = 1 then f.arr_delay_min end), 1) as avg_arr_delay_min
  from otp.fact_flight f
 group by f.month_start;

comment on table v_otp_month is 'Punctuality per month, all flights.';

create or replace view v_otp_airline_month as
select f.month_start,
       f.line_type,
       a.airline_icao,
       coalesce(a.airline_name, a.airline_icao)  as airline_name,
       a.nationality,
       count(*)                                  as flights,
       sum(f.is_cancelled)                       as cancelled,
       sum(f.is_measurable)                      as measurable,
       sum(f.on_time_15)                         as on_time
  from otp.fact_flight f
  join otp.dim_airline a on a.airline_key = f.airline_key
 group by f.month_start, f.line_type, a.airline_icao, a.airline_name, a.nationality;

comment on table v_otp_airline_month is 'Punctuality per month, line type and airline (additive measures).';

create or replace view v_otp_airport_month as
select f.month_start,
       f.line_type,
       o.airport_icao,
       coalesce(o.airport_name, o.city, o.airport_icao) as airport_name,
       o.city,
       o.state_uf,
       o.country_name,
       o.is_brazil,
       o.latitude,
       o.longitude,
       count(*)                                         as departures,
       sum(f.is_cancelled)                              as cancelled,
       sum(f.is_measurable)                             as measurable,
       sum(f.on_time_15)                                as on_time
  from otp.fact_flight f
  join otp.dim_airport o on o.airport_key = f.orig_airport_key
 group by f.month_start, f.line_type, o.airport_icao, o.airport_name, o.city, o.state_uf,
          o.country_name, o.is_brazil, o.latitude, o.longitude;

comment on table v_otp_airport_month is 'Punctuality per month, line type and ORIGIN airport (additive measures).';

create or replace view v_otp_route_month as
select f.month_start,
       f.line_type,
       o.airport_icao                       as orig_icao,
       coalesce(o.city, o.airport_icao)     as orig_city,
       d.airport_icao                       as dest_icao,
       coalesce(d.city, d.airport_icao)     as dest_city,
       count(*)                             as flights,
       sum(f.is_cancelled)                  as cancelled,
       sum(f.is_measurable)                 as measurable,
       sum(f.on_time_15)                    as on_time
  from otp.fact_flight f
  join otp.dim_airport o on o.airport_key = f.orig_airport_key
  join otp.dim_airport d on d.airport_key = f.dest_airport_key
 group by f.month_start, f.line_type, o.airport_icao, o.city, d.airport_icao, d.city;

comment on table v_otp_route_month is 'Punctuality per month, line type and route (additive measures).';

create or replace view v_otp_weekday_month as
select f.month_start,
       f.line_type,
       d.iso_day_of_week,
       d.day_name_pt,
       count(*)              as flights,
       sum(f.is_cancelled)   as cancelled,
       sum(f.is_measurable)  as measurable,
       sum(f.on_time_15)     as on_time
  from otp.fact_flight f
  join otp.dim_date d on d.date_key = f.date_key
 group by f.month_start, f.line_type, d.iso_day_of_week, d.day_name_pt;

comment on table v_otp_weekday_month is 'Punctuality per month, line type and day of the week (additive measures).';

create or replace view v_otp_hour_month as
select f.month_start,
       f.line_type,
       h.hour_key,
       h.period_pt,
       count(*)              as flights,
       sum(f.is_cancelled)   as cancelled,
       sum(f.is_measurable)  as measurable,
       sum(f.on_time_15)     as on_time
  from otp.fact_flight f
  join otp.dim_hour h on h.hour_key = f.dep_hour
 group by f.month_start, f.line_type, h.hour_key, h.period_pt;

comment on table v_otp_hour_month is 'Punctuality per month, line type and hour of scheduled departure (additive measures).';

create or replace view v_load_runs as
select r.run_id,
       r.src_file,
       to_char(r.ref_month, 'YYYY-MM')  as month_label,
       r.status,
       r.started_at,
       r.finished_at,
       r.rows_staged,
       r.rows_loaded,
       r.rows_rejected,
       r.rows_duplicate,
       r.error_message
  from otp.core_load_run r;

comment on table v_load_runs is 'Audit log of every load of the observatory (VRA, reference data, star schema).';
