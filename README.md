# Escáner de Cumplimiento Ley 21.719 — versión Streamlit

Mismo motor de análisis estático real (ver `checks.py`), pero como app
Streamlit en vez de FastAPI + React — para desplegar junto a RetailPulse
Latam con el mismo flujo de trabajo que ya usas.

## Correr en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar vía Git en Streamlit Community Cloud

1. Sube esta carpeta (`app.py`, `checks.py`, `requirements.txt`) a un repo
   de GitHub — puede ser el mismo repo de RetailPulse Latam en una subcarpeta,
   o uno nuevo.
2. Entra a [share.streamlit.io](https://share.streamlit.io) → "New app".
3. Conecta el repo, elige la rama y apunta al archivo principal
   (`app.py`; si está en una subcarpeta, indica la ruta completa, ej.
   `escaner-ley-21719/app.py`).
4. Deploy. Cada `git push` a la rama configurada redespliega automáticamente
   — es el mismo flujo que usas para tus otras apps Streamlit.

## Antes de publicar

- Reemplaza `CALENDLY_URL` en `app.py` por tu link real de agendamiento.
- Si quieres, puedes fijar el dominio en `share.streamlit.io` con un nombre
  propio (ej. `retailpulse-ley21719.streamlit.app`), igual que
  `retailpulse-chile.streamlit.app`.

## Qué mantiene de la versión FastAPI/React

- La misma lógica de chequeos (`checks.py`, sin cambios) — plataforma,
  trackers, CMP, checkboxes, política de privacidad, canal ARCO.
- El mismo criterio de honestidad: donde no hay evidencia estática
  suficiente, el estado es **"No Verificable"**, no un veredicto inventado.
- El mismo cálculo de score (solo sobre controles evaluables).

## Qué cambia visualmente

- El gauge radial ahora es un `plotly.graph_objects.Indicator` en vez de un
  SVG animado — mismo lenguaje visual que ya usas en tus otras herramientas
  con Plotly.
- Las categorías usan `st.expander` en vez de un acordeón custom — mismo
  comportamiento (clic para expandir), estética nativa de Streamlit.
- El CTA final usa `st.link_button` apuntando a Calendly, en vez de un botón
  que simula "agendado" — así el clic sí lleva a una acción real de
  conversión, no a un estado ficticio.

## Nota sobre el frontend React anterior

Si más adelante quieres volver a un lead magnet embebible en tu landing
(con el diseño Dark Teal a medida), el archivo `escaner-ley-21719.jsx` y el
backend FastAPI (`scanner_api/`) siguen siendo válidos — no se eliminaron,
solo quedan como alternativa si cambias de arquitectura.
