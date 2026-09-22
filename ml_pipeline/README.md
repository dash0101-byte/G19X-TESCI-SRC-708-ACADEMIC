# Machine Learning Pipeline - Sistema Inteligente de Lead Scoring (PluriOne)

Módulo especializado en el ciclo de vida de modelos predictivos y algoritmos de scoring dinámico.

## Componentes y Arquitectura (Bloque 2):
1. **Generador y Preprocesador de Datos**: Limpieza, encoding categórico e imputación sin fugas de datos (Data Leakage).
2. **Ingeniería de Características (Feature Engineering)**:
   - Factores demográficos/firmográficos (Cargo C-Level, tamaño de empresa, industria clave).
   - Factores de comportamiento y velocidad (Frecuencia de visitas, apertura de correos, descarga de contenido).
   - Factor de decaimiento exponencial temporal: $Score_{decay} = Score_{base} \cdot e^{-\lambda \Delta t}$.
3. **Entrenamiento y Comparación de Modelos**:
   - Modelos base: Regresión Logística, Random Forest, XGBoost Classifier.
   - Evaluación: ROC-AUC, F1-Score, Matriz de Confusión y Curva de Calibración de Probabilidades.
4. **Adaptadores Azure ML & Mock Local**:
   - Inferencia local con fallback cero costo ($0 USD).
   - Contrato compatible con endpoints administrados de Azure Machine Learning.
