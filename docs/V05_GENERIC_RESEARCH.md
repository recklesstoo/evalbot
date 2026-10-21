# EvalBot V0.5 — Motor genérico de investigación

**Objetivo:** aprender la probabilidad de que el precio alcance un TP antes de un SL para una operación larga o corta, utilizando exclusivamente barras cerradas. No depende de Trump, Truth Social, noticias, ni de un régimen predefinido.

## Arquitectura

1. **Percepción causal:** 12 características normalizadas por ATR, volumen relativo y posición en rango, calculadas con barras disponibles al decidir.
2. **Etiquetado triple barrera:** entrada hipotética en apertura de la barra siguiente, stop ATR y objetivo R:R, con horizonte configurable. Si una misma vela toca TP y SL, se asigna SL de manera conservadora.
3. **Modelo:** XGBoost para P(TP antes de SL) de ambas direcciones. Las muestras sin resolución dentro del horizonte se excluyen: la probabilidad es **condicional a resolución**, no una probabilidad incondicional de beneficio.
4. **Validación:** división temporal 60/20/20 con purga de etiquetas solapadas. Se reportan AUC, Brier y R medio de operaciones seleccionadas con costos aproximados.
5. **Abstención:** si la probabilidad estimada no supera el umbral económico, no hay señal.

## Current review status\n\n**REJECTED pending reproducibility and validation.** The documented commands cannot all run from a clean clone. The strategy has not been compiled in NinjaTrader. Do not treat the reported selected mean R as executable P&L.\n\n## Windows

```powershell
pip install numpy scikit-learn xgboost yfinance tzdata
cd tester
python test_backtest.py
python test_adaptive.py
python test_v05.py
python fetch_yahoo.py
python evalbot_v05.py data/MNQ_1m.csv --horizon 15 --rr 2 --out model_v05.json
```

CSV requerido: `timestamp,open,high,low,close,volume`; timestamp representa inicio de vela en UTC o con offset. Con pocos días de Yahoo se espera **MUESTRA INSUFICIENTE**.

## Limitaciones esenciales

- **No es un bot listo para producción:** no modifica la estrategia NinjaTrader V0.3 ni envía órdenes.
- No se ha demostrado rentabilidad ni paridad de ejecución con NinjaTrader.
- Se evalúan ambas direcciones de cada barra como candidatos independientes: el R medio mostrado **no es P&L de una cartera ejecutable**, ya que ignora exclusión de señales simultáneas, capital, horario, órdenes y superposición.
- El coste R utiliza el stop mínimo de la muestra (aproximación conservadora) y no reemplaza un simulador de órdenes.
- Las etiquetas que no tocan barreras se excluyen; antes de tomar decisiones reales habrá que modelar la tercera clase «sin resolución» o valorar el cierre al horizonte.
- El test no se usa para seleccionar hiperparámetros. Para evaluación comercial, hacer walk-forward con períodos independientes, validación de calibración, fees/slippage realistas y conciliación con NinjaTrader.
- Los archivos de V0.4 en `tester/` se conservan sin cambios para comparaciones.