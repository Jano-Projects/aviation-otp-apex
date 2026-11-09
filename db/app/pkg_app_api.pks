create or replace package pkg_app_api authid definer as
  /*
   * Actions the web application (APEX pages and REST services) may run.
   *
   * Transaction contract: unlike the observatory's packages, these procedures
   * COMMIT. In the observatory, the caller decides when to commit; here, the
   * caller is an HTTP request, and the end of the request is the end of the
   * unit of work.
   */

  /*
   * Rebuilds the star schema for one month (any date inside it), or for every
   * month when p_month is NULL. Returns the number of months rebuilt.
   */
  function refresh_mart(p_month in date default null) return pls_integer;

  /*
   * 'YYYY-MM' -> first day of that month. NULL for NULL; ORA-20200 for anything else.
   */
  function to_month(p_value in varchar2) return date;

end pkg_app_api;
/
