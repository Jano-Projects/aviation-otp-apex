--------------------------------------------------------------------------------
-- Creates the APEX workspace OTP on schema OTP_APP and its developer account
-- (idempotent). Run as SYS in FREEPDB1, after ORDS has installed APEX.
-- Substitution variables: dev_user, dev_password.
--------------------------------------------------------------------------------
whenever sqlerror exit failure rollback
set verify off feedback off serveroutput on

declare
  l_count pls_integer;
begin
  select count(*) into l_count
    from dba_registry
   where comp_id = 'APEX' and status = 'VALID';
  if l_count = 0 then
    raise_application_error(-20101,
      'APEX is not installed (yet). Run "python apex.py up" and wait until it reports ORDS ready.');
  end if;

  select count(*) into l_count from apex_workspaces where workspace = 'OTP';
  if l_count = 0 then
    apex_instance_admin.add_workspace(
      p_workspace      => 'OTP',
      p_primary_schema => 'OTP_APP');
    dbms_output.put_line('Workspace OTP created.');
  else
    dbms_output.put_line('Workspace OTP already exists.');
  end if;

  apex_util.set_workspace(p_workspace => 'OTP');

  select count(*) into l_count
    from apex_workspace_apex_users
   where workspace_name = 'OTP' and user_name = upper('&dev_user');
  if l_count = 0 then
    apex_util.create_user(
      p_user_name                    => upper('&dev_user'),
      p_web_password                 => '&dev_password',
      p_email_address                => lower('&dev_user') || '@localhost',
      p_developer_privs              => 'ADMIN:CREATE:DATA_LOADER:EDIT:HELP:MONITOR:SQL',
      p_change_password_on_first_use => 'N');
    dbms_output.put_line('Developer ' || upper('&dev_user') || ' created.');
  else
    dbms_output.put_line('Developer ' || upper('&dev_user') || ' already exists.');
  end if;

  commit;
end;
/

exit
