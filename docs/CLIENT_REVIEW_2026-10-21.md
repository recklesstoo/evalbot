# Cliente: revisión de 21-oct-2026 — plan de aceptación

**Estado: NO APROBADO.** Este documento recoge los hallazgos del cliente. No afirma que se hayan resuelto.

## Bloqueantes

1. **Reproducibilidad**: incorporar todos los scripts originales del tester, requirements con versiones, CI en Windows/Linux y pruebas desde clon limpio. Hasta entonces, no publicar métricas como reproducibles.
2. **Ejecución real**: compilar NinjaScript en Windows; comparar operaciones con Strategy Analyzer; resolver reinicio por sesión, riesgos a nivel de cuenta, órdenes pendientes tras reinicio, reconexión, stop/target, límites y fills parciales. Ningún código Python se considera sustituto de esta validación.

## Correcciones de motor de investigación

3. Costos por candidato: `cost_R_i = (commission_roundtrip + slippage_ticks_roundtrip * tick_size * point_value) / (stop_points_i * point_value)`. Umbral individual `p_i > (1 + cost_R_i) / (1 + RR_i)`.
4. Resolver la tercera barrera mediante salida al horizonte y valorar su retorno realizado. Eliminar el descarte de casos sin TP/SL.
5. Intervalos de confianza con bootstrap **por días o sesiones**; incluir modelo nulo/permutado y baseline; eliminar accuracy como métrica principal.
6. Walk-forward mensual con purga de etiquetas y embargo temporal, sin reutilizar el test para ajustar parámetros.
7. No construir features a través de discontinuidades de sesión; validar continuidad hacia atrás y adelante.
8. Entrenar y evaluar sobre las **entradas candidatas reales de la estrategia**, no sobre cada vela y ambas direcciones.
9. Excluir simultaneidad largo/corto y posiciones superpuestas; registrar instrumento, contrato, zona horaria, período, proveedor de datos, hash de datos, semilla y versión del código.

## Cambios parciales publicados tras la revisión

- Ejecución automática **desactivada por defecto**.
- ATR de la vela previa para tamaño de stop; stop mínimo de 8 ticks (2 puntos en MNQ, aún requiere validación).
- Filtro EMA50 opcional y horario predeterminado 09:30–11:30 **según la zona horaria del gráfico**, no necesariamente Nueva York.
- README y COMPLIANCE ahora describen explícitamente el envío de órdenes.
- Documentación de V0.4/V0.5 deja claro que el repositorio no es reproducible.

**Estas modificaciones no resuelven los bloqueantes.** No existe todavía un control consolidado de riesgo por cuenta ni prueba de compilación en NinjaTrader. El cambio de horario predeterminado requiere revisar la zona horaria y DST de cada instalación.

## Criterios de aprobación

- CI verde desde clon limpio y pruebas documentadas, sin archivos externos.
- Backtest reproducible con datos trazables y costos por operación.
- Validación walk-forward con baseline, incertidumbre por sesiones y registro de candidatos ejecutables.
- NinjaTrader compila; prueba de paridad y fallos/reinicios documentada.
- Firma explícita de revisión del cliente; no declarar aprobación unilateralmente.
