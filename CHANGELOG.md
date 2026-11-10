# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- ORDS + APEX container on the observatory's Docker network, started by `python apex.py up`.
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
- Fedora and other SELinux hosts: `.secrets` is mounted with the `z` label.
