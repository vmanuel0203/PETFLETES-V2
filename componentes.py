"""Componentes compartidos de PetFletes: mapas, tracking, chats, calificaciones y puja."""
from datetime import datetime

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import db
import estilos
import tarifas
import tracking
from estilos import colones

ZONA_DEFECTO = "San José centro"
ZONAS = {
    "San José centro": (9.9281, -84.0907),
    "San Pedro de Montes de Oca": (9.9347, -84.0510),
    "Santa Ana centro": (9.9328, -84.1833),
    "Desamparados centro": (9.8975, -84.0661),
    "Heredia - Barreal": (9.9972, -84.1523),
    "Alajuela centro": (10.0162, -84.2140),
    "Cartago centro": (9.8644, -83.9194),
}
ESTADOS = {"Esperando tienda": "🏪", "Buscando repartidor": "🔎", "Tiempo agotado": "⏰", "Aceptado": "🛵",
           "Entregado": "✅", "Cancelado": "❌"}
TIPOS_PUBLICACION = ["Oferta de tienda", "Tip de mascotas", "Pregunta"]
ICONOS_TIPO = {"Oferta de tienda": "🏷️", "Tip de mascotas": "💡", "Pregunta": "❓"}

COLOR_TIENDA = "#2E7D32"
COLOR_DESTINO = "#D32F2F"
FMT_FECHA = "%Y-%m-%d %H:%M:%S"
GATO_HTML = '<div style="font-size:30px;line-height:30px;text-align:center">🐱🚲</div>'

# Nombres de las secciones de navegación (se usan para saltar entre pantallas)
NAV_TIENDAS = "🛍️ Tiendas"
NAV_CARRITO = "🛒 Carrito"
NAV_PEDIDOS = "📦 Mis pedidos"
NAV_EN_CURSO = "🚚 En curso"


def mostrar_mapa(puntos):
    """Mapa simple (st.map). Cada punto: lat, lon, color, size."""
    df = pd.DataFrame(puntos)
    st.map(df, latitude="lat", longitude="lon", color="color", size="size", zoom=11)
    leyenda = []
    if (df["color"] == COLOR_TIENDA).any():
        leyenda.append("🟢 Inicio / tienda")
    if (df["color"] == COLOR_DESTINO).any():
        leyenda.append("🔴 Destino")
    st.caption(" · ".join(leyenda))


def puntos_ruta(p):
    return [
        {"lat": p["origen_lat"], "lon": p["origen_lon"], "color": COLOR_TIENDA, "size": 250},
        {"lat": p["destino_lat"], "lon": p["destino_lon"], "color": COLOR_DESTINO, "size": 250},
    ]


def _mapa_clicable(mapa, key):
    try:
        return st_folium(mapa, height=320, use_container_width=True,
                         returned_objects=["last_clicked"], key=key)
    except TypeError:  # versiones de streamlit-folium sin use_container_width
        return st_folium(mapa, height=320, returned_objects=["last_clicked"], key=key)


def quitar_pin(clave):
    st.session_state[clave] = None


def selector_pin(clave, centro, etiqueta, color, zoom=13):
    """Mapa donde el usuario toca para fijar un pin. Devuelve (lat, lon) o None."""
    pin = st.session_state.get(clave)
    mapa = folium.Map(location=list(pin or centro), zoom_start=15 if pin else zoom, control_scale=True)
    if pin:
        folium.Marker(list(pin), tooltip=etiqueta, icon=folium.Icon(color=color)).add_to(mapa)
    salida = _mapa_clicable(mapa, "mapa_" + clave)
    click = salida.get("last_clicked") if salida else None
    if click:
        nuevo = (round(click["lat"], 6), round(click["lng"], 6))
        if st.session_state.get("ult_" + clave) != nuevo:
            st.session_state["ult_" + clave] = nuevo
            st.session_state[clave] = nuevo
            st.rerun()
    pin = st.session_state.get(clave)
    if pin:
        col_txt, col_btn = st.columns([3, 1])
        col_txt.caption(f"📍 {etiqueta}: {pin[0]:.5f}, {pin[1]:.5f}")
        col_btn.button("Quitar", key="quitar_" + clave, on_click=quitar_pin, args=(clave,))
    else:
        st.caption(f"👆 Toca el mapa para fijar el pin ({etiqueta.lower()}).")
    return pin


def fmt_mmss(segundos):
    m, s = divmod(int(max(0, segundos)), 60)
    return f"{m:02d}:{s:02d}"


def fmt_duracion(segundos):
    h, resto = divmod(int(max(0, segundos)), 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def duracion_entre(inicio, fin):
    return (datetime.strptime(fin, FMT_FECHA) - datetime.strptime(inicio, FMT_FECHA)).total_seconds()


def texto_calificacion(promedio, n):
    return f"⭐ {promedio:.1f} ({n})" if n else "Sin calificaciones aún"


def _render_folium(mapa, key, objetos, alto=320):
    try:
        return st_folium(mapa, height=alto, use_container_width=True,
                         returned_objects=objetos, key=key)
    except TypeError:  # versiones de streamlit-folium sin use_container_width
        return st_folium(mapa, height=alto, returned_objects=objetos, key=key)


def render_tracking(p, key):
    """Métricas de tiempo + mapa con el repartidor (🐱🚲), la tienda y el destino."""
    factor = 10.0 if st.session_state.get("acel_demo") else 1.0
    t = tracking.estado_tracking(p, factor)

    c1, c2, c3 = st.columns(3)
    c1.metric("Tiempo de la orden", fmt_duracion(tracking.segundos_desde(p["creado"])))
    c2.metric("Llega a la tienda", f"{t['eta_tienda_min']} min" if t["eta_tienda_min"] else "En tienda")
    c3.metric("Tienda → destino", f"{t['eta_destino_min']} min" if t["eta_destino_min"] else "Llegó")
    st.info(t["mensaje"] + (" (simulación x10)" if factor > 1 else ""))

    origen = [p["origen_lat"], p["origen_lon"]]
    destino = [p["destino_lat"], p["destino_lon"]]
    pos = [t["lat"], t["lon"]]
    mapa = folium.Map(location=pos, zoom_start=13, control_scale=True)
    folium.Marker(origen, tooltip="Tienda / punto de inicio",
                  icon=folium.Icon(color="green", icon="home")).add_to(mapa)
    folium.Marker(destino, tooltip="Destino del cliente",
                  icon=folium.Icon(color="red", icon="flag")).add_to(mapa)
    folium.PolyLine([origen, destino], color="#0F5C4D", weight=4, opacity=0.7).add_to(mapa)
    if t["fase"] == "hacia_tienda":
        folium.PolyLine([pos, origen], color="#E8A33D", weight=3, dash_array="6 8").add_to(mapa)
    folium.Marker(pos, tooltip="Repartidor",
                  icon=folium.DivIcon(html=GATO_HTML, icon_size=(60, 40), icon_anchor=(30, 20))).add_to(mapa)
    mapa.fit_bounds([origen, destino, pos], padding=(30, 30))
    _render_folium(mapa, key, [], 300)
    st.caption("🟢 Tienda · 🔴 Destino · 🐱🚲 Repartidor (ubicación simulada)")


def botones_navegacion(p):
    """Abre la tienda o al cliente en Waze / Google Maps."""
    st.markdown("**🧭 Navegar con una app externa**")
    for etiqueta, lat, lon in (("🏪 Ir a la tienda / punto de inicio", p["origen_lat"], p["origen_lon"]),
                               ("🏠 Ir al destino del cliente", p["destino_lat"], p["destino_lon"])):
        st.caption(etiqueta)
        c1, c2 = st.columns(2)
        c1.link_button("Waze", tracking.enlace_waze(lat, lon), use_container_width=True)
        c2.link_button("Google Maps", tracking.enlace_google_maps(lat, lon), use_container_width=True)


def _lista_mensajes(mensajes, mi_id, vacio):
    with st.container(height=260, border=True):
        if not mensajes:
            st.caption(vacio)
        for m in mensajes:
            propio = m["autor_id"] == mi_id
            with st.chat_message("user" if propio else "assistant"):
                st.markdown(f"**{'Tú' if propio else m['autor']}** · {m['creado'][11:16]}")
                st.write(m["texto"])


def _form_mensaje(clave):
    with st.form(clave, clear_on_submit=True):
        texto = st.text_input("Mensaje", placeholder="Escribe un mensaje…", label_visibility="collapsed")
        enviar = st.form_submit_button("Enviar", use_container_width=True)
    return texto if enviar else None


@st.fragment(run_every=4)
def chat_pedido(pedido_id):
    """Chat cliente ↔ repartidor (se actualiza solo cada 4 s)."""
    usuario = st.session_state.usuario
    mensajes = db.listar_mensajes_pedido(pedido_id, usuario["id"])
    _lista_mensajes(mensajes, usuario["id"], "Aún no hay mensajes. ¡Saluda para coordinar la entrega!")
    if db.estado_pedido(pedido_id) != "Aceptado":
        st.caption("El chat se cerró porque el viaje ya no está activo.")
        return
    texto = _form_mensaje(f"chat_pedido_{pedido_id}")
    if texto and texto.strip():
        try:
            db.enviar_mensaje_pedido(pedido_id, usuario["id"], texto)
            st.rerun(scope="fragment")
        except ValueError as error:
            st.error(str(error))


@st.fragment(run_every=4)
def chat_soporte(hilo_usuario_id):
    """Chat de soporte con el administrador (se actualiza solo cada 4 s)."""
    usuario = st.session_state.usuario
    mensajes = db.listar_mensajes_soporte(hilo_usuario_id, usuario["id"])
    vacio = ("Cuéntanos tu incidencia y el administrador te responderá aquí."
             if usuario["rol"] != "admin" else "Esta conversación aún no tiene mensajes.")
    _lista_mensajes(mensajes, usuario["id"], vacio)
    texto = _form_mensaje(f"chat_soporte_{hilo_usuario_id}")
    if texto and texto.strip():
        try:
            db.enviar_mensaje_soporte(hilo_usuario_id, usuario["id"], texto)
            st.rerun(scope="fragment")
        except ValueError as error:
            st.error(str(error))


def form_calificacion(pedido_id, autor_rol, actor_id, a_quien):
    """Encuesta mutua tras la entrega: estrellas + comentario opcional."""
    previa = db.obtener_calificacion(pedido_id, autor_rol)
    if previa:
        st.success(f"Calificaste {a_quien} con {'⭐' * previa['estrellas']}. ¡Gracias!")
        return
    st.markdown(f"#### ⭐ Califica {a_quien}")
    with st.form(f"cal_{pedido_id}_{autor_rol}"):
        estrellas = st.radio("Calificación", [5, 4, 3, 2, 1], horizontal=True,
                             format_func=lambda n: "⭐" * n)
        comentario = st.text_area("Comentario (opcional)", max_chars=300)
        enviar = st.form_submit_button("Enviar calificación", use_container_width=True)
    if enviar:
        try:
            db.guardar_calificacion(pedido_id, autor_rol, actor_id, estrellas, comentario)
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def _resumen_pedido(p):
    with st.container(border=True):
        st.markdown(f"**Tienda:** {p['tienda_nombre']}")
        st.markdown(f"**Inicio:** {p['origen_nombre']}")
        st.markdown(f"**Destino:** {p['destino_nombre']}")
        st.caption(p["destino_senas"])
        st.write(f"Distancia: {p['distancia_km']:g} km · Peso: {p['peso_total']:g} kg")
        for item in p["items"]:
            st.write(f"• {item['cantidad']} × {item['nombre']} ({colones(item['precio'] * item['cantidad'])})")
        st.write(f"Productos: **{colones(p['subtotal'])}** · Envío: **{colones(p['oferta'])}** · "
                 f"Total: **{colones(p['subtotal'] + p['oferta'])}**")


def _ui_espera_tienda(p, usuario):
    st.info("🏪 Tu pedido espera la confirmación de la tienda. Cuando confirme que recibió el pago de los "
            "productos, se empieza a preparar y se abre la búsqueda de repartidor.")
    sinpe = p.get("tienda_sinpe")
    donde = (f"por SINPE Móvil al **{sinpe}** (a nombre de {p['tienda_nombre']}) o en efectivo en la tienda"
             if sinpe else "con los datos de pago que te indique la tienda")
    st.success(f"**Paga los productos directo a la tienda:** {colones(p['subtotal'])} {donde}."
               + (f" Teléfono de la tienda: {p['tienda_telefono']}." if p.get("tienda_telefono") else ""))
    st.caption("El envío no se paga aquí: lo cobra el repartidor al entregarte el pedido. "
               "PetFletes no procesa pagos.")
    if st.button("Cancelar pedido", key=f"canc_esp_{p['id']}", use_container_width=True):
        db.cancelar_pedido(p["id"], usuario["id"])
        st.rerun()
    st.caption("Si ya pagaste y cancelas, coordina el reembolso directamente con la tienda.")


def _ui_puja(p, usuario):
    restante = p["segundos_restantes"]
    st.progress(min(1.0, restante / p["puja_segundos"]),
                text=f"⏳ Tiempo de la puja: {fmt_mmss(restante)}")

    st.markdown("#### 💰 Tu oferta por el envío")
    diferencia = int(p["oferta"] - p["oferta_inicial"])
    st.metric("Tarifa actual", colones(p["oferta"]), delta=diferencia if diferencia else None)
    c1, c2 = st.columns(2)
    c1.button("➖ Bajar ₡100", key=f"baj_{p['id']}", on_click=db.ajustar_tarifa,
              args=(p["id"], usuario["id"], -db.PASO_TARIFA),
              disabled=p["oferta"] - db.PASO_TARIFA < p["tarifa_minima"], use_container_width=True)
    c2.button("➕ Aumentar ₡100", key=f"sub_{p['id']}", on_click=db.ajustar_tarifa,
              args=(p["id"], usuario["id"], db.PASO_TARIFA),
              disabled=p["oferta"] + db.PASO_TARIFA > p["tope_envio"], use_container_width=True)
    st.caption(f"Mínimo: {colones(p['tarifa_minima'])} · Máximo (costo de los productos): {colones(p['tope_envio'])} · "
               f"Iniciaste en {colones(p['oferta_inicial'])}. "
               "Cada clic suma o resta ₡100 a la tarifa actual.")

    c3, c4 = st.columns(2)
    if c3.button("Cancelar pedido", key=f"can_{p['id']}", use_container_width=True):
        db.cancelar_pedido(p["id"], usuario["id"])
        st.rerun()
    if db.DEMO and c4.button("🧪 Simular ofertas (demo)", key=f"sim_{p['id']}", use_container_width=True):
        db.simular_ofertas(p["id"])

    st.markdown("#### 📨 Ofertas de repartidores")
    ofertas = db.listar_ofertas(p["id"])
    if not ofertas:
        st.info("Esperando ofertas… Subir un poco la tarifa suele atraer más repartidores.")
    for o in ofertas:
        with st.container(border=True):
            st.markdown(f"**Repartidor: {o['repartidor_nombre']}** — Oferta: **{colones(o['monto'])}**")
            st.caption(f"{o['vehiculo']} · {texto_calificacion(o['promedio'], o['n_cal'])}")
            if st.button(f"Aceptar oferta de {colones(o['monto'])}", key=f"el_{o['id']}",
                         type="primary", use_container_width=True):
                if db.elegir_oferta(p["id"], o["id"], usuario["id"]):
                    st.rerun()
                else:
                    st.error("Esa oferta ya no está disponible.")


def _ui_timeout(p, usuario):
    minutos = max(1, p["puja_segundos"] // 60)
    st.warning(f"⏰ Pasaron {minutos} minutos y ningún repartidor aceptó ni elegiste una oferta.")
    st.markdown("**¿Qué quieres hacer con tu orden?**")
    c1, c2 = st.columns(2)
    if c1.button(f"🔁 Seguir esperando {minutos} min más", key=f"seg_{p['id']}", type="primary",
                 use_container_width=True):
        db.reactivar_pedido(p["id"], usuario["id"])
        st.rerun()
    if c2.button("❌ Cancelar la orden", key=f"cant_{p['id']}", use_container_width=True):
        db.cancelar_pedido(p["id"], usuario["id"])
        st.rerun()
    st.caption("Si sigues esperando, la orden se republica, el ciclo se reinicia y podrás modificar la tarifa de nuevo.")


def _ui_viaje(p, usuario):
    st.toggle("⏩ Acelerar simulación x10 (demo)", key="acel_demo")
    render_tracking(p, f"trk_{p['id']}")

    total = p["subtotal"] + p["oferta"]
    st.markdown("### 🛵 Datos del viaje")
    with st.container(border=True):
        promedio, n = db.promedio_repartidor(p["repartidor_id"])
        st.write(f"**Repartidor:** {p['repartidor_nombre']} · {p['repartidor_vehiculo']}")
        st.caption(texto_calificacion(promedio, n))
        st.write(f"**Ruta:** {p['origen_nombre']} → {p['destino_nombre']}")
        st.write(f"**Tarifa acordada:** {colones(p['oferta'])}")
    st.success(
        f"**Pago del envío:** los productos ya los pagaste a la tienda. Al recibir tu paquete paga solo el envío, "
        f"**{colones(p['oferta'])}**, por SINPE Móvil al número **{p['repartidor_sinpe']}** "
        f"(a nombre de {p['repartidor_nombre']}) o en efectivo."
    )
    st.caption("PetFletes no procesa tarjetas ni dinero: los pagos son acuerdos directos con la tienda y el repartidor.")
    if st.button("✅ Ya recibí mi pedido", key=f"rec_{p['id']}", type="primary", use_container_width=True):
        if db.marcar_entregado_usuario(p["id"], usuario["id"]):
            st.balloons()
        st.rerun()


def _ui_entregado(p, usuario):
    st.success("¡Pedido entregado! Gracias por usar PetFletes 🐾")
    if p.get("entregado_en"):
        st.caption(f"Duración total de la orden: {fmt_duracion(duracion_entre(p['creado'], p['entregado_en']))}")
    form_calificacion(p["id"], "usuario", usuario["id"], f"al repartidor {p['repartidor_nombre']}")


def panel_pedido(pedido_id, estado_visto):
    """Panel del pedido (se refresca solo mientras la orden está activa)."""
    usuario = st.session_state.usuario
    p = db.obtener_pedido(pedido_id, usuario["id"])
    if p is None:
        st.error("Pedido no encontrado.")
        return
    if p["estado"] != estado_visto:
        st.rerun()  # el estado cambió: se redibuja la página completa (por ejemplo, para abrir el chat)

    st.subheader(f"{ESTADOS[p['estado']]} Pedido #{p['id']} — {p['estado']}")
    estado = p["estado"]
    if estado == "Esperando tienda":
        _ui_espera_tienda(p, usuario)
    elif estado == "Buscando repartidor":
        _ui_puja(p, usuario)
    elif estado == "Tiempo agotado":
        _ui_timeout(p, usuario)
    elif estado == "Aceptado":
        _ui_viaje(p, usuario)
    elif estado == "Entregado":
        _ui_entregado(p, usuario)
    else:
        st.warning("Este pedido fue cancelado."
                   + (f" Nota de la tienda: {p['nota_tienda']}" if p.get("nota_tienda") else ""))
    with st.expander("Ver detalle del pedido"):
        _resumen_pedido(p)
    if estado in ("Cancelado", "Tiempo agotado"):
        mostrar_mapa(puntos_ruta(p))


@st.fragment(run_every=5)
def tracking_repartidor(pedido_id):
    rid = st.session_state.usuario["repartidor_id"]
    p = db.obtener_pedido_repartidor(pedido_id, rid)
    if p is None or p["estado"] != "Aceptado":
        st.rerun()
        return
    render_tracking(p, f"trk_rep_{pedido_id}")


def vista_comunidad():
    usuario = st.session_state.usuario
    st.header("👥 Comunidad")
    st.caption("Compartí ofertas de tiendas, tips y preguntas con otros dueños de mascotas.")

    with st.form("form_publicacion", clear_on_submit=True):
        tipo = st.selectbox("Tipo de publicación", TIPOS_PUBLICACION)
        titulo = st.text_input("Título", max_chars=80)
        contenido = st.text_area("Contenido", max_chars=500)
        publicar = st.form_submit_button("Publicar", type="primary", use_container_width=True)
    if publicar:
        if not titulo.strip() or not contenido.strip():
            st.error("Completá el título y el contenido.")
        else:
            db.crear_publicacion(usuario["id"], tipo, titulo, contenido)
            st.success("¡Publicación creada!")

    st.subheader("Últimas publicaciones")
    filtro = st.selectbox("Filtrar", ["Todas"] + TIPOS_PUBLICACION)
    publicaciones = db.listar_publicaciones(None if filtro == "Todas" else filtro)
    if not publicaciones:
        st.info("Todavía no hay publicaciones.")
    for pub in publicaciones:
        with st.container(border=True):
            st.markdown(f"{ICONOS_TIPO.get(pub['tipo'], '📝')} **{pub['titulo']}**")
            st.write(pub["contenido"])
            st.caption(f"{pub['tipo']} · por {pub['autor']} · {pub['creado']}")


def vista_soporte():
    usuario = st.session_state.usuario
    st.header("💬 Soporte")
    if usuario["rol"] == "admin":
        hilos = db.listar_hilos_soporte()
        pendientes = sum(1 for h in hilos if h["pendiente"])
        st.caption(f"Conversaciones: {len(hilos)} · Pendientes de responder: {pendientes}")
        if not hilos:
            st.info("Aún no hay incidencias reportadas.")
            return
        sel = st.selectbox(
            "Conversación", [h["id"] for h in hilos],
            format_func=lambda i: next(
                f"{'🔴' if h['pendiente'] else '🟢'} {h['nombre']} ({h['rol']}) · {h['ultimo_creado'][5:16]}"
                for h in hilos if h["id"] == i))
        chat_soporte(sel)
        return
    st.caption("Reporta incidencias al administrador de PetFletes; te responderá por este chat.")
    chat_soporte(usuario["id"])
