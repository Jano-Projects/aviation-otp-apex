# APEX application export

This folder holds the exported Oracle APEX application (`f100.sql`, application ID 100, alias `OBSERVATORIO`).

- **Import:** `python3 apex.py install` imports any `f*.sql` found here into workspace `OTP`, parsing schema `OTP_APP`. Re-importing replaces the application with the same ID.
- **Export after changing pages:** App Builder > application 100 > Export / Import > Export (format SQL), then move the file here and commit it.
- **Open:** `http://localhost:8181/ords/r/otp/observatorio/home`

Until the first export is committed this folder only contains this file. Building the pages is described step by step in [docs/pt/guia-paginas-apex.md](../docs/pt/guia-paginas-apex.md).
