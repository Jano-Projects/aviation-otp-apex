# Guia de instalação (Debian 13)

Este guia põe a aplicação web no ar na tua máquina, em blocos: copia o bloco, cola no terminal (Ctrl+Shift+V) e confere o que **deve ver**.

Pré-requisito: o [Observatório](https://github.com/Jano-Projects/aviation-otp-observatory) a funcionar, com a fase 2.2 (esquema estrela) carregada.

---

## Bloco 1. Conferir o Observatório

```bash
cd ~/projetos/aviation-otp-observatory
python3 tasks.py up
python3 tasks.py status
docker network ls | grep otp-observatory
```

**Deve ver:** a base `healthy`, os meses carregados com o número de factos (`FACT_FLIGHT`) e uma linha `otp-observatory_default`. É por essa rede que o contentor do ORDS vai chegar à base.

Se `FACT_FLIGHT` estiver vazia: `python3 tasks.py mart`.

## Bloco 2. Memória e disco

```bash
free -h
df -h /
```

**Deve ver:** pelo menos 1,5 GB em `available` na memória e 5 GB livres no disco. Se a memória estiver curta, desliga a VM e aumenta a RAM no VirtualBox (Definições > Sistema), 6 GB ou mais é o confortável.

## Bloco 3. Criar o repositório vazio no GitHub

```bash
gh repo create Jano-Projects/aviation-otp-apex --public \
  --description "Local web app and REST API for the Aviation OTP Observatory (Oracle APEX + ORDS)"
```

**Deve ver:** `✓ Created repository Jano-Projects/aviation-otp-apex on GitHub`.

## Bloco 4. Descompactar e publicar

Assumindo que o zip está em `~/Downloads`:

```bash
cd ~/projetos
unzip ~/Downloads/aviation-otp-apex.zip
cd aviation-otp-apex
git init -b main
git add .
git commit -m "ORDS + APEX container, OTP_APP schema, indicator views, REST API v1"
git remote add origin https://github.com/Jano-Projects/aviation-otp-apex.git
git push -u origin main
```

**Deve ver:** o push terminar com `main -> main`.

## Bloco 5. Subir o ORDS (primeira vez: 15 a 30 minutos)

```bash
python3 apex.py up
```

**Deve ver:** primeiro o download da imagem do ORDS (cerca de 1 GB), depois linhas `...` a cada 15 segundos enquanto o ORDS instala o próprio ORDS e o APEX dentro da base. Termina com `ORDS is ready: http://localhost:8181/ords/`.

O que está a acontecer: o `apex.py` grava a ligação à base (`CONN_STRING`) num ficheiro em `.secrets/`, o contentor lê esse ficheiro, instala tudo e apaga-o. Nas vezes seguintes o `up` demora segundos, porque a configuração fica guardada no volume `otp-apex_ords_config`.

Para acompanhar a instalação noutro terminal:

```bash
cd ~/projetos/aviation-otp-apex && python3 apex.py logs
```

## Bloco 6. Instalar a camada da aplicação

```bash
python3 apex.py install
```

**Deve ver**, por esta ordem:

- o esquema `OTP_APP` criado (ou já existente) com as permissões sobre o `OTP`;
- o espaço de trabalho APEX `OTP` e o utilizador `DEV`;
- as views, o `pkg_app_api` e `No invalid objects`;
- `REST module otp.api.v1 published at /ords/otp/api/v1/`;
- por fim, o aviso de que ainda não há `apex/f<id>.sql` (normal: as páginas ainda vão ser construídas).

O comando pode ser repetido sem problema: tudo é `create or replace` ou verifica se já existe.

## Bloco 7. Testar a API REST

```bash
python3 apex.py check
curl -s "http://localhost:8181/ords/otp/api/v1/airlines?line_type=N" | python3 -m json.tool | head -25
```

**Deve ver:** a tabela de meses (voos, % pontualidade, % cancelados) e, no `curl`, um JSON com `"items": [...]` das companhias em voos domésticos.

## Bloco 8. Testar a ação (reconstruir um mês)

```bash
python3 apex.py refresh --month 2026-07
```

**Deve ver:** `HTTP 200: {"months_refreshed":1}`. No Observatório, `python3 tasks.py status` mostra uma nova execução `MART` no registo de cargas.

## Bloco 9. Abrir o APEX

```bash
python3 apex.py urls
```

Abre no Firefox da VM o endereço `http://localhost:8181/ords/`, escolhe **Oracle APEX** e entra com:

| Campo | Valor |
|---|---|
| Workspace | `OTP` |
| Username | `DEV` |
| Password | a de `APEX_DEV_PASSWORD` no `.env` |

**Deve ver:** a página inicial do APEX com App Builder, SQL Workshop e outros. A partir daqui segue o [guia das páginas](guia-paginas-apex.md).

---

## Dia a dia

| Quero | Comando |
|---|---|
| Ligar tudo | `python3 tasks.py up` (no Observatório), depois `python3 apex.py up` |
| Desligar | `python3 apex.py down`, depois `python3 tasks.py down` |
| Consola SQL como OTP_APP | `python3 apex.py sql` |
| Ver os endereços | `python3 apex.py urls` |

A ordem importa: o ORDS precisa da base ligada e da rede do Observatório.

## Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `network otp-observatory_default not found` | O Observatório não está ligado. `python3 tasks.py up` no outro repositório. |
| `up` fica muito tempo em `...` | Normal na primeira vez (até 30 min). Vê o progresso com `python3 apex.py logs`. |
| `ORA-20100` no install | O esquema estrela não existe. No Observatório: `python3 tasks.py install` e `python3 tasks.py mart`. |
| `ORA-20101` no install | O APEX não ficou instalado. Vê `python3 apex.py logs`; se a instalação falhou, `python3 apex.py down`, `docker volume rm otp-apex_ords_config` e repete o bloco 5. |
| Página `404` em `/ords/otp/...` | O módulo REST não foi publicado. Repete o bloco 6. |
| A VM fica lenta | Pouca RAM. Aumenta a memória da VM ou desliga outras aplicações. |
