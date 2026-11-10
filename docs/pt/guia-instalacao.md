# Guia de instalação (Debian 13 ou Fedora)

Este guia põe a aplicação web no ar na tua máquina, em blocos: copia o bloco, cola no terminal (Ctrl+Shift+V) e confere o que **deve ver**.

Pré-requisito: o [Observatório](https://github.com/Jano-Projects/aviation-otp-observatory) a funcionar, com a fase 2.2 (esquema estrela) carregada.

---

## Bloco 1. Conferir o Observatório

```bash
cd ~/projetos/aviation-otp-observatory
source .venv/bin/activate
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

## Bloco 3. Obter o projeto

```bash
cd ~/projetos
git clone https://github.com/Jano-Projects/aviation-otp-apex.git
cd aviation-otp-apex
```

**Deve ver:** `ls` mostra `apex.py`, `db`, `docs`, `docker-compose.yml`, `README.md`...

Não é preciso ambiente Python próprio: o `apex.py` só usa a biblioteca padrão do Python.

## Bloco 4. Subir o ORDS (primeira vez: 15 a 30 minutos)

```bash
python3 apex.py up
```

**Deve ver:** primeiro o download da imagem do ORDS (cerca de 1 GB), depois a mensagem `First start: it installs ORDS and APEX...` e uma linha `... N min` a cada 15 segundos, enquanto o ORDS instala o próprio ORDS e o APEX dentro da base. Termina com `ORDS is ready: http://localhost:8181/ords/`.

Confirma noutro terminal que a imagem é a fixada no projeto e que não há erros:

```bash
docker inspect --format '{{.Config.Image}}' otp-ords
docker logs --tail 10 otp-ords
```

A imagem tem de terminar em `ords:24.4.0` (ver *Porquê a versão 24.4.0* abaixo).

O que está a acontecer: o `apex.py` grava a ligação à base (`CONN_STRING`) num ficheiro em `.secrets/`, o contentor lê esse ficheiro, instala tudo e apaga-o. Nas vezes seguintes o `up` demora segundos, porque a configuração fica guardada no volume `otp-apex_ords_config`.

**Porquê a versão 24.4.0.** As imagens mais recentes do ORDS usam o Oracle Linux 10, que exige um processador com instruções AVX2 (o nível *x86-64-v3*). Muitas VMs do VirtualBox não as têm, sobretudo quando o Windows do computador tem o Hyper-V ligado. Para saber se a tua tem: `grep -c avx2 /proc/cpuinfo` (`0` = não tem). A 24.4.0 funciona com ou sem AVX2; quem tiver AVX2 pode usar outra versão mudando `ORDS_IMAGE` no `.env`.

Para acompanhar a instalação noutro terminal:

```bash
cd ~/projetos/aviation-otp-apex && python3 apex.py logs
```

## Bloco 5. Instalar a camada da aplicação

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

## Bloco 6. Testar a API REST

```bash
python3 apex.py check
curl -s "http://localhost:8181/ords/otp/api/v1/airlines?line_type=N" | python3 -m json.tool | head -25
```

**Deve ver:** a tabela de meses (voos, % pontualidade, % cancelados) e, no `curl`, um JSON com `"items": [...]` das companhias em voos domésticos.

## Bloco 7. Testar a ação (reconstruir um mês)

```bash
python3 apex.py refresh --month 2026-07
```

**Deve ver:** `HTTP 200: {"months_refreshed":1}`. No Observatório, `python3 tasks.py status` mostra uma nova execução `MART` no registo de cargas.

## Bloco 8. Abrir o APEX

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
| `ORA-20101` no install | O APEX não ficou instalado. Vê `python3 apex.py logs`; se a instalação falhou, `python3 apex.py down`, `docker volume rm otp-apex_ords_config` e repete o bloco 4. |
| Página `404` em `/ords/otp/...` | O módulo REST não foi publicado. Repete o bloco 5. |
| `Fatal glibc error: CPU does not support x86-64-v3` nos logs | A imagem do ORDS não é a 24.4.0. Confirma `ORDS_IMAGE` no `.env` (ou apaga essa linha para usar a do `docker-compose.yml`), depois `python3 apex.py down`, `docker volume rm otp-apex_ords_config` e o bloco 4. |
| `up` só mostra `...` sem minutos e nunca acaba | Versão antiga do `apex.py`, que não detetava um primeiro arranque interrompido. `git pull`, depois `python3 apex.py down`, `docker volume rm otp-apex_ords_config` e o bloco 4. |
| `Permission denied` em `/opt/oracle/variables` (Fedora) | O SELinux bloqueou a pasta `.secrets`. Confirma `:z` no fim dessa linha do `docker-compose.yml` (`git pull`). |
| `permission denied ... docker.sock` | O teu utilizador ainda não está no grupo `docker` desta sessão. Confirma com `groups`; se não aparecer, reinicia a máquina. |
| A VM fica lenta | Pouca RAM. Aumenta a memória da VM ou desliga outras aplicações. |
