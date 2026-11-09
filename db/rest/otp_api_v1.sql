--------------------------------------------------------------------------------
-- REST API of the observatory, served by ORDS. Run as OTP_APP.
--
--   GET  /ords/otp/api/v1/months
--   GET  /ords/otp/api/v1/airlines?month_from=YYYY-MM&month_to=YYYY-MM&line_type=N
--   GET  /ords/otp/api/v1/airports?month_from=...&month_to=...&line_type=...
--   GET  /ords/otp/api/v1/hours?month_from=...&month_to=...&line_type=...
--   GET  /ords/otp/api/v1/weekdays?month_from=...&month_to=...&line_type=...
--   GET  /ords/otp/api/v1/runs
--   POST /ords/otp/api/v1/mart/refresh?month=YYYY-MM     (no month = every month)
--
-- Query parameters are bound by name (:month_from, :month_to, :line_type, :month).
-- All filters are optional. Percentages are computed from additive sums AFTER
-- filtering, never averaged.
--
-- define_module replaces an existing module with the same name, so this script
-- can be re-run after any change.
--------------------------------------------------------------------------------
whenever sqlerror exit failure rollback
set define off feedback off serveroutput on

declare
  c_module  constant varchar2(30) := 'otp.api.v1';

  -- Shared filter: month range and line type, all optional.
  c_filter  constant varchar2(400) :=
       ' where month_start between pkg_app_api.to_month(nvl(:month_from, ''1900-01''))'
    || '                       and pkg_app_api.to_month(nvl(:month_to, ''9999-12''))'
    || '   and (:line_type is null or line_type = :line_type)';

  -- Shared measures: additive sums, then the percentages of the filtered period.
  c_measures constant varchar2(400) :=
       ' sum(flights) as flights, sum(cancelled) as cancelled,'
    || ' sum(measurable) as measurable, sum(on_time) as on_time,'
    || ' round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct,'
    || ' round(100 * sum(cancelled) / nullif(sum(flights), 0), 1) as cancelled_pct';

  procedure get_collection(p_pattern in varchar2, p_source in varchar2) is
  begin
    ords.define_template(p_module_name => c_module, p_pattern => p_pattern);
    ords.define_handler(
      p_module_name    => c_module,
      p_pattern        => p_pattern,
      p_method         => 'GET',
      p_source_type    => ords.source_type_collection_feed,
      p_items_per_page => 0,
      p_source         => p_source);
  end get_collection;
begin
  ords.enable_schema(
    p_enabled             => true,
    p_schema              => 'OTP_APP',
    p_url_mapping_type    => 'BASE_PATH',
    p_url_mapping_pattern => 'otp',
    p_auto_rest_auth      => true);

  ords.define_module(
    p_module_name    => c_module,
    p_base_path      => '/api/v1/',
    p_items_per_page => 0,
    p_status         => 'PUBLISHED',
    p_comments       => 'Aviation OTP Observatory: punctuality indicators and actions');

  get_collection('months',
       'select month_label, flights, cancelled, measurable, on_time, on_time_pct, cancelled_pct,'
    || '       avg_arr_delay_min'
    || '  from v_otp_month order by month_start');

  get_collection('airlines',
       'select airline_icao, airline_name,' || c_measures
    || '  from v_otp_airline_month' || c_filter
    || ' group by airline_icao, airline_name order by flights desc');

  get_collection('airports',
       'select airport_icao, airport_name, city, state_uf, country_name, latitude, longitude,'
    || c_measures
    || '  from (select month_start, line_type, airport_icao, airport_name, city, state_uf,'
    || '               country_name, latitude, longitude, departures as flights, cancelled,'
    || '               measurable, on_time from v_otp_airport_month)' || c_filter
    || ' group by airport_icao, airport_name, city, state_uf, country_name, latitude, longitude'
    || ' order by flights desc');

  get_collection('hours',
       'select hour_key, period_pt,' || c_measures
    || '  from v_otp_hour_month' || c_filter
    || ' group by hour_key, period_pt order by hour_key');

  get_collection('weekdays',
       'select iso_day_of_week, day_name_pt,' || c_measures
    || '  from v_otp_weekday_month' || c_filter
    || ' group by iso_day_of_week, day_name_pt order by iso_day_of_week');

  get_collection('runs',
       'select run_id, src_file, month_label, status, started_at, finished_at,'
    || '       rows_staged, rows_loaded, rows_rejected, rows_duplicate'
    || '  from v_load_runs order by run_id desc fetch first 50 rows only');

  -- Action: rebuild the star schema.
  ords.define_template(p_module_name => c_module, p_pattern => 'mart/refresh');
  ords.define_handler(
    p_module_name => c_module,
    p_pattern     => 'mart/refresh',
    p_method      => 'POST',
    p_source_type => ords.source_type_plsql,
    p_source      =>
         'declare'
      || '  l_months pls_integer;'
      || 'begin'
      || '  l_months := pkg_app_api.refresh_mart(pkg_app_api.to_month(:month));'
      || '  owa_util.mime_header(''application/json'', true);'
      || '  htp.p(''{"months_refreshed":'' || l_months || ''}'');'
      || 'end;');

  commit;
  dbms_output.put_line('REST module ' || c_module || ' published at /ords/otp/api/v1/');
end;
/
