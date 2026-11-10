#!/usr/bin/env python3
"""Commands for the APEX web app of the Aviation OTP Observatory.

Needs the database of aviation-otp-observatory running (python tasks.py up there).

    python apex.py up        start ORDS; the first time it installs APEX and ORDS (20-30 min)
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
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
CACHE_DIR = ROOT / ".cache"
NETWORK = "otp-observatory_default"
CONFIG_VOLUME = "otp-apex_ords_config"
APEX_DIR = ROOT / "apex"

# Oracle APEX 24.2, English only (public download, Oracle Free Use Terms).
# Pinned with its checksum, like the ORDS image: the same version on every machine.
APEX_ZIP_URL = "https://download.oracle.com/otn_software/apex/apex_24.2_en.zip"
APEX_ZIP_SHA256 = "94e6a624cfe80272041094543c6ccd56b87333d8ad856100802a1cb0f91cd42d"
APEX_ZIP = CACHE_DIR / "apex_24.2_en.zip"
APEX_FILES = CACHE_DIR / "apex"          # unzipped; images/ is served by ORDS as /i/

# ORDS 26.3.1, run from Oracle's zip. ORDS 24.4 (the one inside the container image)
# cannot install into Oracle AI Database 26ai: its first check looks for a product
# named 'Oracle Database%' in PRODUCT_COMPONENT_VERSION, and 26ai calls itself
# 'Oracle AI Database', so the check fails with ORA-01403. The image is kept only as
# a Java 17 runtime that works without AVX2; ORDS 26.3 supports Java 17, 21 and 25.
ORDS_VERSION = "26.3.1.303.1615"
ORDS_ZIP_URL = f"https://download.oracle.com/otn_software/java/ords/ords-{ORDS_VERSION}.zip"
ORDS_ZIP = CACHE_DIR / f"ords-{ORDS_VERSION}.zip"
ORDS_FILES = CACHE_DIR / "ords"          # mounted in the container as /opt/ords-app
ORDS_CMD = "bash /opt/ords-app/bin/ords --config /etc/ords/config"


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


def sql_value(cfg: dict[str, str], query: str) -> str:
    """Runs one query as SYS and returns its single value as text."""
    result = sqlplus(cfg, sys_logon(cfg),
                     "set heading off feedback off pagesize 0 verify off\n" + query + ";\nexit\n",
                     capture=True)
    check(result, "Query")
    return result.stdout.strip()


def apex_installed(cfg: dict[str, str]) -> bool:
    return sql_value(cfg, "select count(*) from dba_registry "
                          "where comp_id = 'APEX' and status = 'VALID'") == "1"


def ensure_apex_files() -> None:
    """Downloads (once) and unzips the APEX installation files into .cache/apex."""
    if (APEX_FILES / "apexins.sql").exists() and (APEX_FILES / "images").is_dir():
        return
    CACHE_DIR.mkdir(exist_ok=True)
    if not APEX_ZIP.exists():
        info(f"Downloading Oracle APEX 24.2 (about 200 MB): {APEX_ZIP_URL}")
        partial = APEX_ZIP.with_suffix(".part")
        with urllib.request.urlopen(APEX_ZIP_URL, timeout=120) as response, open(partial, "wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        partial.rename(APEX_ZIP)
    digest = hashlib.sha256()
    with open(APEX_ZIP, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != APEX_ZIP_SHA256:
        APEX_ZIP.unlink()
        fail("The APEX download is corrupted (checksum mismatch). Run the command again.")
    info("Unzipping APEX")
    with zipfile.ZipFile(APEX_ZIP) as archive:
        archive.extractall(CACHE_DIR)      # creates .cache/apex/


def download(url: str, target: Path, what: str) -> None:
    info(f"Downloading {what}: {url}")
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)
    partial.rename(target)


def ensure_ords_files() -> None:
    """Downloads (once) and unzips ORDS into .cache/ords; a version marker detects upgrades."""
    marker = ORDS_FILES / ".version"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == ORDS_VERSION:
        return
    CACHE_DIR.mkdir(exist_ok=True)
    if not ORDS_ZIP.exists():
        download(ORDS_ZIP_URL, ORDS_ZIP, f"ORDS {ORDS_VERSION} (about 100 MB)")
    info(f"Unzipping ORDS {ORDS_VERSION}")
    if ORDS_FILES.exists():
        shutil.rmtree(ORDS_FILES)
    try:
        with zipfile.ZipFile(ORDS_ZIP) as archive:
            archive.extractall(ORDS_FILES)
    except zipfile.BadZipFile:
        ORDS_ZIP.unlink()
        fail("The ORDS download is corrupted. Run the command again.")
    if not (ORDS_FILES / "bin" / "ords").exists():
        fail(f"Unexpected ORDS zip layout: {ORDS_FILES}/bin/ords not found.")
    marker.write_text(ORDS_VERSION + "\n", encoding="utf-8")


def install_apex(cfg: dict[str, str]) -> None:
    """Installs APEX into FREEPDB1 with Oracle's own script, apexins.sql (10-20 minutes)."""
    db = cfg.get("DB_CONTAINER", "otp-oracle")
    info("Installing Oracle APEX 24.2 into the database (10-20 minutes, no output until the end)")
    run(["docker", "exec", "-u", "root", db, "rm", "-rf", "/tmp/apex"])
    check(run(["docker", "cp", str(APEX_FILES), f"{db}:/tmp/apex"]), "Copying the APEX files")
    # apexins.sql writes its log next to itself: the database user must be able to write there.
    check(run(["docker", "exec", "-u", "root", db, "chmod", "-R", "a+rwX", "/tmp/apex"]),
          "Preparing the APEX files")
    started = time.monotonic()
    log_file = CACHE_DIR / "apexins.log"
    with open(log_file, "w", encoding="utf-8") as log:
        process = subprocess.Popen(
            ["docker", "exec", "-i", "-w", "/tmp/apex", db, "sqlplus", "-s", "-L", sys_logon(cfg)],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        process.stdin.write("@apexins.sql SYSAUX SYSAUX TEMP /i/\nexit\n")
        process.stdin.close()
        while process.poll() is None:
            time.sleep(30)
            print(f"   ... {int((time.monotonic() - started) // 60)} min "
                  f"(log: .cache/apexins.log)", flush=True)
    run(["docker", "exec", "-u", "root", db, "rm", "-rf", "/tmp/apex"])
    if not apex_installed(cfg):
        print("".join(log_file.read_text(encoding="utf-8", errors="replace").splitlines(True)[-40:]))
        fail("APEX was not installed. The end of .cache/apexins.log is above.")
    # ORDS runs APEX pages as APEX_PUBLIC_USER, through a proxy connection.
    check(sqlplus(cfg, sys_logon(cfg), "alter user apex_public_user account unlock;\nexit\n", capture=True),
          "Unlocking APEX_PUBLIC_USER")
    print(f"   APEX installed in {int((time.monotonic() - started) // 60)} min.")


def install_ords(cfg: dict[str, str]) -> None:
    """Installs ORDS into the database and writes its configuration into the volume."""
    info("Installing ORDS into the database and configuring it (2-5 minutes)")
    # With APEX installed and APEX_PUBLIC_USER present, "ords install" configures the
    # PL/SQL gateway for APEX by itself (proxied mode), so no gateway options are given.
    command = (
        f"{ORDS_CMD} install --admin-user SYS --proxy-user "
        "--db-hostname oracle --db-port 1521 --db-servicename FREEPDB1 "
        "--feature-sdw true --password-stdin "
        f"&& {ORDS_CMD} config set standalone.static.path /opt/oracle/apex/images"
    )
    passwords = f"{cfg['ORACLE_PASSWORD']}\n{cfg.get('ORDS_PUBLIC_PASSWORD', 'Ords_Public_2026')}\n"
    check(run(["docker", "compose", "run", "--rm", "--no-deps", "-T", "--entrypoint", "bash",
               "ords", "-c", command], input=passwords, text=True),
          "Installing ORDS")


# --------------------------------------------------------------------------- commands
def cmd_up(args: argparse.Namespace) -> None:
    cfg = env()
    require_database(cfg)

    # A folder created by Docker (a bind mount of a path that did not exist yet)
    # belongs to root, and nothing can be downloaded into it afterwards.
    if CACHE_DIR.exists() and not os.access(CACHE_DIR, os.W_OK):
        fail(f"{CACHE_DIR} is not writable (probably created by Docker as root). "
             f"Fix with: sudo chown -R $USER:$USER {CACHE_DIR}")

    # Each step checks the real state, so an interrupted first start simply resumes.
    ensure_apex_files()
    ensure_ords_files()
    if not apex_installed(cfg):
        install_apex(cfg)
    if not ords_configured(cfg):
        install_ords(cfg)

    info("Starting ORDS")
    check(run(["docker", "compose", "up", "-d"]), "docker compose up")

    started = time.monotonic()
    deadline = started + args.timeout
    while time.monotonic() < deadline:
        if ords_answers(cfg):
            info(f"ORDS is ready: {base_url(cfg)}/")
            return
        time.sleep(10)
        print(f"   ... {int((time.monotonic() - started) // 60)} min", flush=True)
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

    p = sub.add_parser("up", help="start ORDS (first time: install APEX and ORDS)")
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
