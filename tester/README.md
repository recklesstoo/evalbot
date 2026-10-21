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
pip install yfinance tzdata
python fetch_yahoo.py                              # data/MNQ_1m.csv
python test_backtest.py                            # debe terminar en "Todas las pruebas pasaron."
python backtest.py data/MNQ_1m.csv                 # réplica del .cs
python backtest.py data/MNQ_1m.csv --compare       # variantes
python backtest.py data/MNQ_1m.csv --start 2026-09-01 --end 2026-09-30 --trades-out trades.csv
python backtest.py data/MNQ_1m.csv --set commission_per_contract=1.4 --set slippage_ticks=2
```

Todos los parámetros están en `Params` (mismos nombres y valores por defecto que el `.cs`).

## Qué replica del `.cs`

Señal de barrido (máx/mín de las 20 barras previas, cierre de recuperación, vela a favor), ATR(14) de
Wilder como NinjaTrader, stop = ATR×1.5 redondeado al tick (mín. 4 ticks), objetivo = stop×2,
tamaño = `RiskPerTrade / (stop × valor del punto)` con tope de contratos, máx. operaciones por día,
límites de pérdida/ganancia diarios (evaluados al cierre de barra), filtro de horario, reinicio diario
a medianoche del gráfico, cierre a las 16:59 ET. Entrada a mercado en la apertura de la barra siguiente.

## Supuestos que el consultor debe revisar

- **Stop y objetivo en la misma barra → se asume el stop primero** (conservador).
- **Slippage** (1 tick por defecto) en entradas a mercado y salidas por stop/mercado; los objetivos
  (límite) se llenan sin slippage. **Comisión** 1.00 USD ida y vuelta por contrato: ajustar al broker real.
- **Gap sobre el stop → se llena en la apertura** (peor que el stop).
- **Hora de la barra:** Yahoo da el *inicio*; NinjaTrader marca el *cierre*. El tester suma 1 minuto.
- **Zona horaria del gráfico:** `chart_tz` (por defecto `America/Panama`). Con `--set day_mode=cme` el día
  de trading cambia a las 18:00 ET en vez de medianoche (la réplica fiel del `.cs` es `calendar`).
- Si la barra siguiente no es contigua (cierre diario, hueco de datos) la señal se descarta.

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