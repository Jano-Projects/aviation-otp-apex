#!/usr/bin/env python3
"""Commands for the APEX web app of the Aviation OTP Observatory.

Needs the database of aviation-otp-observatory running (python tasks.py up there).

    python apex.py up        start ORDS; the first time it installs ORDS and APEX (15-30 min)
    python apex.py install   schema OTP_APP, views, API package, REST API, APEX workspace
    python apex.py check     call the REST API and print what it returns
    python apex.py refresh   rebuild the star schema through the REST API (POST)
    python apex.py urls      print the addresses to open in the browser
    python apex.py sql       interactive SQL*Plus session as OTP_APP
    python apex.py logs      follow the ORDS container log
    python apex.py down      stop ORDS (APEX stays installed in the database)

Run "python apex.py <command> --help" for options.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
SECRETS_DIR = ROOT / ".secrets"
NETWORK = "otp-observatory_default"
CONFIG_VOLUME = "otp-apex_ords_config"
APEX_DIR = ROOT / "apex"


def app_export() -> Path | None:
    """The exported APEX application (apex/f<id>.sql), if it has been exported yet."""
    exports = sorted(APEX_DIR.glob("f[0-9]*.sql"))
    return exports[0] if exports else None


# --------------------------------------------------------------------------- helpers
def info(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def fail(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


def env() -> dict[str, str]:
    if not ENV_FILE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        print(f"Created {ENV_FILE.name} from {ENV_EXAMPLE.name} (edit it to change passwords).")
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, **kwargs)


def check(result: subprocess.CompletedProcess, what: str) -> None:
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        fail(f"{what} failed (exit code {result.returncode}).")


def base_url(cfg: dict[str, str]) -> str:
    return f"http://localhost:{cfg.get('ORDS_PORT', '8181')}/ords"


def require_database(cfg: dict[str, str]) -> None:
    if shutil.which("docker") is None:
        fail("Docker not found.")
    container = cfg.get("DB_CONTAINER", "otp-oracle")
    result = run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
                 capture_output=True, text=True)
    if result.returncode != 0 or result.stdout.strip() != "healthy":
        fail(f"The observatory database ({container}) is not running. "
             "In the aviation-otp-observatory folder run: python tasks.py up")
    if run(["docker", "network", "inspect", NETWORK], capture_output=True).returncode != 0:
        fail(f"Docker network {NETWORK} not found: start aviation-otp-observatory first.")


def sqlplus(cfg: dict[str, str], logon: str, script: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Runs SQL*Plus inside the observatory's database container, script through stdin."""
    cmd = ["docker", "exec", "-i", "-w", "/tmp", cfg.get("DB_CONTAINER", "otp-oracle"),
           "sqlplus", "-s", "-L", logon]
    return run(cmd, input=script, text=True, encoding="utf-8", errors="replace", capture_output=capture)


def sys_logon(cfg: dict[str, str]) -> str:
    return f'sys/"{cfg["ORACLE_PASSWORD"]}"@//localhost:1521/FREEPDB1 as sysdba'


def app_logon(cfg: dict[str, str]) -> str:
    return f'otp_app/"{cfg["OTP_APP_PASSWORD"]}"@//localhost:1521/FREEPDB1'


def script(*files: str, defines: dict[str, str] | None = None) -> str:
    """Concatenates SQL files into one script for stdin (no @ includes needed)."""
    head = "".join(f'define {k} = "{v}"\n' for k, v in (defines or {}).items())
    body = "\n".join((ROOT / f).read_text(encoding="utf-8") for f in files)
    return head + body + "\nexit\n"


def http(method: str, url: str, timeout: int = 600) -> tuple[int, str]:
    request = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def ords_answers(cfg: dict[str, str]) -> bool:
    try:
        status, _ = http("GET", base_url(cfg) + "/", timeout=10)
        return status < 500
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def ords_configured(cfg: dict[str, str]) -> bool:
    """True when the config volume already holds a database pool (ORDS was installed before)."""
    if run(["docker", "volume", "inspect", CONFIG_VOLUME], capture_output=True).returncode != 0:
        return False
    image = cfg.get("ORDS_IMAGE", "container-registry.oracle.com/database/ords:24.4.0")
    probe = ["docker", "run", "--rm", "-v", f"{CONFIG_VOLUME}:/etc/ords/config",
             "--entrypoint", "test", image, "-f", "/etc/ords/config/databases/default/pool.xml"]
    return run(probe, capture_output=True).returncode == 0


# --------------------------------------------------------------------------- commands
def cmd_up(args: argparse.Namespace) -> None:
    cfg = env()
    require_database(cfg)

    # Not "does the volume exist": an interrupted first start leaves the volume behind
    # without any configuration, and ORDS would then wait forever for a connection.
    first_time = not ords_configured(cfg)
    if first_time:
        # ORDS reads the connection once, installs ORDS and APEX, then deletes the file.
        SECRETS_DIR.mkdir(exist_ok=True)
        os.chmod(SECRETS_DIR, 0o777)  # the container user must be able to delete the file
        conn = SECRETS_DIR / "conn_string.txt"
        conn.write_text(f"CONN_STRING=sys/{cfg['ORACLE_PASSWORD']}@oracle:1521/FREEPDB1\n", encoding="utf-8")
        os.chmod(conn, 0o666)
        info("Starting ORDS. First start: it installs ORDS and APEX into the database (15-30 minutes)")
        print("   Follow the installation in another terminal with: python apex.py logs")
    else:
        SECRETS_DIR.mkdir(exist_ok=True)
        info("Starting ORDS")

    check(run(["docker", "compose", "up", "-d"]), "docker compose up")

    started = time.monotonic()
    deadline = started + args.timeout
    hinted = False
    while time.monotonic() < deadline:
        if ords_answers(cfg):
            leftover = SECRETS_DIR / "conn_string.txt"
            if leftover.exists():
                leftover.unlink()
            info(f"ORDS is ready: {base_url(cfg)}/")
            return
        time.sleep(15)
        minutes = int((time.monotonic() - started) // 60)
        print(f"   ... {minutes} min", flush=True)
        if not first_time and minutes >= 3 and not hinted:
            hinted = True
            print("   ORDS should start in seconds once installed. See why with: python apex.py logs")
    fail(f"ORDS did not answer after {args.timeout}s. See: python apex.py logs")


def cmd_install(args: argparse.Namespace) -> None:
    cfg = env()
    require_database(cfg)
    if not ords_answers(cfg):
        fail("ORDS is not running yet. Run: python apex.py up")

    info("Creating schema OTP_APP and its grants")
    check(sqlplus(cfg, sys_logon(cfg), script("db/admin/create_app_schema.sql",
                                              defines={"app_password": cfg["OTP_APP_PASSWORD"]})),
          "Creating OTP_APP")

    info("Creating the APEX workspace OTP")
    check(sqlplus(cfg, sys_logon(cfg), script("db/admin/create_apex_workspace.sql",
                                              defines={"dev_user": cfg.get("APEX_DEV_USER", "DEV"),
                                                       "dev_password": cfg["APEX_DEV_PASSWORD"]})),
          "Creating the APEX workspace")

    info("Installing views and the API package")
    check(sqlplus(cfg, app_logon(cfg),
                  "whenever sqlerror exit failure rollback\nset define off feedback on\n"
                  + script("db/app/views.sql", "db/app/pkg_app_api.pks", "db/app/pkg_app_api.pkb",
                           "db/admin/check_invalid.sql")),
          "Installing the application layer")

    info("Publishing the REST API")
    check(sqlplus(cfg, app_logon(cfg), script("db/rest/otp_api_v1.sql")), "Publishing the REST API")

    export = app_export()
    if export:
        info(f"Importing the APEX application from {export.relative_to(ROOT)}")
        head = ("whenever sqlerror exit failure rollback\n"
                "begin\n"
                "  apex_application_install.set_workspace('OTP');\n"
                "  apex_application_install.set_schema('OTP_APP');\n"
                "end;\n/\n")
        check(sqlplus(cfg, app_logon(cfg), head + script(str(export.relative_to(ROOT)))),
              "Importing the APEX application")
    else:
        print("\n   No apex/f<id>.sql yet: build the pages in App Builder (docs/pt/guia-paginas-apex.md).")

    cmd_urls(args)


def cmd_check(args: argparse.Namespace) -> None:
    cfg = env()
    api = base_url(cfg) + "/otp/api/v1"
    info(f"GET {api}/months")
    status, body = http("GET", f"{api}/months")
    if status != 200:
        fail(f"HTTP {status}: {body[:300]}")
    items = json.loads(body).get("items", [])
    print(f"   {'month':<8} {'flights':>9} {'on-time %':>10} {'cancelled %':>12}")
    for row in items:
        print(f"   {row['month_label']:<8} {row['flights']:>9,} {row['on_time_pct']!s:>10} {row['cancelled_pct']!s:>12}")

    info(f"GET {api}/airlines?line_type=N  (top 5 domestic airlines)")
    status, body = http("GET", f"{api}/airlines?line_type=N")
    if status != 200:
        fail(f"HTTP {status}: {body[:300]}")
    for row in json.loads(body).get("items", [])[:5]:
        print(f"   {row['airline_icao']}  {row['airline_name'][:40]:<40} {row['flights']:>9,}  on time {row['on_time_pct']}%")


def cmd_refresh(args: argparse.Namespace) -> None:
    cfg = env()
    url = base_url(cfg) + "/otp/api/v1/mart/refresh" + (f"?month={args.month}" if args.month else "")
    info(f"POST {url}")
    status, body = http("POST", url)
    print(f"   HTTP {status}: {body.strip()[:300]}")
    if status != 200:
        sys.exit(1)


def cmd_urls(args: argparse.Namespace) -> None:
    cfg = env()
    base = base_url(cfg)
    info("Open in the browser")
    print(f"   APEX: {base}/  -> Oracle APEX -> workspace OTP, user {cfg.get('APEX_DEV_USER', 'DEV')}")
    print(f"   REST API (months): {base}/otp/api/v1/months")
    print(f"   The application, once built: {base}/r/otp/observatorio")


def cmd_sql(args: argparse.Namespace) -> None:
    cfg = env()
    sys.exit(run(["docker", "exec", "-it", cfg.get("DB_CONTAINER", "otp-oracle"),
                  "sqlplus", "-L", app_logon(cfg)]).returncode)


def cmd_logs(args: argparse.Namespace) -> None:
    sys.exit(run(["docker", "logs", "-f", "--tail", "100", "otp-ords"]).returncode)


def cmd_down(args: argparse.Namespace) -> None:
    check(run(["docker", "compose", "down"]), "docker compose down")


# --------------------------------------------------------------------------- CLI
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("up", help="start ORDS (first time: install ORDS and APEX)")
    p.add_argument("--timeout", type=int, default=3600, help="seconds to wait for ORDS (default 3600)")
    p.set_defaults(func=cmd_up)

    sub.add_parser("install", help="schema OTP_APP, views, API, REST, APEX workspace").set_defaults(func=cmd_install)
    sub.add_parser("check", help="call the REST API").set_defaults(func=cmd_check)

    p = sub.add_parser("refresh", help="rebuild the star schema through the REST API")
    p.add_argument("--month", help="YYYY-MM (default: every month)")
    p.set_defaults(func=cmd_refresh)

    sub.add_parser("urls", help="addresses to open in the browser").set_defaults(func=cmd_urls)
    sub.add_parser("sql", help="interactive SQL*Plus as OTP_APP").set_defaults(func=cmd_sql)
    sub.add_parser("logs", help="follow the ORDS log").set_defaults(func=cmd_logs)
    sub.add_parser("down", help="stop ORDS").set_defaults(func=cmd_down)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
