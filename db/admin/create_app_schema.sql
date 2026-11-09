--------------------------------------------------------------------------------
-- Creates the schema OTP_APP, the application layer of the web app (idempotent).
-- Run as SYS in FREEPDB1. Substitution variable: app_password.
--
-- Least privilege: OTP_APP owns only views, one API package and the REST
-- definitions. It can READ the observatory's tables and EXECUTE pkg_mart, object
-- by object; it cannot change the data of schema OTP directly.
--------------------------------------------------------------------------------
whenever sqlerror exit failure rollback
set verify off feedback off serveroutput on

declare
  l_count pls_integer;
begin
  select count(*) into l_count
    from dba_objects
   where owner = 'OTP' and object_name in ('FACT_FLIGHT', 'PKG_MART');
  if l_count < 2 then
    raise_application_error(-20100,
      'Schema OTP has no star schema yet. Install aviation-otp-observatory (phase 2.2 or later) first.');
  end if;

  select count(*) into l_count from dba_users where username = 'OTP_APP';
  if l_count = 0 then
    execute immediate 'create user otp_app identified by "&app_password" '
                   || 'default tablespace users quota 50m on users';
    dbms_output.put_line('User OTP_APP created.');
  else
    dbms_output.put_line('User OTP_APP already exists.');
  end if;
end;
/

grant create session, create view, create procedure, create synonym to otp_app;

-- Read access to the observatory, table by table (granted directly, not through a
-- role, because views and definer-rights packages ignore privileges from roles).
grant select on otp.fact_flight     to otp_app;
grant select on otp.dim_date        to otp_app;
grant select on otp.dim_hour        to otp_app;
grant select on otp.dim_airline     to otp_app;
grant select on otp.dim_airport     to otp_app;
grant select on otp.core_load_run   to otp_app;
grant select on otp.core_vra_reject to otp_app;

-- The only action the app may run on the observatory: rebuilding the star schema.
grant execute on otp.pkg_mart to otp_app;

prompt ==> Schema OTP_APP ready.
exit
