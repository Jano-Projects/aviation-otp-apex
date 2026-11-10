# Guia das páginas APEX

Este guia constrói a aplicação no App Builder, página a página. Cada região diz **onde clicar**, **o que preencher** e traz o **SQL pronto a colar**. No fim, a aplicação é exportada para a pasta `apex/` e passa a fazer parte do repositório.

Pré-requisito: [guia de instalação](guia-instalacao.md) concluído (blocos 1 a 8) e sessão aberta no APEX com o utilizador `DEV`.

Testado com APEX 24.2. Os passos 1 a 3 foram feitos e conferidos assim; os restantes seguem o mesmo método.

> **Atalho:** se o repositório já tem `apex/f100.sql`, o `python3 apex.py install` importa a aplicação feita até aí. Este guia serve para a construir de raiz, perceber cada peça ou continuar as páginas que faltam.

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

## Como é o Page Designer

Quase tudo se faz no **Page Designer**, que abre quando se clica numa página. Tem três colunas:

| Coluna | O que tem |
|---|---|
| Esquerda | A árvore da página. O primeiro separador (**Rendering**) tem as regiões, os itens e os botões; o separador do **raio** tem as ações dinâmicas (*Dynamic Actions*), agrupadas por evento. |
| Meio | A disposição da página (*Layout*) e, por baixo, a galeria de regiões e itens que se podem arrastar. |
| Direita | O **Property Editor**: as propriedades do que está selecionado à esquerda. Nas regiões de gráfico e de cartões tem dois separadores: **Region** (de onde vêm os dados) e **Attributes** (como se desenham). |

Para criar qualquer coisa: botão direito no sítio certo da árvore (por exemplo **Body**) e **Create Region**, **Create Page Item** ou **Create Dynamic Action**. Depois preenche-se o Property Editor. No fim, **Save** (canto superior direito) e ▶ para correr.

## Como os filtros chegam ao SQL

1. O utilizador muda uma lista; o browser dispara o evento *Change*.
2. A ação dinâmica **Aplicar filtros** apanha-o e faz *Submit Page*.
3. O APEX guarda os valores na sessão (*session state*) com os nomes `P0_MONTH_FROM`, `P0_MONTH_TO`, `P0_LINE_TYPE`.
4. A página é desenhada de novo; cada região corre o seu SQL e o APEX troca `:P0_LINE_TYPE` (e os outros) pelos valores da sessão.

Se os filtros não mudarem nada, um destes elos falhou; a secção *Dicas*, no fim, diz como encontrar qual.

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

A página 0 é desenhada dentro de todas as outras páginas. Os filtros ficam lá e cada região lê `:P0_...`.

### 2.1 A região "Filtros"

1. Abrir a página **0 - Global Page** (o assistente de criação já a cria; se não existir: **Create Page** > **Global Page**).
2. Botão direito em **Body** > **Create Region**. À direita:
   - **Identification > Title:** `Filtros` · **Type:** `Static Content`
   - **Server-side Condition > Type:** `Current Page is NOT in Comma Delimited List` · **Pages:** `6,7,9999`

A condição esconde os filtros nas páginas onde não fazem sentido: **9999** (Login), **6** (Cargas) e **7** (Ações). As páginas 6 e 7 ainda não existem neste ponto; uma condição que as menciona não dá erro e fica pronta para quando forem criadas.

### 2.2 Os três itens

Botão direito na região **Filtros** > **Create Page Item**, três vezes. O APEX dá o nome provisório `P0_NEW`; muda-se logo em **Name**.

| Name | Type | Label | Layout > Start New Row |
|---|---|---|---|
| `P0_MONTH_FROM` | Select List | Mês inicial | ligado |
| `P0_MONTH_TO` | Select List | Mês final | desligado |
| `P0_LINE_TYPE` | Select List | Tipo de linha | desligado |

Nos dois meses, **List of Values > Type** `SQL Query`:

```sql
select month_label as d, month_label as r
  from v_months
 order by month_start desc
```

No tipo de linha, **List of Values > Type** `Static Values`; clicar no campo **Static Values** abre uma grelha de pares *Display Value* / *Return Value*:

| Display Value | Return Value |
|---|---|
| Doméstico | N |
| Internacional | I |
| Cargueiro | C |
| Outros | G |

Nos três itens: **Display Extra Values** desligado, **Display Null Value** ligado, **Null Display Value** `(todos)`. Confirmar também **Session State > Storage** = `Per Session (Persistent)` (é o valor por omissão).

### 2.3 A ação dinâmica

Sem ela, mudar uma lista não envia nada ao servidor e os números não mudam.

1. Na coluna da esquerda, separador do **raio**. Botão direito em **Change** > **Create Dynamic Action**.
2. Na ação nova, à direita:
   - **Identification > Name:** `Aplicar filtros`
   - **When > Event:** `Change` · **Selection Type:** `Item(s)` · **Item(s):** `P0_MONTH_FROM,P0_MONTH_TO,P0_LINE_TYPE`
3. Na árvore, por baixo de **True**, clicar na ação **Show** e mudar **Identification > Action** para `Submit Page`.

**Deve ver** (Save, ▶): o login sem filtros; depois de entrar, a caixa **Filtros** no topo do Painel. Ao escolher *Doméstico*, a página recarrega e a lista mantém *Doméstico*.

## Passo 3. Página 1, Painel

### 3.1 Indicadores-chave (Cards)

Botão direito em **Body** > **Create Region**. Separador **Region**: **Title** `Indicadores`, **Type** `Cards`, **Source > Type** `SQL Query`, e o SQL:

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

Separador **Attributes**: **Appearance > Layout** = `Horizontal (Row)`; **Title > Column** = `VALUE`; **Subtitle > Column** = `LABEL`; **Icon and Badge > Icon Source** = `Icon Class Column`, **Icon Column** = `ICON`.

### 3.2 Pontualidade por mês (gráfico de linhas)

**Create Region**: **Title** `Pontualidade por mês`, **Type** `Chart`. Na árvore, por baixo da região, aparece **Series** com uma série **New**; clicar nela:

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
- Na árvore, por baixo da região, **Axes** > **y**: **Title** `%`, **Minimum** `0`, **Maximum** `100`.

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

- Série 1 (a **New**): **Name** `Realizados`, Value = `REALIZED`. Série 2 (botão direito em **Series** > **Create Series**): **Name** `Cancelados`, Value = `CANCELLED`. Label = `MONTH_LABEL` nas duas.
- Na região, separador **Attributes**: **Settings > Stack** ligado.

**Deve ver** (▶ Run): os quatro cartões, a linha da pontualidade e as barras empilhadas. Mudar o tipo de linha para Doméstico recalcula tudo.

## Passo 4. Página 2, Companhias

Na página inicial da aplicação, **Create Page** > **Blank Page**: **Page Number** `2`, **Name** `Companhias`, e ligar a entrada no menu de navegação (**Use Navigation** / *Create a new navigation menu entry*, conforme a versão). **Create Page** abre o Page Designer na página nova.

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

O `python3 apex.py install` importa `apex/f100.sql` **só se a aplicação ainda não existir** no workspace (por exemplo, numa máquina nova). Assim nunca apaga por engano páginas feitas no App Builder e ainda não exportadas. Para substituir de propósito a aplicação pela versão exportada: `python3 apex.py install --replace-app`.

Regra para duas máquinas: **exportar e fazer push antes de mudar de máquina**; na outra, `git pull` e `python3 apex.py install --replace-app`.

## Dicas

- **Os filtros não mudam nada:** abre a página 0, separador do raio. Se **Events > Change** não tiver a ação **Aplicar filtros**, falta o passo 2.3. Se a página recarrega mas a lista volta a `(todos)`, confirma **Session State > Storage** = `Per Session (Persistent)` nos três itens. Para ver os valores guardados: na aplicação a correr, barra de baixo > **Session**.
- **Os filtros aparecem no login:** falta `9999` na condição da região **Filtros** (passo 2.1).

- **Ver o SQL de uma região a correr:** Run > barra de baixo **Debug**, depois **View Debug**.
- **Erro `ORA-20200` numa região:** um filtro chegou num formato diferente de `YYYY-MM`. Confirma que o **Return Value** das listas de meses é `month_label`.
- **Gráfico vazio:** confirma o **Column Mapping** (Label e Value) da série; é o esquecimento mais comum.
- **Mudaste uma view?** Corre de novo `python3 apex.py install`; as páginas leem as views em cada pedido.
