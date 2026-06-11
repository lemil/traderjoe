# Propuesta 4: El Giro Moderno (LLMs + Quant)
## "Agentes Financieros Autónomos: Conectando LLMs con Motores de Optimización"

### 1. Visión General de la Solución
El LLM actúa como orquestador extrayendo restricciones en lenguaje natural y compilando un modelo matemático estricto en Python.

### 2. Roles de Agentes Especializados
* **NLP & Intent Extraction Agent:** Desarrolla el mapeo de lenguaje natural.
* **Quant Translation Agent:** Construye la sintaxis del problema de optimización.
* **Mathematical Validator Agent:** Inspecciona las matrices.
* **E2E Integration & QA Agent:** Diseña simulaciones de usuario.

### 3. Arquitectura del Software y Flujo de Datos
[ Usuario ] -> [ LLM Orchestrator ] -> [ Validador Pydantic ] -> [ Quant Engine (CVXPY) ] -> [ Reporte Final ]

### 4. Proceso de Implementación Paso a Paso
1. **Estructuración Semántica:** Definir modelo en Pydantic.
2. **Tool Calling:** Enlazar Pydantic al LLM.
3. **Compilación en CVXPY:** Traducir parámetros a variables de optimización.
4. **Ejecución:** Resolver y capturar errores de inviabilidad.

### 5. Suite de TDD
* **Test 1:** Extracción Precisa de Restricciones.
* **Test 2:** Rechazo Seguro de Infecciones de Prompts.
* **Test 3:** Manejo Elegante de Inviabilidad Matemática.
