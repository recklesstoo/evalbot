# EvalBot tester

Replica en Python la lógica de `ninjatrader/EvalBotAutoTrader.cs` (V0.3) sobre barras de 1 minuto y
mide el resultado **con comisiones y slippage**. No se conecta a ningún broker ni envía órdenes.

| Archivo | Para qué |
|---|---|
| `fetch_yahoo.py` | Descarga barras de 1 min de Yahoo (`MNQ=F`) y las **acumula** en un CSV. Correrlo a diario/semanalmente. |
| `backtest.py` | El tester. Lee el CSV, simula, imprime métricas y compara variantes. |
| `test_backtest.py` | Pruebas con escenarios de resultado conocido (objetivo, stop, gap, límites, short). |
| `synth_data.py` | Datos **sintéticos** para probar que el tester corre. No son mercado. |

## Uso

```bash
pip install -r requirements.txt                    # versiones fijadas
python fetch_yahoo.py                              # data/MNQ_1m.csv (Yahoo, ~29 días; está en .gitignore)
python -m unittest discover -p "test_*.py" -v      # debe terminar en "OK"
python backtest.py data/MNQ_1m.csv                 # réplica del .cs
python backtest.py data/MNQ_1m.csv --compare       # variantes
python backtest.py data/MNQ_1m.csv --start 2026-09-01 --end 2026-09-30 --trades-out trades.csv
python backtest.py data/MNQ_1m.csv --set commission_per_contract=1.4 --set slippage_ticks=2
```

Todos los parámetros están en `Params` (mismos nombres y valores por defecto que el `.cs`).

## Qué replica del `.cs`

Señal de barrido (máx/mín de las 20 barras previas ±1 tick, cierre de recuperación, vela a favor, filtro
EMA50 activado por defecto), ATR(14) de Wilder como NinjaTrader, stop = ATR de la barra previa × 1.5
redondeado hacia arriba al tick (**mínimo 8 ticks**, igual que el `.cs`), objetivo = stop × 2,
tamaño = `RiskPerTrade / (stop × valor del punto)` redondeado hacia abajo con tope de contratos, máx.
operaciones por día, límites de pérdida/ganancia diarios (evaluados al cierre de barra; la salida es a
mercado en la apertura siguiente), sesión 09:30–11:30, reinicio diario, cierre a las 16:59 en `chart_tz`.
Entrada a mercado en la apertura de la barra siguiente.

## Costos por operación

`cost_R_i = (comisión + patas_con_slippage × slippage_ticks × tick × valor_punto) / (stop_puntos × valor_punto)`.
Una operación que cierra en el objetivo tiene 1 pata con slippage (la entrada); una que cierra en stop,
gap, límite diario o cierre de sesión tiene 2. Se cumple `r_net = r_gross − cost_R_i` y las pruebas lo
verifican. Comisión por defecto: **2.80 USD** ida y vuelta por contrato (igual que el preregistro).

## Diferencias deliberadas respecto al `.cs` (revisar)

- El `.cs` **solo cuenta `tradesToday` en tiempo real** (`State == Realtime`), así que en Strategy Analyzer
  el límite de 3 operaciones al día no se aplicaría. El tester lo aplica, que es la intención del diseño.
- `AccountWideRiskGuardImplemented()` devuelve siempre `false`: el `.cs` actual **no envía órdenes**.
  El tester ignora ese guard para poder medir la lógica.
- El `.cs` no tiene hora de cierre propia: sale por `IsExitOnSessionCloseStrategy` (plantilla de sesión,
  60 s antes del cierre). El tester usa `flatten_hhmm=1659`.
- Fórmula del ATR con calentamiento y stop/objetivo en la misma barra de entrada: **no verificados contra
  NinjaTrader**; es justo lo que debe comprobar la prueba de paridad.

## Supuestos que el consultor debe revisar

- **Stop y objetivo en la misma barra → se asume el stop primero** (conservador).
- **Slippage** (1 tick por defecto) en entradas a mercado y salidas por stop/mercado; los objetivos
  (límite) se llenan sin slippage y, si el precio los atraviesa con gap, se llenan en el objetivo (conservador).
- **Gap sobre el stop → se llena en la apertura** (peor que el stop), más el slippage.
- **Hora de la barra:** el CSV trae el *inicio*; NinjaTrader marca el *cierre*. El tester suma 1 minuto.
- **Zona horaria del gráfico:** `chart_tz` (por defecto `America/New_York`, con horario de verano). Con
  `--set day_mode=cme` el día de trading cambia a las 18:00 ET en vez de medianoche (la réplica fiel del
  `.cs` es `calendar`). Los timestamps sin offset se interpretan con `--input-tz` (defecto UTC).
- Si la barra siguiente no es contigua (cierre diario, hueco de datos) la señal se descarta; una posición
  abierta cuando aparece un hueco se cierra en la apertura siguiente (`DATA_GAP`).

## Qué NO modela

Cola de ejecución y fills parciales, rechazos de órdenes, reconexiones, comisiones reales por exchange,
el drawdown/trailing de la cuenta, ni P&L a nivel de cuenta (como el `.cs`, el contador es por estrategia).

## Límites de los datos de Yahoo (leer antes de concluir nada)

- El 1 minuto de Yahoo cubre **solo días o pocas semanas**. Con ese volumen la muestra es de decenas de
  operaciones: **no sirve para elegir parámetros ni filtros**. El tester avisa cuando n < 100.
- `MNQ=F` es una serie continua; no se verificó cómo trata los rollovers, el volumen ni los husos horarios.
  Comparar una semana contra las barras de NinjaTrader del mismo período antes de fiarse.
- Para historia larga: exportar desde NinjaTrader (Tools → Historical Data → Export) o comprar un paquete de
  datos, y pasar el CSV por el mismo `backtest.py` (columnas `timestamp,open,high,low,close,volume`).

## Cómo evaluar una mejora sin engañarse

1. **Validar paridad primero:** una semana en NinjaTrader (Strategy Analyzer, mismos parámetros y costos)
   contra `--trades-out`. Si las operaciones no coinciden, el tester no es fiable todavía.
2. Elegir variantes con un tramo (`--start/--end`) y **confirmar en otro tramo que no se usó para elegir**.
3. Mirar el intervalo de confianza de la expectativa, no solo el neto. `--compare` prueba 7 variantes sobre
   los mismos datos: sobre una caminata aleatoria (sin ventaja alguna) alguna sale "ganadora" por azar.
4. Reportar también peor racha perdedora, drawdown y semanas positivas.