"""
Escaner de Cumplimiento Ley 21.719 - RetailPulse LATAM
App Streamlit (mismo stack que RetailPulse Latam) - analisis estatico real,
sin navegador headless. Reutiliza la logica de checks.py ya probada.
"""
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

import checks

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Escáner Ley 21.719 · RetailPulse LATAM",
    page_icon="🛡️",
    layout="centered",
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RetailPulseComplianceBot/1.0; +https://aovalle.com)"}
TIMEOUT = 12
CALENDLY_URL = "https://calendly.com/TU-USUARIO/auditoria-ley-21719"  # reemplaza con tu link real

COLOR_BRAND = "#B24958"       # burdeo/crimson de marca (logo AOVALLE.COM, CTA)
COLOR_BRAND_DARK = "#8F3A46"  # variante mas oscura para hover/acentos
COLOR_BG = "#FFFFFF"
COLOR_CARD = "#F2F2F2"
COLOR_BORDER = "#CCCCCC"
COLOR_TEXT = "#262626"
COLOR_MUTED = "#8A8A8A"
COLOR_AMBER = "#C97A2B"
COLOR_RED = "#B4432E"
COLOR_GREEN = "#3F7A5C"
COLOR_SLATE = "#5B6B78"

ESTADO_STYLE = {
    "Cumple": {"bg": "#E7F1EC", "fg": COLOR_GREEN, "icon": "✅"},
    "Parcial": {"bg": "#F7ECDD", "fg": COLOR_AMBER, "icon": "⚠️"},
    "No Cumple": {"bg": "#F5E6E2", "fg": COLOR_RED, "icon": "❌"},
    "No Verificable": {"bg": "#EAEEF0", "fg": COLOR_SLATE, "icon": "❔"},
}

SOLUTIONS = {
    "C1.1": "Configurar el gestor de tags (GTM u otro) condicionado al hook de un CMP, para que los scripts de tracking solo se disparen tras el consentimiento explícito.",
    "C1.2": "Rediseñar los botones del banner de cookies con la misma jerarquía visual para 'Aceptar' y 'Rechazar'.",
    "C1.3": "Implementar un widget o enlace persistente (ej. en el footer) para reabrir el panel de preferencias de cookies.",
    "C2.1": "Eliminar el atributo 'checked' por defecto en los checkboxes de suscripción/marketing.",
    "C2.2": "Separar el consentimiento de términos y condiciones del consentimiento para fines de marketing en checkboxes independientes.",
    "C3.1": "Revisar manualmente el flujo de checkout y limitar los campos obligatorios a los estrictamente necesarios.",
    "C3.2": "Mover el checkbox de consentimiento al mismo paso donde se captura el correo, antes de disparar automatizaciones de marketing.",
    "C4.1": "Reestructurar la política de privacidad con encabezados claros por sección y lenguaje simple.",
    "C4.2": "Incluir la Razón Social, RUT y domicilio legal del responsable del tratamiento de datos.",
    "C5.1": "Crear un formulario dedicado y trazable (conectado a un sistema de tickets) para solicitudes de derechos ARCO+.",
    "C5.2": "Establecer webhooks o procesos de eliminación unificada entre la plataforma de ecommerce y los sistemas internos.",
}

CATEGORY_TITLES = {
    "C1": ("Gestión de Cookies y Scripts", "🍪"),
    "C2": ("UX y Formularios de Captación", "🖱️"),
    "C3": ("Checkout y Minimización", "🛒"),
    "C4": ("Políticas y Términos Legal UX", "📄"),
    "C5": ("Canales de Derechos ARCO+", "👤"),
}

REQ_TEXT = {
    "C1.1": "Carga bloqueada previa de cookies no esenciales",
    "C1.2": "Banner con opción 'Rechazar Todo' al mismo nivel",
    "C1.3": "Revocación simple del consentimiento",
    "C2.1": "Casillas de suscripción desmarcadas por defecto",
    "C2.2": "Consentimiento separado por finalidad",
    "C3.1": "Minimización de datos en el Checkout",
    "C3.2": "Carritos abandonados con consentimiento previo",
    "C4.1": "Política redactada en lenguaje claro",
    "C4.2": "Identificación explícita del Responsable de Datos",
    "C5.1": "Formulario o canal dedicado para derechos ARCO",
    "C5.2": "Derecho al Olvido y Eliminación trazable",
}

PRIORIDAD = {
    "C1.1": "Alta", "C1.2": "Alta", "C1.3": "Media",
    "C2.1": "Alta", "C2.2": "Alta",
    "C3.1": "Media", "C3.2": "Alta",
    "C4.1": "Baja", "C4.2": "Alta",
    "C5.1": "Alta", "C5.2": "Media",
}

# ---------------------------------------------------------------------------
# ESTILOS
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
    .stApp {{ background-color: {COLOR_BG}; }}
    h1, h2, h3, h4, h5, h6 {{ font-family: Roboto, 'Roboto', serif; color: {COLOR_TEXT}; }}
    .stApp p, .stApp li, .stApp label, .stApp span {{ color: {COLOR_TEXT}; }}
    /* Expanders: Streamlit renders these as native <details>/<summary>.
       Force both background AND text so the 'open' state (which Streamlit
       darkens by default) never loses contrast. */
    .stApp details summary {{
        background-color: {COLOR_CARD} !important;
        color: {COLOR_TEXT} !important;
    }}
    .stApp details summary p, .stApp details summary span, .stApp details summary div {{
        color: {COLOR_TEXT} !important;
    }}
    .stApp details summary svg {{ fill: {COLOR_TEXT} !important; }}
    .stApp details {{ background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 10px; }}
    /* st.metric label/value */
    [data-testid="stMetricLabel"] p {{ color: {COLOR_MUTED} !important; }}
    [data-testid="stMetricValue"] {{ color: {COLOR_TEXT} !important; }}
    /* Black CTA button: force white text unconditionally, scoped only to
       this button so it never fights the global dark-text rule above. */
    .stLinkButton, .stLinkButton * {{ color: #FFFFFF !important; }}
    .badge {{
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 12px; font-weight: 600; padding: 4px 10px;
        border-radius: 999px;
    }}
    .rp-urgency {{
        background-color: #F7ECDD; border: 1px solid #EBD5AE; border-radius: 12px;
        padding: 12px 18px; color: #7A5218; font-size: 13.5px; margin-bottom: 16px;
    }}
    .rp-noverif {{
        background-color: #EAEEF0; border: 1px solid #D5DCDF; border-radius: 12px;
        padding: 12px 18px; color: #3D4C48; font-size: 13.5px; margin-bottom: 16px;
    }}
    .rp-cta {{
        background-color: {COLOR_BRAND}; border-radius: 16px; padding: 26px;
        color: #FFFFFF;
    }}
    div.stButton > button[kind="primary"] {{
        background-color: {COLOR_BRAND} !important; border-color: {COLOR_BRAND} !important;
    }}
    div.stButton > button[kind="primary"]:hover {{
        background-color: {COLOR_BRAND_DARK} !important; border-color: {COLOR_BRAND_DARK} !important;
    }}
    .stLinkButton > a {{
        background-color: #000000 !important; border-color: #000000 !important; color: #FFFFFF !important;
    }}
    .stLinkButton > a:hover {{
        background-color: #2A2A2A !important; border-color: #2A2A2A !important;
    }}
    .rp-cta-spacer {{ height: 18px; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------
def days_to_deadline():
    target = datetime(2026, 12, 1, tzinfo=timezone(timedelta(hours=-3)))
    now = datetime.now(timezone(timedelta(hours=-3)))
    delta = target - now
    days = max(0, delta.days)
    months = round(days / 30.44, 1)
    return days, months


def normalize_url(v: str) -> str:
    v = v.strip()
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    return v


def find_policy_url(soup, base_url):
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = a["href"].lower()
        if re.search(r"privacidad|privacy|datos\s+personales", text) or re.search(r"privacidad|privacy", href):
            return urljoin(base_url, a["href"])
    return None


def run_scan(url, status):
    status.write("Descargando y parseando el HTML público...")
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    status.write("Identificando la plataforma de ecommerce...")
    platform = checks.detect_platform(html, resp.headers)

    status.write("Buscando y evaluando la política de privacidad...")
    policy_url = find_policy_url(soup, url)
    policy_html = None
    if policy_url:
        try:
            policy_html = requests.get(policy_url, headers=HEADERS, timeout=TIMEOUT).text
        except requests.exceptions.RequestException:
            policy_html = None

    status.write("Evaluando categorías de cumplimiento...")
    results = {}
    results["C1.1"] = checks.check_c1_1(soup)
    results["C1.2"] = checks.check_c1_2(soup, html)
    results["C1.3"] = checks.check_c1_3(html)
    results["C2.1"], results["C2.2"] = checks.check_c2(soup)
    results["C3.1"], results["C3.2"] = checks.check_c3()
    results["C4.1"], results["C4.2"] = checks.check_c4(policy_html, policy_url)
    results["C5.1"], results["C5.2"] = checks.check_c5(html + (policy_html or ""))

    status.write("Generando reporte final...")

    weights = {"Cumple": 1.0, "Parcial": 0.5, "No Cumple": 0.0}
    evaluable = [r for r in results.values() if r["estado"] in weights]
    no_verificable = [r for r in results.values() if r["estado"] == "No Verificable"]
    reprobados = [(k, r) for k, r in results.items() if r["estado"] in ("No Cumple", "Parcial")]
    prioridades_altas = [k for k, r in reprobados if PRIORIDAD[k] == "Alta"]

    score = round(sum(weights[r["estado"]] for r in evaluable) / len(evaluable) * 100) if evaluable else None

    return {
        "url": url,
        "platform": platform,
        "score": score,
        "results": results,
        "summary": {
            "evaluados": len(results),
            "no_verificables": len(no_verificable),
            "reprobados": len(reprobados),
            "prioridades_altas": len(prioridades_altas),
        },
    }


def render_gauge(score):
    color = COLOR_SLATE if score is None else COLOR_RED if score < 50 else COLOR_AMBER if score < 80 else COLOR_GREEN
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score if score is not None else 0,
        number={"suffix": "%" if score is not None else "", "font": {"size": 40, "color": COLOR_TEXT}},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar": {"color": color, "thickness": 0.85},
            "bgcolor": "#E4E4E4",
            "borderwidth": 0,
        },
    ))
    fig.update_layout(
        height=220, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font={"color": COLOR_TEXT},
    )
    return fig


def estado_badge(estado):
    s = ESTADO_STYLE[estado]
    return f'<span class="badge" style="background-color:{s["bg"]};color:{s["fg"]}">{s["icon"]} {estado}</span>'


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
days, months = days_to_deadline()

st.markdown(f"""
<div style="text-align:center; padding: 10px 0 24px 0;">
  <p style="color:{COLOR_BRAND}; font-weight:600; letter-spacing:1px; font-size:13px; text-transform:uppercase;">
    <img src="https://retailpulse.cl/assets/img/logo-retailpulse.png" width="30%">
  </p>
  <h1 style="color:{COLOR_TEXT}; font-size:32px; margin-bottom:6px;">
    Escáner de Privacidad y Tracking Técnico<br/><span style="color:{COLOR_BRAND};">Ley 21.719</span>
  </h1>
  <p style="color:{COLOR_MUTED}; font-size:14.5px; max-width:480px; margin:0 auto;">
    Análisis técnico real sobre el HTML público de tu sitio. Evita multas de hasta
    <span style="color:{COLOR_BRAND}; font-weight:600;">20.000 UTM</span>.
    Quedan {months} meses para la fiscalización (1 dic. 2026).
  </p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------
col1, col2 = st.columns([4, 1.4])
with col1:
    url_input = st.text_input("URL", placeholder="www.tutienda.com", label_visibility="collapsed")
with col2:
    scan_clicked = st.button("Iniciar Escaneo", use_container_width=True, type="primary")

if "scan_data" not in st.session_state:
    st.session_state.scan_data = None

if scan_clicked:
    if not url_input.strip():
        st.error("Ingresa una URL para escanear.")
    else:
        target = normalize_url(url_input)
        try:
            with st.status("Escaneando sitio...", expanded=True) as status:
                data = run_scan(target, status)
                status.update(label="Análisis completo", state="complete")
            st.session_state.scan_data = data
        except requests.exceptions.RequestException as e:
            st.error(f"No se pudo acceder al sitio: {e}")
            st.session_state.scan_data = None

# ---------------------------------------------------------------------------
# RESULTADOS
# ---------------------------------------------------------------------------
data = st.session_state.scan_data
if data:
    score = data["score"]
    summary = data["summary"]
    platform = data["platform"]
    platform_label = platform["name"] or "tu plataforma actual"

    with st.container(border=True):
        gcol, tcol = st.columns([1, 1.6])
        with gcol:
            st.plotly_chart(render_gauge(score), use_container_width=True, config={"displayModeBar": False})
        with tcol:
            st.markdown(f"""
            <p style="color:{COLOR_BRAND}; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px;">🛡️ Cumplimiento Técnico</p>
            <h3 style="color:{COLOR_TEXT}; margin:2px 0 6px 0;">{f"{score}% de Cumplimiento Técnico" if score is not None else "Datos insuficientes"}</h3>
            <p style="color:{COLOR_TEXT}; font-size:13.5px; margin-bottom:2px;">Plataforma detectada: <b>{platform_label}</b>
              {f'<span style="color:{COLOR_MUTED};">(confianza {platform["confidence"]})</span>' if platform["confidence"] else ''}</p>
            <p style="color:{COLOR_MUTED}; font-size:12.5px;">El puntaje solo considera controles con evidencia suficiente.</p>
            """, unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Evaluados", summary["evaluados"])
        m2.metric("Reprobados", summary["reprobados"])
        m3.metric("Prioridad alta", summary["prioridades_altas"])
        m4.metric("No verificables", summary["no_verificables"])

    st.markdown(f"""
    <div class="rp-urgency">
      ⏰ <b>Tiempo restante para la vigencia total de la ley:</b> {days} días (menos de {months} meses) ·
      entra en vigor el 1 de diciembre de 2026.
    </div>
    """, unsafe_allow_html=True)

    if summary["no_verificables"] > 0:
        st.markdown(f"""
        <div class="rp-noverif">
          ❔ {summary['no_verificables']} de {summary['evaluados']} controles no se pudieron verificar con análisis
          estático (requieren revisión visual, sesión de compra real, o acceso a sistemas internos).
        </div>
        """, unsafe_allow_html=True)

    st.markdown("##### Hallazgos por categoría")
    for cat_id, (title, emoji) in CATEGORY_TITLES.items():
        item_ids = [k for k in data["results"] if k.startswith(cat_id)]
        fails = sum(1 for k in item_ids if data["results"][k]["estado"] in ("No Cumple", "Parcial"))
        with st.expander(f"{emoji} {title} — {len(item_ids)} controles · {fails} con hallazgos", expanded=(cat_id == "C1")):
            for item_id in item_ids:
                r = data["results"][item_id]
                st.markdown(f"""
                <div style="padding:10px 0; border-bottom:1px solid {COLOR_BORDER};">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                    <div>
                      <p style="font-weight:600; margin:0; color:{COLOR_TEXT};">{item_id} · {REQ_TEXT[item_id]}</p>
                      <p style="font-size:13px; color:#5B6B67; margin:6px 0 0 0;"><b>Evidencia:</b> {r['evidencia']}</p>
                      <p style="font-size:13px; color:#5B6B67; margin:4px 0 0 0;"><b>Recomendación:</b> {SOLUTIONS[item_id]}</p>
                    </div>
                    <div style="text-align:right; white-space:nowrap;">{estado_badge(r['estado'])}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="rp-cta">
      <h3 style="color:#FFFFFF; margin-top:0;">Estructura tu Plan de Remediación Técnica con un Consultor Especialista</h3>
      <p style="color:#F3DADE; font-size:13.5px;">
        Este reporte identificó brechas y puntos que requieren revisión frente a la Ley 21.719 en {platform_label}.
        Podemos ayudarte a adecuar tu tienda y reconfigurar tus etiquetas de tracking sin perder ventas.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rp-cta-spacer"></div>', unsafe_allow_html=True)
    st.link_button("📅 Agendar Auditoría de Validación (15 min)", CALENDLY_URL, use_container_width=True, type="primary")

st.markdown(
    f'<p style="text-align:center; color:{COLOR_MUTED}; font-size:11.5px; margin-top:24px;">'
    'Análisis estático sobre el HTML público · No requiere acceso a tu backend</p>',
    unsafe_allow_html=True,
)
