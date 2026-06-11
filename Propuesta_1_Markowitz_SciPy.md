# Propuesta 1: De Markowitz a SciPy
## "Más allá del Loop: Optimización de Portafolios a Gran Escala con Vectorización en Python"

### 1. Visión General de la Solución
Esta solución implementa la Teoría Moderna de Portafolio (MPT) optimizando la asignación de activos mediante programación cuadrática. El objetivo central es maximizar el Ratio de Sharpe o minimizar la varianza para un universo de miles de activos financieros, eliminando por completo los bucles explícitos de Python (`for`, `while`) dentro de la función objetivo para garantizar rendimiento de grado institucional.

### 2. Roles de Agentes Especializados
* **Quant Math Agent:** Diseña las funciones matemáticas vectorizadas.
* **Data Engineer Agent:** Construye la capa de ingesta optimizada.
* **Core Software Engineer Agent:** Implementa la integración con los solvers de `SciPy.optimize`.
* **QA Automation Agent:** Desarrolla la suite completa de pruebas unitarias bajo un enfoque TDD riguroso.

### 3. Arquitectura del Software y Flujo de Datos
[ Capa de Datos ] -> [ Ingestión y Preprocesamiento ] -> [ Quant Core Engine ] -> [ Capa de Optimización ] -> [ Capa de Métricas y Output ]

### 4. Proceso de Implementación Paso a Paso
1. **Fase de Ingesta:** Cargar series temporales de precios de cierre ajustados.
2. **Fase de Estimación Robustecida:** Implementar la contracción de Ledoit-Wolf.
3. **Fase de Formulación del Solver:** Definir la función de pérdida a minimizar.
4. **Fase de Restricciones:** Configurar el solver `SLSQP` con restricciones.

### 5. Suite de TDD (Test-Driven Development)
* **Test 1:** Simetría y Definición Positiva de la Matriz de Covarianza.
* **Test 2:** Invariancia de Restricciones del Solver.
* **Test 3:** Rendimiento de Vectorización
