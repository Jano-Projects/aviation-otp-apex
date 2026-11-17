# APEX application export

`f100.sql` is the exported Oracle APEX application: ID 100, alias `OBSERVATORIO`, workspace `OTP`, parsing schema `OTP_APP`, exported from APEX 24.2.

| Page | Name | Status |
|---|---|---|
| 0 | Global Page: filters (month from, month to, line type) | ✅ |
| 1 | Painel: key figures, on-time % by month, flights and cancellations by month | ✅ |
| 2 | Companhias: on-time % of the 15 busiest airlines, interactive report of all airlines | ✅ |
| 3 | Aeroportos: map of origin airports, interactive report of all airports | ✅ |
| 5 | Horários: on-time % by hour of scheduled departure and by day of the week | ✅ |
| 9999 | Login | ✅ |

There is no page 4, and no pages for routes, load history or rebuilding the star schema. Load history and the rebuild are available through the REST API (`GET /runs`, `POST /mart/refresh`).

- **Open:** `http://localhost:8181/ords/r/otp/observatorio/home` (sign in with the APEX developer account from `.env`).
- **Import:** `python3 apex.py install` imports it **only when the application does not exist yet** in workspace `OTP`, so it never overwrites pages built in App Builder. To replace the installed application with this file on purpose: `python3 apex.py install --replace-app`.
- **Export after changing pages:** App Builder > application 100 > Export / Import > Export (format SQL), move the file here, commit and push. Do this before switching machines.

How each page is built, region by region: [docs/pt/guia-paginas-apex.md](../docs/pt/guia-paginas-apex.md).
