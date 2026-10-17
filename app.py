"""PetFletes - MVP de economía colaborativa para productos de mascotas.

Roles: usuario, repartidor y administrador.
Ejecutar con:  python -m streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="PetFletes", page_icon="🐾", layout="wide", initial_sidebar_state="collapsed")

import db  # noqa: E402
import estilos  # noqa: E402
import vistas_admin as va  # noqa: E402
import vistas_cliente as vc  # noqa: E402
import vistas_repartidor as vr  # noqa: E402
import vistas_tienda as vt  # noqa: E402
from componentes import (NAV_CARRITO, NAV_EN_CURSO, NAV_PEDIDOS, NAV_TIENDAS, ZONA_DEFECTO,  # noqa: E402
                         ZONAS, texto_calificacion, vista_comunidad, vista_soporte)

estilos.inyectar_css()


@st.cache_resource
def iniciar_base_de_datos():
    db.init_db()
    return True


iniciar_base_de_datos()

ROLES = {"🧑 Usuario": "usuario", "🛵 Repartidor": "repartidor", "🏪 Tienda": "tienda",
         "🛠️ Administrador": "admin"}
NOMBRE_ROL = {"usuario": "Usuario", "repartidor": "Repartidor", "tienda": "Tienda", "admin": "Administrador"}
# Cuentas de demostración: solo existen si la app se inicia con PETFLETES_DEMO=1
DEMO_EMAIL = ({"usuario": "demo@petfletes.cr", "repartidor": "repartidor@petfletes.cr",
               "tienda": "tienda@petfletes.cr"} if db.DEMO else {})
DESCRIPCION_ROL = {
    "usuario": "Pide productos para tu mascota y ofrece tu tarifa de envío.",
    "repartidor": "Acepta viajes, gana con cada entrega y navega con Waze o Google Maps.",
    "tienda": "Recibe pedidos, confirma el pago del producto y administra tu catálogo.",
    "admin": "Panel de control de la plataforma.",
}
VEHICULOS = ["Moto", "Bicicleta", "Carro pequeño", "Pick-up", "Camión pequeño"]

NAVEGACION = {
    "usuario": {
        NAV_TIENDAS: vc.vista_tiendas,
        NAV_CARRITO: vc.vista_carrito,
        NAV_PEDIDOS: vc.vista_seguimiento,
        "💬 Soporte": vista_soporte,
        "👥 Comunidad": vista_comunidad,
        "🗺️ Mapa": vc.vista_mapa,
    },
    "repartidor": {
        "🧭 Viajes disponibles": vr.vista_disponibles,
        NAV_EN_CURSO: vr.vista_en_curso,
        "💰 Ganancias": vr.vista_ganancias,
        "💬 Soporte": vista_soporte,
        "👥 Comunidad": vista_comunidad,
    },
    "tienda": {
        "📥 Pedidos": vt.vista_pedidos_tienda,
        "🛍️ Mi catálogo": vt.vista_catalogo_tienda,
        "🏪 Mi tienda": vt.vista_mi_tienda,
        "💬 Soporte": vista_soporte,
        "👥 Comunidad": vista_comunidad,
    },
    "admin": {
        "📊 Resumen": va.vista_resumen,
        "📦 Pedidos": va.vista_pedidos_admin,
        "👤 Usuarios": va.vista_usuarios_admin,
        "🛵 Repartidores": va.vista_repartidores_admin,
        "🏪 Tiendas": va.vista_tiendas_admin,
        "📈 Reportes": va.vista_reportes,
        "💬 Soporte": vista_soporte,
    },
}


# --------------------------------------------------------------- Autenticación
def _form_login(rol):
    with st.form("form_login"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        try:
            usuario = db.autenticar(email, password)
        except ValueError as error:
            st.error(str(error))
            return
        if usuario is None:
            st.error("Correo o contraseña incorrectos.")
        elif usuario["rol"] != rol:
            st.error(f"Esa cuenta es de tipo «{NOMBRE_ROL[usuario['rol']]}». "
                     "Cambia la opción de arriba para entrar.")
        else:
            st.session_state.usuario = usuario
            st.rerun()
    if rol in DEMO_EMAIL and st.button("✨ Probar con la cuenta demo", key="btn_demo", use_container_width=True):
        st.session_state.usuario = db.autenticar(DEMO_EMAIL[rol], "demo123")
        st.rerun()


def _form_registro(rol):
    with st.form("form_registro"):
        nombre = st.text_input("Nombre completo")
        email = st.text_input("Correo electrónico", key="email_registro")
        telefono = st.text_input("Teléfono de contacto", placeholder="8888-0000")
        sinpe, vehiculo, tienda = "", "", None
        if rol == "tienda":
            t_nombre = st.text_input("Nombre de la tienda")
            t_direccion = st.text_input("Dirección de la tienda")
            sinpe = st.text_input("SINPE Móvil de la tienda (para recibir el pago de los productos)",
                                  placeholder="8888-0000")
            t_zona = st.selectbox("Zona de la tienda", list(ZONAS))
            tienda = {"nombre": t_nombre, "direccion": t_direccion, "sinpe": sinpe,
                      "lat": ZONAS[t_zona][0], "lon": ZONAS[t_zona][1], "descripcion": ""}
        if rol == "repartidor":
            sinpe = st.text_input("Número de SINPE Móvil (para recibir pagos)", placeholder="8888-0000")
            vehiculo = st.selectbox("Tipo de vehículo", VEHICULOS)
        password = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="password_registro")
        registrar = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)
    if registrar:
        try:
            st.session_state.usuario = db.crear_usuario(
                nombre, email, telefono, password, rol=rol, sinpe=sinpe, vehiculo=vehiculo, tienda=tienda)
            st.rerun()
        except ValueError as error:
            st.error(str(error))


def vista_auth():
    estilos.inyectar_fondo_ingreso()
    estilos.html(estilos.logo())
    col_hero, _espacio, col_form = st.columns([1.15, 0.85, 1.0], gap="large")  # el centro queda libre para la ilustración
    with col_hero:
        estilos.html(estilos.hero(
            "Economía colaborativa", "Tu mascota lo pide, tú pones el precio del envío",
            "Elige una tienda, ofrece tu tarifa y los repartidores de tu zona compiten por llevarte el pedido.",
            emoji=""))
        estilos.html('<div class="pf-solo-desktop">'
                     + estilos.subtitulo("Así de fácil")
                     + estilos.pasos([("Elige tu tienda", "Arma tu carrito con alimento, higiene, juguetes y más."),
                                      ("Ofrece tu tarifa", "Sube o baja el envío de ₡100 en ₡100 y elige la mejor oferta."),
                                      ("Recibe y paga directo", "Sigue el viaje en el mapa y paga por SINPE Móvil o efectivo.")])
                     + estilos.subtitulo("Todo para tu mascota")
                     + estilos.categorias_tira() + '</div>')
    with col_form:
        with st.container(key="card_auth"):
            st.markdown("### Bienvenido 👋")
            st.session_state.setdefault("rol_auth", list(ROLES)[0])
            etiqueta = st.pills("¿Cómo quieres entrar?", list(ROLES), selection_mode="single",
                                key="rol_auth") or list(ROLES)[0]
            rol = ROLES[etiqueta]
            st.caption(DESCRIPCION_ROL[rol])
            if rol == "admin":
                _form_login(rol)
            else:
                tab_login, tab_registro = st.tabs(["Iniciar sesión", "Registrarme"])
                with tab_login:
                    _form_login(rol)
                    if rol in DEMO_EMAIL:
                        st.caption("Cuenta de prueba: " + DEMO_EMAIL[rol] + " / demo123")
                with tab_registro:
                    _form_registro(rol)


# ------------------------------------------------------------------- Barra superior
def cerrar_sesion():
    st.session_state.clear()


def ir_a_carrito():
    st.session_state["nav"] = NAV_CARRITO


def barra_superior(usuario):
    es_cliente = usuario["rol"] == "usuario"
    with st.container(key="topbar"):
        if es_cliente:
            c_logo, c_zona, c_busca, c_carro, c_cuenta = st.columns([2.2, 2.6, 4, 1.4, 1], vertical_alignment="center")
        else:
            c_logo, c_cuenta = st.columns([6, 1], vertical_alignment="center")
        c_logo.markdown(estilos.logo(), unsafe_allow_html=True)

        if es_cliente:
            st.session_state.setdefault("zona_actual", ZONA_DEFECTO)
            with c_zona:
                with st.popover(f"📍 {st.session_state['zona_actual']}", use_container_width=True):
                    st.selectbox("Tu zona (para ordenar las tiendas por cercanía)", list(ZONAS), key="zona_actual")
            consulta = c_busca.text_input("Buscar productos", key="busqueda", placeholder="🔎 Buscar productos…",
                                          label_visibility="collapsed")
            if consulta != st.session_state.get("_ultima_busqueda", ""):
                st.session_state["_ultima_busqueda"] = consulta
                if consulta.strip():
                    st.session_state["nav"] = NAV_TIENDAS
            unidades = sum(st.session_state.carrito.values())
            c_carro.button(f"🛒 {unidades}", key="btn_carrito", on_click=ir_a_carrito, use_container_width=True,
                           type="primary" if unidades else "secondary")

        with c_cuenta:
            with st.popover("👤", use_container_width=True):
                st.markdown(f"**{usuario['nombre']}**")
                st.caption(f"Cuenta: {NOMBRE_ROL[usuario['rol']]}")
                if usuario["rol"] == "usuario":
                    promedio, n = db.promedio_usuario(usuario["id"])
                elif usuario["rol"] == "repartidor" and usuario["repartidor_id"]:
                    promedio, n = db.promedio_repartidor(usuario["repartidor_id"])
                else:
                    promedio, n = None, 0
                if n:
                    st.caption(f"Tu calificación: {texto_calificacion(promedio, n)}")
                with st.expander("🔑 Cambiar contraseña"):
                    with st.form("form_clave", clear_on_submit=True):
                        clave_actual = st.text_input("Contraseña actual", type="password")
                        clave_nueva = st.text_input("Contraseña nueva (mínimo 6)", type="password")
                        cambiar = st.form_submit_button("Cambiar", use_container_width=True)
                    if cambiar:
                        try:
                            db.cambiar_password(usuario["id"], clave_actual, clave_nueva)
                            st.success("Contraseña actualizada.")
                        except ValueError as error:
                            st.error(str(error))
                st.button("Cerrar sesión", key="btn_salir", on_click=cerrar_sesion, use_container_width=True)


# ------------------------------------------------------------------- Principal
def main():
    for clave, valor in {"usuario": None, "carrito": {}, "tienda_carrito": None, "pedido_id": None}.items():
        st.session_state.setdefault(clave, valor)

    if st.session_state.usuario is None:
        vista_auth()
        return

    usuario = st.session_state.usuario
    vistas = NAVEGACION[usuario["rol"]]
    secciones = list(vistas)

    if "ir_a" in st.session_state:
        st.session_state["nav"] = st.session_state.pop("ir_a")
    barra_superior(usuario)
    if st.session_state.get("nav") not in secciones:
        st.session_state["nav"] = secciones[0]

    seleccion = st.pills("Navegación", secciones, selection_mode="single", key="nav", label_visibility="collapsed")
    seccion = seleccion or st.session_state.get("_nav_previa", secciones[0])
    st.session_state["_nav_previa"] = seccion
    vistas[seccion]()


main()
