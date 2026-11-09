create or replace package body pkg_app_api as

  function to_month(p_value in varchar2) return date is
  begin
    if p_value is null then
      return null;
    end if;
    if not regexp_like(p_value, '^\d{4}-(0[1-9]|1[0-2])$') then
      raise_application_error(-20200, 'Month must be YYYY-MM, got "' || substr(p_value, 1, 20) || '".');
    end if;
    return to_date(p_value || '-01', 'YYYY-MM-DD');
  end to_month;

  function refresh_mart(p_month in date default null) return pls_integer is
    l_months  pls_integer;
    l_run_id  number;
  begin
    if p_month is null then
      l_months := otp.pkg_mart.refresh_all;
    else
      l_run_id := otp.pkg_mart.refresh_month(p_month);
      l_months := 1;
    end if;
    commit;
    return l_months;
  end refresh_mart;

end pkg_app_api;
/
