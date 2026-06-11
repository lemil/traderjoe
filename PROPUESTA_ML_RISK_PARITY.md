# Propuesta 2: Machine Learning para la Gestión de Riesgo
## "Predicción de Regímenes de Mercado y Portafolios Dinámicos con Árboles de Decisión"

### 1. Visión General de la Solución
Utiliza algoritmos de Machine Learning para clasificar el estado actual del mercado y, en función de esto, aplica una asignación basada en la Paridad de Riesgo (Risk Parity).

### 2. Roles de Agentes Especializados
* **Feature Engineer Agent:** Construye y limpia la matriz de características.
* **ML Modeling Agent:** Entrena, valida y serializa el clasificador.
* **Risk Quant Agent:** Diseña e implementa el motor numérico de Risk Parity.
* **QA & MLOps Agent:** Valida las pruebas de robustez del modelo.

### 3. Arquitectura del Software y Flujo de Datos
[ Market Data Ingest ] -> [ Feature Engineering ] -> [ ML Regime Classifier ] -> [ Risk Parity Solver ] -> [ Rebalanceo Dinámico ]

### 4. Proceso de Implementación Paso a Paso
1. **Ingeniería de Features:** Calcular ventanas rodantes.
2. **Entrenamiento:** Implementar partición con TimeSeriesSplit.
3. **Clasificación del Régimen:** Entrenar el modelo de ML.
4. **Optimización por Paridad de Riesgo:** Resolver los pesos óptimos.

### 5. Suite de TDD
* **Test 1:** Prevención Absoluta de Look-Ahead Bias.
* **Test 2:** Convergencia de Igualdad en Contribución de Riesgo.
* **Test 3:** Robustez ante Datos Faltantes.
