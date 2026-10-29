# Orquestación manual (ADR-000: sin orquestador, ejecución vía scripts/Makefile).

.PHONY: help install test ingest lint clean

help:
	@echo "install  - crea venv e instala requirements"
	@echo "test     - corre suite pytest (sección 13)"
	@echo "ingest   - corre pipeline de ingesta Fase 1 (data/ingest.py)"
	@echo "features - construye features Fase 2 (features/build.py)"
	@echo "analyze  - análisis de régimen Fase 3 (analysis/run.py)"
	@echo "analyze-garch-wf - régimen vs GARCH walk-forward (Fase 3)"
	@echo "report   - reporte de estado de mercado (reporting/report.py)"
	@echo "backtest - backtest exploratorio hipótesis ADR-007 (backtest/run.py)"
	@echo "backtest-v5 - backtest V5, confluencia multi-timeframe (ADR-011)"
	@echo "backtest-v3-be - V3 + gestion breakeven movil (ADR-012)"
	@echo "backtest-v5-be - V5 + gestion breakeven movil (ADR-012)"
	@echo "backtest-v3-trail - V3 + trailing stop por estructura (ADR-013)"
	@echo "backtest-v5-trail - V5 + trailing stop por estructura (ADR-013)"
	@echo "backtest-v6 - señal V1 + stop swing H1 (ADR-014)"
	@echo "backtest-v6-trail - V6 + trailing por estructura (ADR-014+013)"
	@echo "backtest-v7 - V7, jerarquia discrecional completa: MSS/CISD + Quarter Theory + BOS (ADR-015)"
	@echo "backtest-v8 - V8, igual V7 con stop en swing M5 en vez de H1 (ADR-015)"
	@echo "backtest-v7-confirmation-split - V7 exigiendo SOLO MSS o SOLO CISD por separado (ADR-015)"
	@echo "backtest-v9-combinations - V9 (MSS-only) combinado con target/stop ya explorados (ADR-015)"
	@echo "backtest-v10 - V9 (MSS-only) + SMT (6A vs 6N) como gate diario (ADR-016, requiere 6N ingerido)"
	@echo "validate-proxy - Compara el proxy AUDUSD contra el 6A real, correlacion y swings (ADR-006+018)"
	@echo "signal - Motor de senales en vivo: evalua si hay una senal V9 vigente ahora (ADR-017)"
	@echo "clean    - borra caches"

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

test:
	. .venv/bin/activate && pytest -v

# Ingesta reproducible. SYMBOLS/TIMEFRAMES se leen de config/settings.yaml.
ingest:
	. .venv/bin/activate && python -m data.ingest

# Feature engineering (Fase 2) sobre el crudo ya ingerido.
features:
	. .venv/bin/activate && python -m features.build

# Análisis de régimen + validación (Fase 3) sobre los features.
analyze:
	. .venv/bin/activate && python -m analysis.run

# Comparación régimen vs baseline GARCH(1,1) (Fase 3).
analyze-garch:
	. .venv/bin/activate && python -m analysis.run_garch

# Comparación régimen vs GARCH walk-forward (Fase 3, conclusión de referencia).
analyze-garch-wf:
	. .venv/bin/activate && python -m analysis.run_garch_wf

# Reporte de estado de mercado on-demand (Fase 3).
report:
	. .venv/bin/activate && python -m reporting.report

# Backtest exploratorio de la hipótesis ADR-007 (Fase 4).
backtest:
	. .venv/bin/activate && python -m backtest.run

# Backtest V2 (AMD, ADR-008) comparado con V1 (Fase 4).
backtest-v2:
	. .venv/bin/activate && python -m backtest.run_v2

# Backtest V3 (mecánica AMD en M5, ADR-009) (Fase 4).
backtest-v3:
	. .venv/bin/activate && python -m backtest.run_v3

# Backtest V4 (señal V3 + stop en swing H1, ADR-010) (Fase 4).
backtest-v4:
	. .venv/bin/activate && python -m backtest.run_v4

# Backtest V5 (confluencia multi-timeframe + equal highs/lows + salida jerárquica, ADR-011).
backtest-v5:
	. .venv/bin/activate && python -m backtest.run_v5

# Backtest V3 + gestión breakeven móvil (ADR-012).
backtest-v3-be:
	. .venv/bin/activate && python -m backtest.run_v3_be

# Backtest V5 + gestión breakeven móvil (ADR-012).
backtest-v5-be:
	. .venv/bin/activate && python -m backtest.run_v5_be

# Backtest V3 + trailing stop por estructura (ADR-013, regla real del usuario).
backtest-v3-trail:
	. .venv/bin/activate && python -m backtest.run_v3_trail

# Backtest V5 + trailing stop por estructura (ADR-013).
backtest-v5-trail:
	. .venv/bin/activate && python -m backtest.run_v5_trail

# Backtest V6: senal de V1 + stop de swing H1 (ADR-014).
backtest-v6:
	. .venv/bin/activate && python -m backtest.run_v6

# Backtest V6 + trailing por estructura (ADR-014 + ADR-013, combinacion pedida).
backtest-v6-trail:
	. .venv/bin/activate && python -m backtest.run_v6_trail

# Backtest V7: jerarquia discrecional completa (MSS/CISD + Quarter Theory + BOS, ADR-015).
backtest-v7:
	. .venv/bin/activate && python -m backtest.run_v7

# Backtest V8: igual V7, stop en swing M5 en vez de H1 (ADR-015, hipotesis 1).
backtest-v8:
	. .venv/bin/activate && python -m backtest.run_v8

# Backtest V7 restringido por fuente de confirmacion, MSS-only vs CISD-only (ADR-015).
backtest-v7-confirmation-split:
	. .venv/bin/activate && python -m backtest.run_v7_confirmation_split

# Backtest V9 (MSS-only) combinado con target/stop ya explorados (ADR-015).
backtest-v9-combinations:
	. .venv/bin/activate && python -m backtest.run_v9_combinations

# Backtest V10: V9 (MSS-only) + SMT (6A vs 6N) como gate diario (ADR-016). Requiere 6N ingerido (make ingest).
backtest-v10:
	. .venv/bin/activate && python -m backtest.run_v10

# Valida el proxy AUDUSD contra 6A real (ADR-006+018). Requiere 6A H1 ingerido (make ingest).
validate-proxy:
	. .venv/bin/activate && python -m analysis.validate_proxy

# Motor de senales en vivo (ADR-017). Corre make ingest primero para tener la barra de hoy.
signal:
	. .venv/bin/activate && python -m decision_engine.run_signal

lint:
	. .venv/bin/activate && python -m pyflakes data tests || true

clean:
	rm -rf .pytest_cache **/__pycache__

backtest-v12:
	. .venv/bin/activate && python -m backtest.run_v12

backtest-v13:
	. .venv/bin/activate && python -m backtest.run_v13

calibrar-bias:
	. .venv/bin/activate && python analysis_v13/calibrar_bias.py "$(NOTION_CSV)" $(YEAR)

backtest-v14:
	. .venv/bin/activate && python -m backtest.run_v14

backtest-v15:
	. .venv/bin/activate && python -m backtest.run_v15

# V16: calibración por reproducción del ledger (uso: make reproducir-ledger LEDGER=ruta.csv YEAR=2026) y backtest (solo si el hold-out acepta)
reproducir-ledger:
	. .venv/bin/activate && python analysis_v16/reproducir_ledger.py "$(LEDGER)" $(YEAR)

backtest-v16:
	. .venv/bin/activate && python -m backtest.run_v16
