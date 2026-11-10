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

## Bloco 4. Instalar o APEX e o ORDS e subir (primeira vez: 20 a 30 minutos)

```bash
python3 apex.py up
```

Na primeira vez, o `up` faz quatro coisas, cada uma com a sua mensagem:

1. `Downloading Oracle APEX 24.2`: descarrega os ficheiros de instalação do APEX (cerca de 200 MB, do site da Oracle) para `.cache/`, confere o checksum e descompacta.
2. `Installing Oracle APEX 24.2 into the database`: corre o script oficial `apexins.sql` dentro da base. Demora 10 a 20 minutos e mostra `... N min` a cada 30 segundos; o registo completo fica em `.cache/apexins.log`.
3. `Installing ORDS into the database`: o `ords install` cria os utilizadores do ORDS na base, liga o APEX (*PL/SQL gateway*) e grava a configuração no volume `otp-apex_ords_config`.
4. `Starting ORDS`: liga o contentor e espera que responda.

**Deve ver no fim:** `ORDS is ready: http://localhost:8181/ords/`.

Cada passo verifica primeiro o estado real (o APEX está instalado? a configuração existe?), por isso, se o `up` for interrompido, basta corrê-lo de novo: continua onde parou. Nas vezes seguintes demora segundos.

**Porquê a versão 24.4.0.** As imagens mais recentes do ORDS usam o Oracle Linux 10, que exige um processador com instruções AVX2 (o nível *x86-64-v3*). Muitas VMs do VirtualBox não as têm, sobretudo quando o Windows do computador tem o Hyper-V ligado. Para saber se a tua tem: `grep -c avx2 /proc/cpuinfo` (`0` = não tem). A 24.4.0 funciona com ou sem AVX2; quem tiver AVX2 pode usar outra versão mudando `ORDS_IMAGE` no `.env`.

**Porquê instalar o APEX à parte.** A imagem `database/ords` só serve o ORDS: arranca vazia, na porta 8080, à espera de configuração. A imagem que fazia tudo sozinha (`database/ords-developer`) pede login no registo da Oracle. Instalar com os scripts oficiais (`apexins.sql` e `ords install`) dá o mesmo resultado, sem conta e sem depender de comportamento escondido na imagem.

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
| `up` fica muito tempo em `... N min` na instalação do APEX | Normal (10 a 20 min). O progresso está em `.cache/apexins.log` (`tail -f .cache/apexins.log` noutro terminal). |
| `APEX was not installed` | As últimas linhas do registo aparecem no ecrã; o registo completo está em `.cache/apexins.log`. Corrige a causa e corre `python3 apex.py up` de novo. |
| `Installing ORDS failed` | Confirma que `ORACLE_PASSWORD` no `.env` é igual ao do Observatório. Depois `python3 apex.py up` de novo. |
| `ORA-20100` no install | O esquema estrela não existe. No Observatório: `python3 tasks.py install` e `python3 tasks.py mart`. |
| `ORA-20101` no install | O APEX não está instalado. Corre `python3 apex.py up` primeiro. |
| Página `404` em `/ords/otp/...` | O módulo REST não foi publicado. Repete o bloco 5. |
| Páginas do APEX sem estilos nem ícones | O ORDS não encontra os ficheiros estáticos. Confirma que existe `.cache/apex/images` e que o `docker-compose.yml` monta essa pasta com `:ro,z`. |
| `Fatal glibc error: CPU does not support x86-64-v3` nos logs | A imagem do ORDS não é a 24.4.0. Confirma `ORDS_IMAGE` no `.env` (ou apaga essa linha para usar a do `docker-compose.yml`) e corre `python3 apex.py up` de novo. |
| `permission denied ... docker.sock` | O teu utilizador ainda não está no grupo `docker` desta sessão. Confirma com `groups`; se não aparecer, reinicia a máquina. |
| A VM fica lenta | Pouca RAM. Aumenta a memória da VM ou desliga outras aplicações. |
