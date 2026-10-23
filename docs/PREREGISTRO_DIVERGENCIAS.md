# Preregistro EvalBot — divergencias OHLCV 1m

**Estado: especificación preliminar, no estudio confirmatorio.** No se han analizado datos reales en esta entrega.

- Datos: 12 meses de MNQ 1m, UTC en inicio de barra; proveedor, contratos, rollover, SHA256 y paridad NinjaTrader documentados.
- A: barrido 20 barras, exceso 1 tick; sin puerta EMA; ATR Wilder 14 previo; stop max(1.5 ATR, 8 ticks); TP 2R; 30 barras.
- B: pivotes confirmados k=3; distancia 5-60 barras; RSI Wilder 14 +2; precio >0.25 ATR; disparo hasta 10 barras; stop 2 ticks más allá del pivote; riesgo entre 8 ticks y 3 ATR; TP 2R; 30 barras.
- RSI y MFI: 14; OHLCV 1m únicamente; 09:30-16:00 America/New_York; 120 barras previas y 30 futuras contiguas.
- Entrada t+1, 1 tick adverso; salida stop/horizonte con 1 tick adverso; objetivo sin slippage; stop antes que objetivo en empate; comisión $2.80 round-trip por contrato; MNQ $2/punto, tick 0.25.
- Riesgo: $100/trade, 3 trades/día, $400 pérdida diaria, 6 contratos máximo; trading day cambia 18:00 ET.
- H1: M1 supera M0 en R neto ejecutado (comparación por día); H2: B0 supera 0; Holm y bootstrap por día, 10k réplicas; 1000 permutaciones; 5 semillas.
- Walk-forward mensual creciente, >=6 meses entrenamiento; purga 120 previas +30 posteriores, validación interna 20%, embargo; malla depth 2/3/4, min_child_weight 20/50, lambda 1/10, eta .03, subsample .8, colsample .8, <=600 árboles.
- Requisito confirmatorio: 12 meses de datos, 6 meses de prueba, >=300 operaciones por hipótesis; 20 controles negativos y 20 positivos.

**No modificar parámetros después de ver datos reales sin registrar una nueva hipótesis.**
