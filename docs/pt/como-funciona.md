# Como funciona

Este documento explica, ficheiro a ficheiro, o que o projeto faz e porquê. Para instalar, ver o [guia de instalação](guia-instalacao.md); para construir as páginas, o [guia das páginas](guia-paginas-apex.md); para a visão geral em inglês, [architecture.md](../architecture.md).

## A ideia

O [Observatório](https://github.com/Jano-Projects/aviation-otp-observatory) carrega os voos da ANAC para um esquema em estrela no Oracle. Este projeto põe uma aplicação web e uma API REST à frente desses dados, sem mexer no esquema do Observatório:

```
Browser ──> ORDS (contentor otp-ords) ──> esquema OTP_APP ──> esquema OTP (Observatório)
              serve o APEX e a API         views, package,      tabelas e PL/SQL
                                           API REST, app 100
```

## Os ficheiros

| Ficheiro | O que faz |
|---|---|
| `apex.py` | O comando do projeto, só com a biblioteca padrão do Python. `up` instala o APEX e o ORDS (na primeira vez) e liga o contentor; `install` cria a camada da aplicação; `check`, `refresh`, `urls`, `sql`, `logs`, `down`. |
| `docker-compose.yml` | O contentor `otp-ords`: imagem `database/ords:24.4.0` usada como Java 17, a correr o ORDS 26.3.1 de `.cache/ords`; porta `127.0.0.1:8181` para `8080`; volume com a configuração do ORDS; ficheiros visuais do APEX montados de `.cache/apex/images`; rede do Observatório. |
| `.env.example` | Modelo das palavras-passe e opções. O `apex.py` copia-o para `.env` (que nunca vai para o Git). |
| `db/admin/create_app_schema.sql` | Cria o esquema `OTP_APP` e dá-lhe só o necessário: `SELECT` em 7 tabelas do `OTP` e `EXECUTE` no `pkg_mart`. |
| `db/admin/create_apex_workspace.sql` | Cria o espaço de trabalho APEX `OTP` (ligado ao `OTP_APP`) e o utilizador de desenvolvimento. |
| `db/admin/check_invalid.sql` | Recompila o esquema e falha se ficar algum objeto inválido. |
| `db/app/views.sql` | As 8 views de indicadores, com medidas aditivas (somas), por mês e tipo de linha. |
| `db/app/pkg_app_api.*` | `to_month` (valida `YYYY-MM`) e `refresh_mart` (reconstrói o esquema estrela e faz `COMMIT`). |
| `db/rest/otp_api_v1.sql` | A API REST: seis `GET` e um `POST`, declarados com `ords.define_module/template/handler`. |
| `apex/f100.sql` | A aplicação APEX exportada (páginas, regiões, filtros). |
| `.cache/` | Ficheiros descarregados pelo `up` (APEX e ORDS), fora do Git. |

## Porquê estas versões

Resumo; o detalhe está em [architecture.md](../architecture.md#versions).

- A base é a **Oracle AI Database 26ai** (23.26), a versão que a imagem do Observatório traz hoje.
- O **ORDS 24.4** não instala na 26ai: procura um produto chamado `Oracle Database%` e a 26ai chama-se `Oracle AI Database` (`ORA-01403`). Por isso corre o **ORDS 26.3.1**, a partir do ZIP oficial.
- As imagens novas do ORDS exigem um processador com **AVX2**, que as VMs do VirtualBox muitas vezes não têm. A imagem **24.4.0** não exige e traz o Java 17 de que o ORDS 26.3.1 precisa; por isso fica, só como ambiente Java.
- O **APEX 24.2** é instalado com o script oficial `apexins.sql`, porque a imagem que o fazia sozinha passou a exigir login no registo da Oracle.

## Regras de desenho

- **Privilégio mínimo entre projetos:** o `OTP_APP` lê, não escreve, e só pode executar uma ação do Observatório.
- **Medidas aditivas:** soma-se primeiro, divide-se depois; nunca média de percentagens.
- **Bind variables e validação:** os filtros chegam ao SQL como variáveis e o mês é validado; não há SQL injection.
- **Quem faz commit:** no Observatório, quem chama; aqui, o pedido HTTP, por isso o `pkg_app_api` faz `COMMIT`.
- **Estado real antes de agir:** o `up` e o `install` verificam o que já existe; podem ser repetidos.
- **A aplicação vive no Git:** exporta-se para `apex/f100.sql`; o `install` só a importa se ainda não existir (ou com `--replace-app`).
