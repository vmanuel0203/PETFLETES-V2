"""Estilos y componentes HTML de PetFletes (verde bosque, naranja y crema)."""
from datetime import datetime
from html import escape

import streamlit as st

CATEGORIAS = {
    "Alimento": ("🍖", "#FDE7C8"),
    "Higiene": ("🧼", "#D9F0E6"),
    "Juguetes": ("🧸", "#FBE0E0"),
    "Accesorios": ("🎀", "#E3E8FB"),
    "Salud": ("💊", "#EAF6D5"),
}
TONOS_ESTADO = {
    "Esperando tienda": "amarillo", "Buscando repartidor": "amarillo", "Tiempo agotado": "naranja",
    "Aceptado": "verde", "Entregado": "verde", "Cancelado": "rojo",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
.stApp, .stApp button, .stApp input, .stApp textarea { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
header[data-testid="stHeader"] { background: transparent; height: 0; visibility: hidden; }
#MainMenu, footer { visibility: hidden; }
section[data-testid="stSidebar"] { display: none; }
.block-container { max-width: 1180px; padding: 1rem 1.25rem 4rem; }
h1, h2, h3, h4 { color: #0E4F39; font-weight: 800; letter-spacing: -0.01em; }

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button, .stLinkButton > a {
  border-radius: 999px; font-weight: 700; }
.stButton > button[kind="secondary"], .stDownloadButton > button, .stLinkButton > a {
  border: 1.5px solid #14664A; color: #14664A; background: #fff; }

[class*="st-key-card_"], [class*="st-key-cardsel_"] {
  background: #fff; border: 1px solid #EBDFCD; border-radius: 20px; padding: 1rem 1.1rem;
  box-shadow: 0 4px 14px rgba(14, 79, 57, 0.06); }
[class*="st-key-cardsel_"] { border: 2px solid #14664A; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; border-color: #EBDFCD; }

.st-key-topbar { background: #fff; border-radius: 22px; padding: 0.55rem 1rem;
  box-shadow: 0 4px 16px rgba(14, 79, 57, 0.08); margin-bottom: 0.7rem; }
.st-key-topbar [data-testid="stHorizontalBlock"],
[class*="st-key-card_linea_"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.4rem; align-items: center; }
.st-key-topbar [data-testid="stColumn"], .st-key-topbar [data-testid="column"],
[class*="st-key-card_linea_"] [data-testid="stColumn"], [class*="st-key-card_linea_"] [data-testid="column"] { min-width: 0 !important; }
.st-key-card_resumen { position: sticky; top: 0.8rem; }

.pf-logo { font-weight: 800; font-size: 1.35rem; color: #0E4F39; white-space: nowrap; }
.pf-logo span { color: #F97316; }
.pf-hero { background: linear-gradient(120deg, #14664A 0%, #0E4F39 100%); color: #fff; border-radius: 26px;
  padding: 2.2rem; position: relative; overflow: hidden; margin-bottom: 1rem; }
.pf-hero h1 { color: #fff; font-size: 2.3rem; line-height: 1.15; margin: 0 0 0.6rem; max-width: min(36rem, calc(100% - 7.5rem)); }
.pf-hero p { color: #D6EBE1; margin: 0; max-width: min(32rem, calc(100% - 7.5rem)); }
.pf-badge { display: inline-block; background: #F6C945; color: #0E4F39; font-weight: 800; border-radius: 999px;
  padding: 0.25rem 0.8rem; font-size: 0.8rem; margin-bottom: 0.8rem; }
.pf-emoji { position: absolute; right: 1.6rem; bottom: 0.4rem; font-size: 6rem; opacity: 0.95; }

.pf-kpi { background: #fff; border: 1px solid #EBDFCD; border-radius: 18px; padding: 0.8rem 1rem; }
.pf-kpi .l { font-size: 0.76rem; color: #5E7A6E; font-weight: 600; }
.pf-kpi .v { font-size: 1.55rem; font-weight: 800; color: #0E4F39; line-height: 1.2; }
.pf-kpi .d { font-size: 0.72rem; color: #8A9A92; }

.pf-chip { display: inline-block; border-radius: 999px; padding: 0.15rem 0.65rem; font-size: 0.75rem;
  font-weight: 700; margin: 0 0.25rem 0.25rem 0; }
.pf-chip.verde { background: #D9F0E6; color: #0E4F39; } .pf-chip.naranja { background: #FFE3CC; color: #B24A00; }
.pf-chip.amarillo { background: #FBEFC2; color: #7A5B00; } .pf-chip.rojo { background: #FBDADA; color: #9B1C1C; }
.pf-chip.gris { background: #EFEAE1; color: #5B6B64; }

.pf-ico { width: 64px; height: 64px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-size: 30px; margin-bottom: 0.5rem; }
.pf-nombre { font-weight: 700; color: #123D2E; line-height: 1.25; min-height: 2.5em; }
.pf-meta { font-size: 0.78rem; color: #6B7F75; margin: 0.15rem 0 0.4rem; }
.pf-precio { font-size: 1.3rem; font-weight: 800; color: #14664A; margin-bottom: 0.3rem; }
.pf-tarifa { font-size: 1.7rem; font-weight: 800; color: #F97316; line-height: 1.1; }
.pf-fila { display: flex; justify-content: space-between; gap: 0.6rem; padding: 0.28rem 0; font-size: 0.92rem; color: #35574A; }
.pf-fila.fuerte { font-weight: 800; color: #0E4F39; border-top: 1px dashed #D9C9B0; margin-top: 0.3rem; padding-top: 0.5rem; }
.pf-total { display: flex; justify-content: space-between; align-items: center; font-weight: 700; color: #0E4F39; }
.pf-total b { font-size: 1.8rem; color: #F97316; }
.pf-sec { display: flex; align-items: center; gap: 0.6rem; font-weight: 800; color: #0E4F39; font-size: 1.1rem; margin: 1rem 0 0.5rem; }
.pf-sec i { font-style: normal; width: 1.7rem; height: 1.7rem; border-radius: 50%; background: #F97316; color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-size: 0.9rem; }

.pf-pasos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; margin: 0.2rem 0 1.2rem; }
.pf-paso { background: #fff; border: 1px solid #EBDFCD; border-radius: 18px; padding: 0.9rem 1rem; }
.pf-paso i { font-style: normal; width: 1.6rem; height: 1.6rem; border-radius: 50%; background: #F97316; color: #fff;
  display: inline-flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem; }
.pf-paso b { display: block; color: #0E4F39; margin: 0.45rem 0 0.15rem; }
.pf-paso span { font-size: 0.82rem; color: #5E7A6E; }
.pf-subtitulo { font-weight: 800; color: #0E4F39; font-size: 1.05rem; margin: 0.4rem 0 0.7rem; }
.pf-cats { display: flex; gap: 1.1rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
.pf-cat { text-align: center; font-size: 0.78rem; font-weight: 700; color: #35574A; }
.pf-cat span { display: flex; width: 58px; height: 58px; border-radius: 50%; align-items: center;
  justify-content: center; font-size: 27px; margin: 0 auto 0.3rem; }
.st-key-card_auth [data-testid="stForm"] { border: none; padding: 0; }
.st-key-card_auth [data-baseweb="input"] { background: #FBF6EE; border: 1.5px solid #E3D5BF; border-radius: 12px; }
.st-key-card_auth [data-baseweb="input"]:focus-within { border-color: #14664A; }
.st-key-card_auth [data-baseweb="base-input"] { background: transparent; }
.st-key-card_auth { padding: 1.4rem 1.5rem; }

.pf-banner { background: linear-gradient(120deg, #14664A 0%, #0E4F39 100%); border-radius: 26px;
  padding: 1.8rem 0 1.5rem; color: #fff; overflow: hidden; margin-bottom: 1rem; }
.pf-banner .cab { padding: 0 1.8rem; }
.pf-banner .cab h1 { color: #fff; font-size: 2rem; line-height: 1.15; margin: 0.2rem 0 0.4rem; }
.pf-banner .cab p { color: #D6EBE1; margin: 0 0 1.1rem; max-width: 40rem; }
.pf-carrusel { overflow: hidden; padding: 0 1.2rem; }
.pf-pista { display: flex; width: max-content; }
.pf-pista.animada { animation: pf-desliza 70s linear infinite; }
.pf-carrusel:hover .pf-pista { animation-play-state: paused; }
@keyframes pf-desliza { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.pf-social { flex: 0 0 300px; margin-right: 1rem; background: #fff; color: #123D2E; border-radius: 20px;
  padding: 1rem 1.1rem; white-space: normal; box-sizing: border-box; display: flex; flex-direction: column; }
.pf-social b { display: block; margin: 0.5rem 0 0.25rem; color: #0E4F39; line-height: 1.25; }
.pf-social .txt { font-size: 0.85rem; color: #35574A; margin: 0 0 0.7rem; flex: 1; }
.pf-social .est { color: #F5A000; letter-spacing: 2px; font-size: 1.05rem; }
.pf-social .cita { font-size: 1rem; font-weight: 600; color: #0E4F39; line-height: 1.35; margin: 0.4rem 0 0.7rem; flex: 1; }
.pf-social .pie { display: flex; align-items: center; gap: 0.5rem; font-size: 0.78rem; color: #6B7F75; }
.pf-avatar { width: 1.7rem; height: 1.7rem; border-radius: 50%; background: #F97316; color: #fff; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; }
.pf-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.8rem; margin: 0.2rem 0 1.2rem; }
[data-testid="stPopoverBody"] { min-width: min(22rem, 88vw); }
[data-testid="stPopoverBody"] [data-testid="stForm"] { border: none; padding: 0; }
[data-testid="stPopoverBody"] [data-baseweb="input"] { background: #FBF6EE; border: 1.5px solid #E3D5BF; border-radius: 12px; }
[data-testid="stPopoverBody"] [data-baseweb="input"]:focus-within { border-color: #14664A; }
[data-testid="stPopoverBody"] [data-baseweb="base-input"] { background: transparent; }
.pf-hero.pf-hero-simple h1 { max-width: 36rem; }
.pf-hero.pf-hero-simple p { max-width: 34rem; }
@media (prefers-reduced-motion: reduce) {
  .pf-pista.animada { animation: none; } .pf-carrusel { overflow-x: auto; }
}

@media (max-width: 640px) {
  .pf-banner .cab { padding: 0 1.1rem; } .pf-banner .cab h1 { font-size: 1.45rem; }
  .pf-social { flex-basis: 250px; }
  .pf-hero h1, .pf-hero p { max-width: calc(100% - 4.2rem); }
  .pf-solo-desktop { display: none; }
  .block-container { padding: 0.6rem 0.7rem 4rem; }
  .pf-hero { padding: 1.3rem; } .pf-hero h1 { font-size: 1.55rem; } .pf-emoji { font-size: 3.4rem; }
  .pf-logo { font-size: 1.1rem; }
}
"""


def inyectar_css():
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

CSS_CRISTAL = """
html, body { background: #2A2018 !important; }
/* Contenido más angosto (como la plantilla): deja a la vista el repartidor de la derecha */
.block-container, [data-testid="stMainBlockContainer"] { max-width: clamp(720px, 62vw, 1180px) !important; }
@media (max-width: 900px) { .block-container, [data-testid="stMainBlockContainer"] { max-width: 100% !important; } }
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] { background: transparent !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #FFFFFF !important; text-shadow: 0 1px 6px rgba(0,0,0,.35); }
.stApp [data-testid="stMarkdownContainer"] p, .stApp label, .stApp label p { color: #F4EFE8; }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: #E3DCD2 !important; }
.stApp a { color: #9ED8FF !important; }
.pf-logo { color: #FFFFFF; text-shadow: 0 1px 6px rgba(0,0,0,.45); }

/* Tarjetas de cristal esmerilado */
.pf-hero { background: linear-gradient(135deg, rgba(20,102,74,.90), rgba(14,79,57,.80)); border: 1px solid rgba(255,255,255,.22);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); box-shadow: 0 20px 50px rgba(0,0,0,.28); }
.pf-subtitulo { color: #FFFFFF; text-shadow: 0 1px 6px rgba(0,0,0,.6); }
.pf-paso { background: rgba(38,30,24,.46); border: 1px solid rgba(255,255,255,.28);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0,0,0,.2); }
.pf-paso b { color: #FFFFFF; } .pf-paso span { color: #F0E9DF; }
.pf-cat { color: #FFFFFF; text-shadow: 0 1px 5px rgba(0,0,0,.7); }
.pf-cat span { border: 2px solid rgba(255,255,255,.7); box-shadow: 0 6px 16px rgba(0,0,0,.25); }
.st-key-card_auth { background: rgba(24,26,31,.68) !important; border: 1px solid rgba(255,255,255,.24) !important; border-radius: 24px !important;
  backdrop-filter: blur(16px) saturate(1.15); -webkit-backdrop-filter: blur(16px) saturate(1.15); box-shadow: 0 24px 60px rgba(0,0,0,.38) !important; }

/* Campos de texto: fondo oscuro y letras claras (varios selectores porque Streamlit cambia sus nombres internos) */
.st-key-card_auth [data-testid="stTextInputRootElement"], .st-key-card_auth [data-baseweb="input"],
.st-key-card_auth [data-baseweb="base-input"], .st-key-card_auth div:has(> input) {
  background: rgba(14,16,20,.86) !important; border-radius: 12px; }
.st-key-card_auth [data-testid="stTextInputRootElement"], .st-key-card_auth [data-baseweb="input"] {
  border: 1.5px solid rgba(255,255,255,.18) !important; }
.st-key-card_auth [data-testid="stTextInputRootElement"]:focus-within, .st-key-card_auth [data-baseweb="input"]:focus-within {
  border-color: #2FB67C !important; }
.st-key-card_auth input, .st-key-card_auth textarea {
  background: rgba(14,16,20,.86) !important; color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; caret-color: #FFFFFF; }
.st-key-card_auth input::placeholder, .st-key-card_auth textarea::placeholder { color: #9AA3AD !important; -webkit-text-fill-color: #9AA3AD !important; }
.st-key-card_auth input:-webkit-autofill { box-shadow: 0 0 0 1000px #15181D inset !important; -webkit-text-fill-color: #FFFFFF !important; }
.st-key-card_auth [data-testid="stTextInput"] button, .st-key-card_auth [data-testid="stTextInput"] button svg { color: #C9D0D6 !important; background: transparent !important; }
.st-key-card_auth [data-baseweb="select"] > div { background: rgba(14,16,20,.86) !important; border: 1.5px solid rgba(255,255,255,.18) !important; color: #FFFFFF !important; }
.st-key-card_auth [data-baseweb="select"] * { color: #FFFFFF !important; }

/* Pestañas */
.st-key-card_auth button[data-baseweb="tab"] p { color: #E8E2D8; }
.st-key-card_auth button[data-baseweb="tab"][aria-selected="true"] p { color: #F97316; }
.st-key-card_auth [data-baseweb="tab-highlight"] { background-color: #F97316 !important; }
.st-key-card_auth [data-baseweb="tab-border"] { background-color: rgba(255,255,255,.18) !important; }

/* Selector de rol (se selecciona por la clave del widget) */
.st-key-rol_auth button { background: rgba(20,22,27,.80) !important; border: 1px solid rgba(255,255,255,.22) !important; color: #EDE7DD !important; }
.st-key-rol_auth button * { color: inherit !important; }
.st-key-rol_auth button:hover { border-color: #F97316 !important; }
.st-key-rol_auth button[data-testid="stBaseButton-pillsActive"], .st-key-rol_auth button[kind="pillsActive"],
.st-key-rol_auth button[aria-checked="true"], .st-key-rol_auth button[aria-pressed="true"] {
  background: rgba(60,36,16,.85) !important; border-color: #F97316 !important; color: #FFC18F !important; }

/* Botón secundario (cuenta demo) */
.st-key-card_auth button[data-testid="stBaseButton-secondary"], .st-key-card_auth button[kind="secondary"] {
  background: rgba(255,255,255,.06); border: 1.5px solid rgba(255,255,255,.40); color: #FFFFFF; }

@media (max-width: 640px) { .st-key-card_auth { padding: 1rem !important; } }
"""


def inyectar_fondo_ingreso():
    """Pantalla de ingreso: ilustración a pantalla completa + tarjetas de cristal (al entrar vuelve el tema claro)."""
    import fondo
    fondo_css = ('.stApp { background: linear-gradient(rgba(0,0,0,.08), rgba(0,0,0,.14)), '
                 f'url("{fondo.url_fondo()}") center bottom / cover no-repeat fixed !important; }}')
    st.markdown(f"<style>{CSS_CRISTAL}\n{fondo_css}</style>", unsafe_allow_html=True)


def html(contenido):
    st.markdown(contenido, unsafe_allow_html=True)


def colones(monto):
    return "₡{:,.0f}".format(monto)


def logo():
    return '<div class="pf-logo">🐾 Pet<span>Fletes</span></div>'


def hero(insignia, titulo, texto, emoji="🐶"):
    """Tarjeta verde de bienvenida. Con emoji="" no lleva ilustración y el texto ocupa todo el ancho."""
    clase = "pf-hero" if emoji else "pf-hero pf-hero-simple"
    arte = f'<div class="pf-emoji">{emoji}</div>' if emoji else ""
    return (f'<div class="{clase}"><span class="pf-badge">{escape(insignia)}</span>'
            f'<h1>{escape(titulo)}</h1><p>{escape(texto)}</p>{arte}</div>')


def kpi(etiqueta, valor, detalle=""):
    extra = f'<div class="d">{escape(str(detalle))}</div>' if detalle else ""
    return (f'<div class="pf-kpi"><div class="l">{escape(etiqueta)}</div>'
            f'<div class="v">{escape(str(valor))}</div>{extra}</div>')


def chip(texto, tono="gris"):
    return f'<span class="pf-chip {tono}">{escape(str(texto))}</span>'


def chip_estado(estado):
    return chip(estado, TONOS_ESTADO.get(estado, "gris"))


def seccion(numero, titulo):
    return f'<div class="pf-sec"><i>{numero}</i>{escape(titulo)}</div>'


def fila(etiqueta, valor, fuerte=False):
    clase = "pf-fila fuerte" if fuerte else "pf-fila"
    return f'<div class="{clase}"><span>{escape(str(etiqueta))}</span><span>{escape(str(valor))}</span></div>'


def total(etiqueta, valor):
    return f'<div class="pf-total"><span>{escape(etiqueta)}</span><b>{escape(str(valor))}</b></div>'


def tarjeta_producto(p, mostrar_tienda=False):
    emoji, color = CATEGORIAS.get(p.get("categoria") or "Accesorios", ("🐾", "#F7E7CF"))
    tienda = f'<div class="pf-meta">🏪 {escape(p["tienda_nombre"])}</div>' if mostrar_tienda else ""
    return (f'<div class="pf-ico" style="background:{color}">{emoji}</div>'
            f'<div class="pf-nombre">{escape(p["nombre"])}</div>{tienda}'
            f'<div class="pf-meta">{escape(p.get("categoria") or "")} · {p["peso_kg"]:g} kg</div>'
            f'<div class="pf-precio">{colones(p["precio"])}</div>')


def tarjeta_tienda(t, km):
    return (f'<div class="pf-ico" style="background:#D9F0E6">🏪</div>'
            f'<div class="pf-nombre">{escape(t["nombre"])}</div>'
            f'<div class="pf-meta">📍 {escape(t["direccion"])}</div>'
            f'{chip(f"a {km:.1f} km", "verde")}'
            f'<div class="pf-meta">{escape(t.get("descripcion") or "")}</div>')


def tarjeta_viaje(p, cliente_txt, restante_txt):
    km = f"{p['distancia_km']:g} km"
    peso = f"{p['peso_total']:g} kg"
    ofertas = f"{p['n_ofertas']} ofertas"
    return (f'<div class="pf-meta">Pedido #{p["id"]} · {escape(p["tienda_nombre"])}</div>'
            f'<div class="pf-tarifa">{colones(p["oferta"])}</div>'
            f'<div class="pf-nombre" style="min-height:0">📍 {escape(p["destino_nombre"])}</div>'
            + chip(km, "verde") + chip(peso, "gris") + chip("⏳ " + restante_txt, "amarillo") + chip(ofertas, "gris")
            + (chip("📦 Listo para recoger", "verde") if p.get("listo_en") else "")
            + f'<div class="pf-meta">Cliente: {escape(p["cliente_nombre"])} · {escape(cliente_txt)}</div>')


def pasos(items):
    """Tarjetas numeradas 'cómo funciona'. items: [(titulo, texto)]."""
    celdas = "".join(f'<div class="pf-paso"><i>{n}</i><b>{escape(t)}</b><span>{escape(x)}</span></div>'
                     for n, (t, x) in enumerate(items, 1))
    return f'<div class="pf-pasos">{celdas}</div>'


def categorias_tira():
    celdas = "".join(f'<div class="pf-cat"><span style="background:{color}">{emoji}</span>{escape(nombre)}</div>'
                     for nombre, (emoji, color) in CATEGORIAS.items())
    return f'<div class="pf-cats">{celdas}</div>'


def subtitulo(texto):
    return f'<div class="pf-subtitulo">{escape(texto)}</div>'


def hace(fecha):
    """'hace 5 min', 'hace 3 h', 'hace 2 d' a partir de 'YYYY-MM-DD HH:MM:SS'."""
    seg = max(0, (datetime.now() - datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")).total_seconds())
    if seg < 60:
        return "justo ahora"
    if seg < 3600:
        return f"hace {int(seg // 60)} min"
    if seg < 86400:
        return f"hace {int(seg // 3600)} h"
    return f"hace {int(seg // 86400)} d"


ICONOS_PUBLICACION = {"Oferta de tienda": "🏷️", "Tip de mascotas": "💡", "Pregunta": "❓"}


def _recortar(texto, largo=140):
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[:largo].rstrip() + "…"


def tarjeta_social(item):
    inicial = escape((item["autor"] or "?")[:1].upper())
    pie = (f'<div class="pie"><span class="pf-avatar">{inicial}</span>'
           f'<span>{escape(item["autor"])} · {hace(item["creado"])}</span></div>')
    if item["clase"] == "resena":
        estrellas = "★" * item["estrellas"] + "☆" * (5 - item["estrellas"])
        return (f'<div class="pf-social"><span class="est">{estrellas}</span>'
                f'<div class="cita">“{escape(_recortar(item["texto"], 120))}”</div>{pie}</div>')
    icono = ICONOS_PUBLICACION.get(item["tipo"], "📝")
    return (f'<div class="pf-social">{chip(icono + " " + item["tipo"], "verde")}'
            f'<b>{escape(_recortar(item["titulo"], 70))}</b>'
            f'<div class="txt">{escape(_recortar(item["texto"]))}</div>{pie}</div>')


def banner_comunidad(items):
    """Banner superior con las últimas publicaciones y reseñas reales (se desliza solo y se pausa al pasar el cursor)."""
    if items:
        tarjetas = "".join(tarjeta_social(i) for i in items)
        animada = len(items) >= 3
        pista = tarjetas + (f'<div style="display:contents" aria-hidden="true">{tarjetas}</div>' if animada else "")
    else:
        animada = False
        pista = ('<div class="pf-social"><b>Aún no hay publicaciones</b>'
                 '<div class="txt">Entra y comparte el primer tip o la primera oferta de la comunidad.</div></div>')
    clase = "pf-pista animada" if animada else "pf-pista"
    return ('<div class="pf-banner"><div class="cab"><span class="pf-badge">Comunidad PetFletes</span>'
            '<h1>Lo que comparte nuestra comunidad</h1>'
            '<p>Tips para tu mascota, ofertas de tiendas y reseñas de otros dueños, publicados por la propia plataforma.</p></div>'
            f'<div class="pf-carrusel"><div class="{clase}">{pista}</div></div></div>')


def estadisticas(items):
    """Fila de cifras reales. items: [(etiqueta, valor, detalle)]; omite las que valen cero."""
    celdas = "".join(kpi(e, v, d) for e, v, d in items)
    return f'<div class="pf-stats">{celdas}</div>' if celdas else ""
