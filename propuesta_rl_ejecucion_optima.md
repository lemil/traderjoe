# Propuesta 3: Reinforcement Learning en la Ejecución Óptima
## "Aprendizaje por Refuerzo (RL) para la Ejecución Óptima y Asignación de Activos"

### 1. Visión General de la Solución
Se construye un entorno compatible con OpenAI Gymnasium, donde un agente aprende la estrategia óptima maximizando las recompensas ajustadas por volatilidad.

### 2. Roles de Agentes Especializados
* **Environment Architect Agent:** Desarrolla el entorno Gymnasium.
* **RL Training Agent:** Configura e implementa la red neuronal.
* **Backtest Simulator Agent:** Construye el simulador histórico.
* **QA & Verification Agent:** Diseña pruebas unitarias de estados.

### 3. Arquitectura del Software y Flujo de Datos
[ Entorno Gymnasium (State Engine) ] <--> [ Agente RL (Stable-Baselines3) ]

### 4. Proceso de Implementación Paso a Paso
1. **Modelado del Espacio de Estados:** Precios históricos, ponderaciones.
2. **Modelado del Espacio de Acciones:** Vector continuo con capa Softmax.
3. **Diseño de Recompensa:** Ajuste por varianza y costos.
4. **Entrenamiento:** Ejecución de episodios.

### 5. Suite de TDD
* **Test 1:** Contención y Normalización del Espacio de Acciones.
* **Test 2:** Consistencia del Reset de Episodios.
* **Test 3:** Penalización por Fricción de Mercado.
