"""
Motor de chequeos estaticos - Escaner Ley 21.719
Cada check documenta EXACTAMENTE que evidencia real encontro.
Si no hay evidencia suficiente para un veredicto, el estado es "No Verificable"
en vez de forzar un Cumple/No Cumple/Parcial sin base real.
"""
import re
from urllib.parse import urljoin

# ---------------------------------------------------------------------------
# Deteccion de plataforma
# ---------------------------------------------------------------------------
PLATFORM_SIGNATURES = [
    ("Shopify", [r"cdn\.shopify\.com", r"myshopify\.com", r"Shopify\.theme"]),
    ("Jumpseller", [r"jumpseller", r"jumpsellercdn"]),
    ("VTEX", [r"vtexassets\.com", r"vtex\.com\.br", r"vtexcommercestable"]),
    ("WooCommerce", [r"wp-content/plugins/woocommerce", r"woocommerce", r"wp-json/wc"]),
    ("Tiendanube/Nuvemshop", [r"tiendanube\.com", r"nuvemshop\.com\.br"]),
    ("Magento", [r"Mage\.Cookies", r"/static/version\d+/frontend"]),
]


def detect_platform(html: str, headers: dict) -> dict:
    generator = ""
    m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if m:
        generator = m.group(1)
        for name, _ in PLATFORM_SIGNATURES:
            if name.lower() in generator.lower():
                return {"name": name, "confidence": "alta", "evidencia": f"Meta tag generator: '{generator}'"}

    server_header = headers.get("server", "") + " " + headers.get("x-powered-by", "")
    for name, patterns in PLATFORM_SIGNATURES:
        for pat in patterns:
            if re.search(pat, html, re.I) or re.search(pat, server_header, re.I):
                return {"name": name, "confidence": "media", "evidencia": f"Firma detectada en el HTML: patron '{pat}'"}

    return {"name": None, "confidence": "baja", "evidencia": "No se identificaron firmas conocidas de plataforma en el HTML publico."}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
TRACKER_PATTERNS = {
    "Meta Pixel": [r"connect\.facebook\.net/.*?/fbevents\.js", r"fbq\(\s*['\"]init['\"]"],
    "Google Analytics / GA4": [r"googletagmanager\.com/gtag/js", r"gtag\(\s*['\"]config['\"]", r"google-analytics\.com/analytics\.js"],
    "Klaviyo": [r"klaviyo\.com", r"_klOnsite", r"KlaviyoSubscribe"],
    "TikTok Pixel": [r"analytics\.tiktok\.com"],
}

CMP_SIGNATURES = [
    "cookiebot", "onetrust", "cookieconsent", "complianz", "iubenda",
    "axeptio", "civicuk", "termly", "cookiehub",
]

CHECKOUT_PATH_HINTS = ["/checkout", "/cart", "/carrito", "/finalizar-compra"]


def find_scripts(soup):
    """Devuelve lista de (src_o_'inline', contenido_o_src, es_inline)"""
    out = []
    for tag in soup.find_all("script"):
        if tag.get("src"):
            out.append((tag.get("src"), tag.get("src"), False))
        elif tag.string:
            out.append(("inline", tag.string, True))
    return out


def is_gated_by_cmp(tag) -> bool:
    """Heuristica: un script queda 'gateado' si su type no es text/javascript
    (patron comun de CMPs: type='text/plain' data-category='marketing') o
    si tiene atributos data-cookie*/data-consent*/data-category."""
    t = (tag.get("type") or "").lower()
    if t and t not in ("text/javascript", "application/javascript", "module", ""):
        return True
    for attr in tag.attrs:
        if re.search(r"consent|cookie|category", attr, re.I):
            return True
    return False


def check_c1_1(soup):
    """Carga bloqueada previa de cookies no esenciales (analisis estatico: solo
    puede detectar si el script esta *gateado* en el marcado, no si realmente
    dispara antes del consentimiento en runtime)."""
    unconditional = []
    gated = []
    for tag in soup.find_all("script"):
        src = tag.get("src", "") or (tag.string or "")
        for tracker, patterns in TRACKER_PATTERNS.items():
            if tracker in ("Meta Pixel", "Google Analytics / GA4", "TikTok Pixel"):
                if any(re.search(p, src, re.I) for p in patterns):
                    if is_gated_by_cmp(tag):
                        gated.append(tracker)
                    else:
                        unconditional.append(tracker)

    if unconditional:
        return {
            "estado": "No Cumple",
            "evidencia": f"Se encontraron scripts de {', '.join(sorted(set(unconditional)))} en el HTML sin marcado de bloqueo por un gestor de consentimiento (type='text/plain' o atributos data-consent/data-category). Nota: esto es una senal estatica; no confirma que la cookie se escriba antes del clic, para eso se requiere inspeccion de red en vivo.",
            "confianza": "media",
        }
    if gated:
        return {
            "estado": "Cumple",
            "evidencia": f"Los scripts de {', '.join(sorted(set(gated)))} estan marcados con atributos propios de un CMP (bloqueo condicional), consistente con carga diferida hasta el consentimiento.",
            "confianza": "media",
        }
    return {
        "estado": "No Verificable",
        "evidencia": "No se detectaron scripts de tracking conocidos en el HTML estatico. Podrian cargarse dinamicamente via Google Tag Manager u otro contenedor, lo cual el analisis estatico no puede inspeccionar.",
        "confianza": "baja",
    }


def check_c1_2(soup, html):
    for sig in CMP_SIGNATURES:
        if sig in html.lower():
            return {
                "estado": "No Verificable",
                "evidencia": f"Se detecto un gestor de consentimiento conocido ('{sig}') en el sitio. Verificar si el boton 'Rechazar' tiene la misma jerarquia visual que 'Aceptar' requiere inspeccion visual/render, no disponible en analisis estatico.",
                "confianza": "media",
            }
    return {
        "estado": "No Verificable",
        "evidencia": "No se identifico un gestor de consentimiento (CMP) conocido en el HTML. Podria existir un banner de cookies construido a medida, que el analisis estatico no puede distinguir de su ausencia.",
        "confianza": "baja",
    }


def check_c1_3(html):
    patterns = [r"preferencias\s+de\s+cookies", r"configurar\s+cookies", r"gestionar\s+cookies", r"cookie\s+settings", r"privacy\s+preferences"]
    for p in patterns:
        if re.search(p, html, re.I):
            return {
                "estado": "Cumple",
                "evidencia": f"Se encontro texto/enlace relacionado a la gestion de preferencias de cookies (coincide con el patron '{p}').",
                "confianza": "alta",
            }
    return {
        "estado": "No Cumple",
        "evidencia": "No se encontro ningun enlace o texto en el HTML que permita revocar o modificar el consentimiento de cookies ya otorgado.",
        "confianza": "media",
    }


NEWSLETTER_KEYWORDS = re.compile(r"newsletter|suscri|ofertas|promocion|boletin|novedades", re.I)
TERMS_KEYWORDS = re.compile(r"t[eé]rminos|condiciones|terms", re.I)
MARKETING_KEYWORDS = re.compile(r"public(idad|itario)|marketing|comercial(es)?", re.I)


def check_c2(soup):
    checkboxes = soup.find_all("input", {"type": "checkbox"})
    if not checkboxes:
        return (
            {"estado": "No Verificable", "evidencia": "No se detectaron formularios con casillas de tipo checkbox en la pagina de inicio. El formulario de suscripcion podria estar en otra pagina o inyectado por JavaScript no visible al analisis estatico.", "confianza": "baja"},
            {"estado": "No Verificable", "evidencia": "Sin checkboxes detectados, no es posible evaluar si el consentimiento esta separado por finalidad.", "confianza": "baja"},
        )

    relevant = []
    for cb in checkboxes:
        context = " ".join([
            cb.get("id", ""), cb.get("name", ""),
            str(cb.find_parent("label").get_text(" ", strip=True)) if cb.find_parent("label") else "",
        ])
        if NEWSLETTER_KEYWORDS.search(context) or TERMS_KEYWORDS.search(context) or MARKETING_KEYWORDS.search(context):
            relevant.append((cb, context))

    if not relevant:
        return (
            {"estado": "No Verificable", "evidencia": "Se encontraron checkboxes en el HTML pero ninguno con contexto claro de suscripcion/newsletter/terminos.", "confianza": "baja"},
            {"estado": "No Verificable", "evidencia": "Sin checkboxes de suscripcion identificables, no se puede evaluar separacion de finalidades.", "confianza": "baja"},
        )

    checked_relevant = [c for c, ctx in relevant if c.has_attr("checked")]
    c2_1 = (
        {"estado": "No Cumple", "evidencia": f"{len(checked_relevant)} de {len(relevant)} checkbox(es) de suscripcion/marketing detectado(s) tienen el atributo 'checked' por defecto.", "confianza": "alta"}
        if checked_relevant else
        {"estado": "Cumple", "evidencia": f"Se detectaron {len(relevant)} checkbox(es) de suscripcion/marketing, ninguno con 'checked' por defecto.", "confianza": "alta"}
    )

    has_terms = any(TERMS_KEYWORDS.search(ctx) for _, ctx in relevant)
    has_marketing = any(MARKETING_KEYWORDS.search(ctx) for _, ctx in relevant)
    distinct_boxes = len(relevant)
    if has_terms and has_marketing and distinct_boxes >= 2:
        c2_2 = {"estado": "Cumple", "evidencia": "Se detectaron checkboxes distintos para terminos/condiciones y para fines de marketing.", "confianza": "media"}
    elif has_terms and has_marketing and distinct_boxes == 1:
        c2_2 = {"estado": "Parcial", "evidencia": "El mismo checkbox contiene lenguaje de terminos/condiciones y de marketing/publicidad simultaneamente.", "confianza": "media"}
    else:
        c2_2 = {"estado": "No Verificable", "evidencia": "El contexto textual disponible no permite determinar con certeza si el consentimiento esta separado por finalidad.", "confianza": "baja"}

    return c2_1, c2_2


def check_c3():
    note = "El checkout requiere una sesion de compra activa (carrito con productos) para ser accedido; el analisis estatico sobre la pagina publica no puede evaluar sus campos ni sus flujos de captura de email. Requiere revision manual o un modo de simulacion de carrito."
    return (
        {"estado": "No Verificable", "evidencia": note, "confianza": "baja"},
        {"estado": "No Verificable", "evidencia": note, "confianza": "baja"},
    )


def check_c4(policy_html, policy_url):
    if not policy_html:
        return (
            {"estado": "No Verificable", "evidencia": "No se encontro un enlace identificable a la politica de privacidad desde la pagina de inicio. Podria existir con otro nombre o estar solo en el footer via JavaScript.", "confianza": "baja"},
            {"estado": "No Verificable", "evidencia": "Sin acceso al texto de la politica de privacidad, no es posible verificar la identificacion del responsable de datos.", "confianza": "baja"},
        )

    text = re.sub(r"\s+", " ", policy_html)
    headers_count = policy_html.count("<h2") + policy_html.count("<h3")
    c4_1 = (
        {"estado": "Cumple", "evidencia": f"Se encontro la politica en {policy_url}, estructurada con {headers_count} encabezados de seccion.", "confianza": "media"}
        if headers_count >= 2 else
        {"estado": "Parcial", "evidencia": f"Se encontro la politica en {policy_url}, pero con poca estructura de encabezados ({headers_count} detectados), lo que dificulta la lectura.", "confianza": "media"}
    )

    rut_pattern = re.search(r"\d{1,2}\.\d{3}\.\d{3}[-.]?[\dkK]", text)
    razon_social = re.search(r"raz[oó]n\s+social", text, re.I)
    responsable = re.search(r"responsable\s+(del\s+)?tratamiento|responsable\s+de\s+datos", text, re.I)
    domicilio = re.search(r"domicilio\s+(legal|comercial)?", text, re.I)

    found = [n for n, v in [("RUT", rut_pattern), ("Razon Social", razon_social), ("Responsable de tratamiento", responsable), ("Domicilio", domicilio)] if v]
    if len(found) >= 3:
        c4_2 = {"estado": "Cumple", "evidencia": f"Se identificaron en el texto: {', '.join(found)}.", "confianza": "alta"}
    elif found:
        c4_2 = {"estado": "Parcial", "evidencia": f"Solo se identificaron: {', '.join(found)}. Faltan elementos de identificacion formal del responsable.", "confianza": "alta"}
    else:
        c4_2 = {"estado": "No Cumple", "evidencia": "No se encontro RUT, Razon Social, domicilio legal ni mencion explicita a un 'responsable del tratamiento' en el texto de la politica.", "confianza": "alta"}

    return c4_1, c4_2


def check_c5(full_html):
    arco_pattern = re.search(r"derechos?\s+arco", full_html, re.I)
    ticket_form = re.search(r"formulario\s+de\s+solicitud|solicitud\s+de\s+datos|data\s+request\s+form", full_html, re.I)
    only_mailto = re.search(r'href=["\']mailto:', full_html, re.I) is not None

    if arco_pattern and ticket_form:
        c5_1 = {"estado": "Cumple", "evidencia": "Se encontro mencion explicita a 'derechos ARCO' junto a un formulario de solicitud dedicado.", "confianza": "media"}
    elif arco_pattern or ticket_form:
        c5_1 = {"estado": "Parcial", "evidencia": "Se encontro un canal de contacto relacionado, pero sin confirmar que sea un formulario dedicado y trazable para derechos ARCO.", "confianza": "baja"}
    elif only_mailto:
        c5_1 = {"estado": "No Cumple", "evidencia": "El unico canal de contacto detectado es un enlace 'mailto:', sin formulario ni sistema de tickets identificable.", "confianza": "media"}
    else:
        c5_1 = {"estado": "No Verificable", "evidencia": "No se identifico ningun canal de contacto ni mencion a derechos ARCO en las paginas analizadas.", "confianza": "baja"}

    c5_2 = {
        "estado": "No Verificable",
        "evidencia": "La trazabilidad de eliminacion entre la plataforma de ecommerce y sistemas internos (CRM, ERP, herramientas de marketing) es informacion de arquitectura interna del cliente; no es verificable desde un analisis externo del sitio publico.",
        "confianza": "baja",
    }
    return c5_1, c5_2
