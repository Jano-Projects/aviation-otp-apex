# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `python apex.py up`: downloads Oracle APEX 24.2 (checksum-verified), installs it with
  `apexins.sql`, installs ORDS with `ords install` (PL/SQL gateway for APEX) and starts the ORDS
  container on the observatory's Docker network. Each step checks the real state, so an
  interrupted first start resumes.
- Schema `OTP_APP` with read grants on the observatory's star schema and `EXECUTE` on `pkg_mart`.
- Indicator views with additive measures; `pkg_app_api` (`to_month`, `refresh_mart`).
- REST API `/ords/otp/api/v1/`: months, airlines, airports, hours, weekdays, runs, `POST mart/refresh`.
- APEX workspace `OTP` with a developer account; import of `apex/f*.sql` on install.
- Guides in Portuguese: installation, and building the APEX pages region by region.

### Fixed
- ORDS image pinned to `24.4.0`: newer images need an x86-64-v3 CPU (AVX2), which many
  VirtualBox VMs do not expose (`Fatal glibc error: CPU does not support x86-64-v3`).
- `apex.py up` detects an interrupted first start (configuration volume left empty) and passes
  the database connection again, instead of waiting forever; progress shows elapsed minutes.
- Fedora and other SELinux hosts: folders shared with the container are mounted with the `z` label.
- The plain `database/ords` image does not read `conn_string.txt` nor install anything (it
  starts empty on port 8080); the image that did (`ords-developer`) now requires a registry
  login. The `conn_string.txt` mechanism was replaced by the explicit install above, and the
  host port maps to 8080.
