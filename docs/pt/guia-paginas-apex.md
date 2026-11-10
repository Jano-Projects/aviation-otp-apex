# Guia das páginas APEX

Este guia constrói a aplicação no App Builder, página a página. Cada região diz **onde clicar**, **o que preencher** e traz o **SQL pronto a colar**. No fim, a aplicação é exportada para a pasta `apex/` e passa a fazer parte do repositório.

Pré-requisito: [guia de instalação](guia-instalacao.md) concluído (blocos 1 a 8) e sessão aberta no APEX com o utilizador `DEV`.

## O que vamos construir

| Página | Nome | Conteúdo |
|---|---|---|
| 0 | Global Page | filtros comuns: mês inicial, mês final, tipo de linha |
| 1 | Painel | indicadores-chave, pontualidade por mês, cancelamentos por mês |
| 2 | Companhias | gráfico das 15 maiores e relatório interativo |
| 3 | Aeroportos | mapa dos aeroportos de origem e relatório interativo |
| 4 | Horários | pontualidade por hora e por dia da semana |
| 5 | Rotas | relatório interativo das rotas |
| 6 | Cargas | histórico das cargas do Observatório |
| 7 | Ações | reconstruir o esquema estrela |

## A regra das percentagens

Todas as views têm **medidas aditivas**: `flights`, `cancelled`, `measurable`, `on_time`. Em cada região, soma-se primeiro e divide-se depois:

```sql
round(100 * sum(on_time)   / nullif(sum(measurable), 0), 1) as on_time_pct
round(100 * sum(cancelled) / nullif(sum(flights), 0), 1)    as cancelled_pct
```

Nunca `avg(on_time_pct)`: a média das percentagens mensais não é a percentagem do período (um mês com 10 voos pesaria o mesmo que um com 60 mil).

E o filtro comum, que aparece em quase todas as regiões:

```sql
where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                      and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
  and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
```

---

## Passo 1. Criar a aplicação

1. **App Builder** > **Create** > **New Application**.
2. Preencher:
   - **Name:** `Observatório de Pontualidade Aérea`
   - **Appearance:** clicar no ícone ao lado e escolher **Vita** (ou outro tema a gosto).
   - **Pages:** deixar só a **Home** que já vem; as outras criamos à mão.
   - **Advanced Settings** (expandir): **Application ID** `100`, **Schema** `OTP_APP`.
3. **Create Application**.
4. Ainda no App Builder, na aplicação: **Shared Components** > **Application Definition** (Edit Application Definition) > **Application Alias** = `OBSERVATORIO` > **Apply Changes**.

**Deve ver:** a aplicação 100 com a página 1 (Home). Correr com o botão ▶ (Run): pede login, que é o mesmo `DEV`. O endereço fica `http://localhost:8181/ords/r/otp/observatorio/home`.

Mudar o nome da página 1 de Home para Painel: abrir a página 1, em **Page** > **Name** = `Painel`, **Title** = `Painel`.

## Passo 2. Global Page (página 0): os filtros

A página 0 é desenhada em todas as outras páginas. Os filtros ficam lá e cada região lê `:P0_...`.

1. Abrir a página **0 - Global Page** (se não existir: **Create Page** > **Global Page**).
2. Criar uma região: botão direito em **Body** > **Create Region**.
   - **Title:** `Filtros` · **Type:** `Static Content`
   - **Appearance** > **Template:** `Buttons Container` (fica compacta)
   - **Server-side Condition** > **Type:** `Current Page is NOT in comma delimited list` · **Value:** `6,7`
3. Na região, criar três itens (botão direito > **Create Page Item**):

| Item | Type | Label | List of Values |
|---|---|---|---|
| `P0_MONTH_FROM` | Select List | Mês inicial | SQL abaixo |
| `P0_MONTH_TO` | Select List | Mês final | SQL abaixo |
| `P0_LINE_TYPE` | Select List | Tipo de linha | Static: `Doméstico;N,Internacional;I,Cargueiro;C,Outros;G` |

SQL da lista dos dois meses:

```sql
select month_label as d, month_label as r
  from v_months
 order by month_start desc
```

Em cada item: **List of Values** > **Display Extra Values** = Off, **Display Null Value** = On, **Null Display Value** = `(todos)`. Em **Layout**, pôr `Start New Row` = Off nos dois últimos, para ficarem lado a lado.

4. Ação dinâmica: selecionar os três itens (Ctrl+clique) > botão direito > **Create Dynamic Action**.
   - **Name:** `Aplicar filtros` · **Event:** `Change`
   - Na ação **True**: **Action** = `Submit Page`.

Assim, ao mudar qualquer filtro, a página recarrega com os novos valores em sessão e todas as regiões recalculam.

## Passo 3. Página 1, Painel

### 3.1 Indicadores-chave (Cards)

Botão direito em **Body** > **Create Region**: **Title** `Indicadores`, **Type** `Cards`.

```sql
with f as (
  select sum(flights) flights, sum(cancelled) cancelled,
         sum(measurable) measurable, sum(on_time) on_time
    from v_otp_airline_month
   where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                         and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
     and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
)
select 1 ord, 'Voos' label, to_char(flights, '999G999G990') value, 'fa-plane' icon from f
union all
select 2, 'Pontualidade (até 15 min)', to_char(round(100 * on_time / nullif(measurable, 0), 1), 'FM990D0') || ' %', 'fa-clock-o' from f
union all
select 3, 'Cancelados', to_char(round(100 * cancelled / nullif(flights, 0), 1), 'FM990D0') || ' %', 'fa-ban' from f
union all
select 4, 'Voos medidos', to_char(measurable, '999G999G990'), 'fa-check' from f
order by 1
```

Em **Attributes** da região: **Title** > Column = `VALUE`; **Subtitle** > Column = `LABEL`; **Icon and Badge** > Icon Source = `Icon Class Column`, Icon Column = `ICON`. **Grid** > Layout = `Horizontal (Row)`.

### 3.2 Pontualidade por mês (gráfico de linhas)

**Create Region**: **Title** `Pontualidade por mês`, **Type** `Chart`. Na série criada automaticamente (**Series** > **New**):

- **Name:** `Pontualidade %` · **Type:** `Line`
- **Source** > SQL:

```sql
select to_char(month_start, 'YYYY-MM') as month_label,
       round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct
  from v_otp_airline_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by month_start
 order by month_start
```

- **Column Mapping:** Label = `MONTH_LABEL`, Value = `ON_TIME_PCT`.
- No eixo **y** (Axes > y): **Title** `%`, **Minimum** `0`, **Maximum** `100`.

### 3.3 Voos e cancelamentos por mês (barras)

Outra região **Chart**, **Title** `Voos e cancelamentos`, **Layout** > Start New Row = Off (fica ao lado da anterior). Duas séries do tipo **Bar**, ambas com este SQL:

```sql
select to_char(month_start, 'YYYY-MM') as month_label,
       sum(flights) - sum(cancelled) as realized,
       sum(cancelled)                as cancelled
  from v_otp_airline_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by month_start
 order by month_start
```

- Série 1: **Name** `Realizados`, Value = `REALIZED`. Série 2: **Name** `Cancelados`, Value = `CANCELLED`. Label = `MONTH_LABEL` nas duas.
- Na região (Attributes): **Stack** = On.

**Deve ver** (▶ Run): os quatro cartões, a linha da pontualidade e as barras empilhadas. Mudar o tipo de linha para Doméstico recalcula tudo.

## Passo 4. Página 2, Companhias

**Create Page** > **Blank Page**: Number `2`, Name `Companhias`, **Navigation** > Create a new navigation menu entry = On.

### 4.1 Gráfico das 15 maiores

Região **Chart**, **Title** `Pontualidade das 15 companhias com mais voos`, série **Bar**:

```sql
select airline_name,
       round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct
  from v_otp_airline_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by airline_icao, airline_name
 order by sum(flights) desc
 fetch first 15 rows only
```

Label = `AIRLINE_NAME`, Value = `ON_TIME_PCT`. Na região: **Orientation** = `Horizontal`.

### 4.2 Relatório interativo

Região **Interactive Report**, **Title** `Todas as companhias`:

```sql
select airline_icao  as "ICAO",
       airline_name  as "Companhia",
       nationality   as "Nacionalidade",
       sum(flights)  as "Voos",
       sum(cancelled) as "Cancelados",
       round(100 * sum(on_time)   / nullif(sum(measurable), 0), 1) as "Pontualidade %",
       round(100 * sum(cancelled) / nullif(sum(flights), 0), 1)    as "Cancelados %"
  from v_otp_airline_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by airline_icao, airline_name, nationality
 order by 4 desc
```

Nas colunas `Voos` e `Cancelados`: **Format Mask** `999G999G990`. O relatório interativo já traz pesquisa, ordenação, filtros, gráficos e download em CSV/Excel no menu **Actions**.

## Passo 5. Página 3, Aeroportos (mapa)

**Create Page** > **Blank Page**: Number `3`, Name `Aeroportos`, com entrada no menu.

### 5.1 Mapa

Região **Map**, **Title** `Aeroportos de origem`. Na camada (**Layers** > **New**):

- **Name:** `Aeroportos` · **Layer Type:** `Points`
- **Source** > SQL:

```sql
select airport_icao, airport_name, city, state_uf, latitude, longitude,
       sum(departures) as departures,
       round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct
  from v_otp_airport_month
 where latitude is not null
   and month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by airport_icao, airport_name, city, state_uf, latitude, longitude
```

- **Column Mapping** > **Geometry Column Data Type:** `Longitude/Latitude` · Longitude = `LONGITUDE` · Latitude = `LATITUDE`.
- **Tooltip** > Advanced Formatting = On, HTML:

```
<b>&AIRPORT_ICAO. &AIRPORT_NAME.</b><br>&CITY. / &STATE_UF.<br>&DEPARTURES. partidas · &ON_TIME_PCT. % no horário
```

- Na região (Attributes) > **Initial Position and Zoom**: Longitude `-52`, Latitude `-14`, Zoom `3` (Brasil inteiro).

O APEX usa um mapa de fundo próprio; precisa de internet na VM para desenhar o fundo, os pontos vêm da base.

### 5.2 Relatório interativo

Região **Interactive Report**, **Title** `Todos os aeroportos`:

```sql
select airport_icao as "ICAO", airport_name as "Aeroporto", city as "Cidade",
       state_uf as "UF", country_name as "País",
       sum(departures) as "Partidas",
       round(100 * sum(on_time)   / nullif(sum(measurable), 0), 1) as "Pontualidade %",
       round(100 * sum(cancelled) / nullif(sum(departures), 0), 1) as "Cancelados %"
  from v_otp_airport_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by airport_icao, airport_name, city, state_uf, country_name
 order by 6 desc
```

## Passo 6. Página 4, Horários

**Create Page** > **Blank Page**: Number `4`, Name `Horários`, com entrada no menu.

### 6.1 Por hora da partida prevista

Região **Chart**, **Title** `Pontualidade por hora da partida prevista`, série **Bar**:

```sql
select lpad(hour_key, 2, '0') || 'h' as hour_label,
       round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct,
       sum(flights) as flights
  from v_otp_hour_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by hour_key
 order by hour_key
```

Label = `HOUR_LABEL`, Value = `ON_TIME_PCT`. Opcional: segunda série do tipo **Line** com Value = `FLIGHTS` e, nela, **Assigned To Y2 Axis** = On, para ver o volume ao lado da pontualidade.

### 6.2 Por dia da semana

Região **Chart**, **Title** `Pontualidade por dia da semana`, Start New Row = Off, série **Bar**:

```sql
select day_name_pt,
       round(100 * sum(on_time) / nullif(sum(measurable), 0), 1) as on_time_pct
  from v_otp_weekday_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by iso_day_of_week, day_name_pt
 order by iso_day_of_week
```

Label = `DAY_NAME_PT`, Value = `ON_TIME_PCT`.

## Passo 7. Página 5, Rotas

**Create Page** > **Blank Page**: Number `5`, Name `Rotas`, com entrada no menu. Região **Interactive Report**, **Title** `Rotas`:

```sql
select orig_icao || ' → ' || dest_icao as "Rota",
       orig_city as "Origem", dest_city as "Destino",
       sum(flights) as "Voos",
       round(100 * sum(on_time)   / nullif(sum(measurable), 0), 1) as "Pontualidade %",
       round(100 * sum(cancelled) / nullif(sum(flights), 0), 1)    as "Cancelados %"
  from v_otp_route_month
 where month_start between nvl(pkg_app_api.to_month(:P0_MONTH_FROM), date '1900-01-01')
                       and nvl(pkg_app_api.to_month(:P0_MONTH_TO),   date '9999-12-01')
   and (:P0_LINE_TYPE is null or line_type = :P0_LINE_TYPE)
 group by orig_icao, orig_city, dest_icao, dest_city
having sum(flights) >= 30
 order by 4 desc
```

O `having` deixa de fora rotas com menos de 30 voos no período, em que uma percentagem diz pouco.

## Passo 8. Página 6, Cargas

**Create Page** > **Blank Page**: Number `6`, Name `Cargas`, com entrada no menu. Região **Interactive Report**, **Title** `Histórico de cargas`:

```sql
select run_id as "Execução", src_file as "Origem", month_label as "Mês",
       status as "Estado", started_at as "Início", finished_at as "Fim",
       rows_staged as "Lidas", rows_loaded as "Carregadas",
       rows_rejected as "Rejeitadas", rows_duplicate as "Duplicadas",
       error_message as "Erro"
  from v_load_runs
 order by run_id desc
```

A página 6 não mostra os filtros (condição do passo 2): o histórico não depende de mês nem de tipo de linha.

## Passo 9. Página 7, Ações

**Create Page** > **Blank Page**: Number `7`, Name `Ações`, com entrada no menu.

1. Região **Static Content**, **Title** `Reconstruir o esquema estrela`. Texto (Source > HTML Code):

```html
<p>Recalcula a tabela de factos e as dimensões a partir dos voos carregados.
Escolha um mês, ou deixe em branco para reconstruir todos (pode levar alguns minutos).</p>
```

2. Item `P7_MONTH`, **Select List**, Label `Mês`, LOV com o mesmo SQL de meses do passo 2, Null Display Value `(todos os meses)`.
3. Botão: botão direito na região > **Create Button**: **Name** `REFRESH`, **Label** `Reconstruir`, **Hot** = On, **Action** = `Submit Page`.
4. Processo: no separador **Processing** (ícone das engrenagens) > botão direito em **Processes** > **Create Process**:
   - **Name:** `Reconstruir esquema estrela` · **Type:** `Execute Code`
   - **PL/SQL Code:**

```sql
declare
  l_months pls_integer;
begin
  l_months := pkg_app_api.refresh_mart(pkg_app_api.to_month(:P7_MONTH));
  apex_application.g_print_success_message :=
    'Esquema estrela reconstruído: ' || l_months || ' mês(es).';
end;
```

   - **Server-side Condition** > When Button Pressed = `REFRESH`.
   - **Error Message:** `Falhou a reconstrução: #SQLERRM#`

5. Por baixo, uma região **Classic Report**, **Title** `Últimas execuções`, para ver o resultado logo a seguir:

```sql
select run_id as "Execução", src_file as "Origem", month_label as "Mês",
       status as "Estado", started_at as "Início", rows_loaded as "Linhas"
  from v_load_runs
 order by run_id desc
 fetch first 5 rows only
```

**Deve ver:** ao clicar em Reconstruir com `2026-07`, a mensagem verde `Esquema estrela reconstruído: 1 mês(es).` e uma nova linha `MART` em Últimas execuções.

O `pkg_app_api.refresh_mart` faz `COMMIT`: na aplicação, o pedido HTTP é a unidade de trabalho. Os packages do Observatório continuam sem commit, como antes.

## Passo 10. Exportar a aplicação para o repositório

Assim a aplicação passa a estar no GitHub e o `python3 apex.py install` reinstala-a em qualquer máquina.

1. App Builder > aplicação 100 > **Export / Import** > **Export**.
2. **Export Application** com as opções por omissão (File Format `SQL`). Descarrega `f100.sql` para `~/Downloads`.
3. No terminal:

```bash
cd ~/projetos/aviation-otp-apex
mv ~/Downloads/f100.sql apex/
git add apex/f100.sql
git commit -m "APEX application: dashboard, airlines, airports map, hours, routes, loads, actions"
git push
```

**Deve ver:** o push terminar com `main -> main`. A partir daqui, sempre que mudares páginas no App Builder, repete o passo 10 para guardar a versão nova.

Para provar que a exportação funciona: `python3 apex.py install` deve terminar com `Importing the APEX application from apex/f100.sql` sem erros.

## Dicas

- **Ver o SQL de uma região a correr:** Run > barra de baixo **Debug**, depois **View Debug**.
- **Erro `ORA-20200` numa região:** um filtro chegou num formato diferente de `YYYY-MM`. Confirma que o **Return Value** das listas de meses é `month_label`.
- **Gráfico vazio:** confirma o **Column Mapping** (Label e Value) da série; é o esquecimento mais comum.
- **Mudaste uma view?** Corre de novo `python3 apex.py install`; as páginas leem as views em cada pedido.
