"""Panel de administración: resumen, pedidos, usuarios, repartidores, tiendas y reportes."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
import estilos
from componentes import ESTADOS, ZONAS, mostrar_mapa, puntos_ruta, render_tracking, selector_pin
from estilos import colones

EN_CURSO = ("Esperando tienda", "Buscando repartidor", "Tiempo agotado", "Aceptado")


def _df_pedidos(pedidos):
    return pd.DataFrame([{
        "Pedido": p["id"], "Fecha": p["creado"][:16], "Estado": f"{ESTADOS[p['estado']]} {p['estado']}",
        "Cliente": p["cliente_nombre"], "Tienda": p["tienda_nombre"], "Destino": p["destino_nombre"],
        "Repartidor": p["repartidor_nombre"] or "—", "Ofertas": p["n_ofertas"],
        "Productos": p["subtotal"], "Envío": p["oferta"], "Total": p["subtotal"] + p["oferta"],
    } for p in pedidos])


def _rango_fechas(clave, dias=30):
    hoy = date.today()
    rango = st.date_input("Fechas", value=(hoy - timedelta(days=dias), hoy), key=clave)
    if isinstance(rango, (tuple, list)):
        return (rango[0], rango[1]) if len(rango) == 2 else (rango[0], rango[0])
    return rango, rango


def _detalle_pedido(p, con_acciones=False):
    with st.container(key=f"card_detalle_{p['id']}"):
        estilos.html(estilos.chip_estado(p["estado"]) + estilos.chip(f"Pedido #{p['id']}", "gris"))
        st.write(f"**Cliente:** {p['cliente_nombre']} · Tel: {p['cliente_telefono'] or '—'}")
        st.write(f"**Ruta:** {p['origen_nombre']} → {p['destino_nombre']}")
        st.caption(f"Señas: {p['destino_senas']}")
        st.write(f"**Repartidor:** {p['repartidor_nombre'] or 'sin asignar'}"
                 + (f" · SINPE {p['repartidor_sinpe']}" if p["repartidor_sinpe"] else ""))
        for item in p["items"]:
            st.write(f"• {item['cantidad']} × {item['nombre']}")
        estilos.html(
            estilos.fila("Productos", colones(p["subtotal"])) + estilos.fila("Envío", colones(p["oferta"]))
            + estilos.fila("Total", colones(p["subtotal"] + p["oferta"]), fuerte=True))
        if p["estado"] == "Aceptado":
            render_tracking(p, f"adm_trk_{p['id']}")
        else:
            mostrar_mapa(puntos_ruta(p))
        if con_acciones and p["estado"] == "Esperando tienda" and p.get("tienda_usuario_id") is None:
            st.warning("Esta tienda no tiene cuenta propia: nadie puede confirmar el pago por ella.")
            if st.button("✅ Confirmar pago en nombre de la tienda", key=f"adm_conf_{p['id']}", type="primary"):
                db.admin_confirmar_pedido(p["id"])
                st.rerun()
        if con_acciones and p["estado"] in EN_CURSO:
            if st.button("❌ Cancelar este pedido", key=f"adm_can_{p['id']}"):
                db.admin_cancelar_pedido(p["id"])
                st.rerun()


# --------------------------------------------------------------------- Resumen
def _panel_resumen():
    s = db.estadisticas_admin()
    pendientes = sum(1 for h in db.listar_hilos_soporte() if h["pendiente"])
    kpis = [("Esperando tienda", s["esperando"], ""),
            ("En puja", s["buscando"] + s["agotados"], f"{s['agotados']} sin respuesta"),
            ("En viaje", s["aceptados"], ""), ("Entregados", s["entregados"], ""),
            ("Usuarios", s["usuarios"], ""), ("Repartidores", s["repartidores"], ""),
            ("Soporte pendiente", pendientes, "conversaciones")]
    for columna, (etiqueta, valor, detalle) in zip(st.columns(7), kpis):
        columna.markdown(estilos.kpi(etiqueta, valor, detalle), unsafe_allow_html=True)

    todos = db.listar_pedidos_admin(solo_en_curso=False)
    if todos:
        st.markdown("#### Pedidos por estado")
        conteo = pd.Series([p["estado"] for p in todos]).value_counts()
        st.bar_chart(conteo)

    en_curso = [p for p in todos if p["estado"] in EN_CURSO]
    st.markdown(f"#### Pedidos en curso ({len(en_curso)})")
    if not en_curso:
        st.info("No hay pedidos en curso.")
        return
    st.dataframe(_df_pedidos(en_curso), hide_index=True)
    mapa_puntos = [pt for p in en_curso for pt in puntos_ruta(p)]
    mostrar_mapa(mapa_puntos)
    with st.expander("Ver detalle de un pedido"):
        sel = st.selectbox("Pedido", [p["id"] for p in en_curso], format_func=lambda i: f"Pedido #{i}")
        _detalle_pedido(next(p for p in en_curso if p["id"] == sel))


def vista_resumen():
    st.markdown("## 📊 Resumen")
    if db.admin_usa_clave_antigua():
        st.error("⚠️ Una cuenta de administrador sigue usando la contraseña por defecto de la v1. "
                 "Cámbiala desde el menú 👤 → «Cambiar contraseña».")
    c1, c2 = st.columns([2, 1], vertical_alignment="center")
    auto = c1.toggle("Actualizar automáticamente (cada 10 s)", value=False)
    c2.button("🔄 Actualizar ahora", use_container_width=True)
    st.toggle("⏩ Acelerar simulación x10 (demo)", key="acel_demo")
    st.fragment(run_every=10 if auto else None)(_panel_resumen)()


# --------------------------------------------------------------------- Pedidos
def vista_pedidos_admin():
    st.markdown("## 📦 Historial de pedidos")
    todos = db.listar_pedidos_admin(solo_en_curso=False)
    f1, f2, f3, f4 = st.columns(4)
    estados = f1.multiselect("Estado", list(ESTADOS))
    tiendas = f2.multiselect("Tienda", sorted({p["tienda_nombre"] for p in todos}))
    with f3:
        desde, hasta = _rango_fechas("rango_pedidos", 30)
    texto = f4.text_input("Buscar cliente o #pedido").strip().lower()

    filtrados = [p for p in todos
                 if (not estados or p["estado"] in estados)
                 and (not tiendas or p["tienda_nombre"] in tiendas)
                 and desde <= date.fromisoformat(p["creado"][:10]) <= hasta
                 and (not texto or texto in p["cliente_nombre"].lower() or texto == str(p["id"]))]
    st.caption(f"{len(filtrados)} pedido(s) de {len(todos)}")
    if not filtrados:
        st.info("No hay pedidos con esos filtros.")
        return
    df = _df_pedidos(filtrados)
    st.dataframe(df, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       "pedidos.csv", "text/csv")
    sel = st.selectbox("Ver detalle y acciones", [p["id"] for p in filtrados],
                       format_func=lambda i: f"Pedido #{i}")
    _detalle_pedido(next(p for p in filtrados if p["id"] == sel), con_acciones=True)


# -------------------------------------------------------- Usuarios y repartidores
def _acciones_cuenta(cuentas, clave):
    """Selector + botón para suspender o reactivar una cuenta. cuentas: [(usuario_id, texto, activo)]."""
    opciones = {uid: (texto, activo) for uid, texto, activo in cuentas}
    sel = st.selectbox("Cuenta", list(opciones), format_func=lambda i: opciones[i][0], key=f"sel_{clave}")
    activo = opciones[sel][1]
    if activo:
        if st.button("⏸️ Suspender cuenta", key=f"susp_{clave}"):
            db.set_usuario_activo(sel, False)
            st.rerun()
    elif st.button("▶️ Reactivar cuenta", key=f"react_{clave}", type="primary"):
        db.set_usuario_activo(sel, True)
        st.rerun()


def vista_usuarios_admin():
    st.markdown("## 👤 Usuarios")
    usuarios = db.listar_usuarios_admin()
    f1, f2 = st.columns([2, 1])
    texto = f1.text_input("Buscar por nombre o correo", key="buscar_usuarios").strip().lower()
    estado = f2.selectbox("Estado de la cuenta", ["Todas", "Activas", "Suspendidas"], key="estado_usuarios")
    filtrados = [u for u in usuarios
                 if (not texto or texto in u["nombre"].lower() or texto in u["email"])
                 and (estado == "Todas" or (estado == "Activas") == bool(u["activo"]))]
    st.caption(f"{len(filtrados)} de {len(usuarios)} usuarios")
    if not filtrados:
        st.info("No hay usuarios con esos filtros.")
        return
    df = pd.DataFrame([{
        "ID": u["id"], "Nombre": u["nombre"], "Correo": u["email"], "Teléfono": u["telefono"] or "—",
        "Registrado": u["registrado"][:10], "Pedidos": u["pedidos"],
        "Calificación": f"{u['calificacion']} ({u['n_cal']})" if u["n_cal"] else "—",
        "Cuenta": "Activa" if u["activo"] else "Suspendida"} for u in filtrados])
    st.dataframe(df, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"), "usuarios.csv", "text/csv")
    _acciones_cuenta([(u["id"], f"{u['nombre']} · {u['email']}", bool(u["activo"])) for u in filtrados],
                     "usuarios")


def vista_repartidores_admin():
    st.markdown("## 🛵 Repartidores")
    repartidores = db.listar_repartidores_admin()
    f1, f2, f3 = st.columns([2, 1, 1])
    texto = f1.text_input("Buscar por nombre o correo", key="buscar_rep").strip().lower()
    tipo = f2.selectbox("Tipo", ["Todos", "Registrado", "Demo"], key="tipo_rep")
    vehiculo = f3.selectbox("Vehículo", ["Todos"] + sorted({r["vehiculo"] for r in repartidores}), key="veh_rep")
    filtrados = [r for r in repartidores
                 if (not texto or texto in r["nombre"].lower() or texto in (r["email"] or ""))
                 and (tipo == "Todos" or r["tipo"] == tipo)
                 and (vehiculo == "Todos" or r["vehiculo"] == vehiculo)]
    st.caption(f"{len(filtrados)} de {len(repartidores)} repartidores")
    if not filtrados:
        st.info("No hay repartidores con esos filtros.")
        return
    df = pd.DataFrame([{
        "ID": r["id"], "Nombre": r["nombre"], "Correo": r["email"] or "—", "SINPE": r["sinpe"],
        "Vehículo": r["vehiculo"], "Tipo": r["tipo"], "En curso": r["en_curso"], "Entregas": r["entregas"],
        "Calificación": f"{r['calificacion']} ({r['n_cal']})" if r["n_cal"] else "—",
        "Cuenta": "Activa" if r["activo"] else "Suspendida"} for r in filtrados])
    st.dataframe(df, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       "repartidores.csv", "text/csv")
    registrados = [(r["usuario_id"], f"{r['nombre']} · {r['email']}", bool(r["activo"]))
                   for r in filtrados if r["usuario_id"]]
    if registrados:
        _acciones_cuenta(registrados, "repartidores")
    else:
        st.caption("Los repartidores de demostración no tienen cuenta que suspender.")


# ---------------------------------------------------------------------- Tiendas
def vista_tiendas_admin():
    st.markdown("## 🏪 Tiendas y productos")
    tab_tiendas, tab_productos = st.tabs(["Tiendas", "Productos"])
    tiendas = db.listar_tiendas_admin()

    with tab_tiendas:
        st.dataframe(pd.DataFrame([{
            "ID": t["id"], "Tienda": t["nombre"], "Dirección": t["direccion"], "Productos": t["n_productos"],
            "Pedidos": t["n_pedidos"], "Estado": "Activa" if t["activa"] else "Oculta",
            "Cuenta": t["propietario"] or "sin cuenta", "SINPE": t["sinpe"] or "—"} for t in tiendas]),
            hide_index=True)
        with st.expander("✏️ Editar o ocultar una tienda"):
            sel = st.selectbox("Tienda", [t["id"] for t in tiendas],
                               format_func=lambda i: next(t["nombre"] for t in tiendas if t["id"] == i),
                               key="editar_tienda")
            t = next(x for x in tiendas if x["id"] == sel)
            with st.form(f"form_editar_tienda_{sel}"):
                nombre = st.text_input("Nombre", value=t["nombre"])
                direccion = st.text_input("Dirección", value=t["direccion"])
                descripcion = st.text_input("Descripción", value=t["descripcion"] or "")
                e1, e2 = st.columns(2)
                sinpe = e1.text_input("SINPE Móvil de la tienda", value=t["sinpe"] or "")
                telefono = e2.text_input("Teléfono", value=t["telefono"] or "")
                activa = st.checkbox("Visible para los clientes (aprobada)", value=bool(t["activa"]))
                guardar = st.form_submit_button("Guardar cambios", type="primary")
            if guardar:
                try:
                    db.actualizar_tienda(sel, nombre, direccion, descripcion, activa, sinpe, telefono)
                    st.success("Tienda actualizada.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        with st.expander("➕ Agregar tienda"):
            nombre = st.text_input("Nombre de la tienda", key="nt_nombre")
            direccion = st.text_input("Dirección", key="nt_direccion")
            descripcion = st.text_input("Descripción (opcional)", key="nt_desc")
            st.caption("Toca el mapa para fijar la ubicación de la tienda.")
            pin = selector_pin("pin_tienda_nueva", ZONAS["San José centro"], "Ubicación de la tienda", "green", 12)
            if st.button("Crear tienda", type="primary", key="nt_crear"):
                if not pin:
                    st.error("Fija la ubicación de la tienda en el mapa.")
                else:
                    try:
                        db.crear_tienda(nombre, direccion, pin[0], pin[1], descripcion)
                        st.session_state.pop("pin_tienda_nueva", None)
                        st.success("Tienda creada.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

    with tab_productos:
        if not tiendas:
            st.info("Aún no hay tiendas.")
            return
        sel_t = st.selectbox("Tienda", [t["id"] for t in tiendas],
                             format_func=lambda i: next(t["nombre"] for t in tiendas if t["id"] == i),
                             key="productos_tienda")
        productos = db.listar_productos(sel_t, solo_activos=False)
        if productos:
            st.dataframe(pd.DataFrame([{
                "ID": p["id"], "Producto": p["nombre"], "Categoría": p["categoria"], "Precio": p["precio"],
                "Peso (kg)": p["peso_kg"], "Estado": "Activo" if p["activo"] else "Oculto"} for p in productos]),
                hide_index=True)
        else:
            st.info("Esta tienda aún no tiene productos.")
        if productos:
            with st.expander("✏️ Editar producto"):
                sel_p = st.selectbox("Producto", [p["id"] for p in productos],
                                     format_func=lambda i: next(p["nombre"] for p in productos if p["id"] == i),
                                     key="editar_producto")
                p = next(x for x in productos if x["id"] == sel_p)
                with st.form(f"form_editar_producto_{sel_p}"):
                    nombre = st.text_input("Nombre", value=p["nombre"])
                    c1, c2, c3 = st.columns(3)
                    precio = c1.number_input("Precio (₡)", min_value=100, step=100, value=int(p["precio"]))
                    peso = c2.number_input("Peso (kg)", min_value=0.0, step=0.1, value=float(p["peso_kg"]))
                    categoria = c3.selectbox("Categoría", db.CATEGORIAS,
                                             index=db.CATEGORIAS.index(p["categoria"]) if p["categoria"] in db.CATEGORIAS else 0)
                    activo = st.checkbox("Visible para los clientes", value=bool(p["activo"]))
                    guardar = st.form_submit_button("Guardar producto", type="primary")
                if guardar:
                    try:
                        db.actualizar_producto(sel_p, nombre, precio, peso, categoria, activo)
                        st.success("Producto actualizado.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
        with st.expander("➕ Agregar producto"):
            with st.form("form_nuevo_producto", clear_on_submit=True):
                nombre = st.text_input("Nombre del producto")
                c1, c2, c3 = st.columns(3)
                precio = c1.number_input("Precio (₡)", min_value=100, step=100, value=5000)
                peso = c2.number_input("Peso (kg)", min_value=0.0, step=0.1, value=1.0)
                categoria = c3.selectbox("Categoría", db.CATEGORIAS)
                crear = st.form_submit_button("Agregar producto", type="primary")
            if crear:
                try:
                    db.crear_producto(sel_t, nombre, precio, peso, categoria)
                    st.success("Producto agregado.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


# --------------------------------------------------------------------- Reportes
def vista_reportes():
    st.markdown("## 📈 Reportes")
    desde, hasta = _rango_fechas("rango_reportes", 30)
    pedidos = [p for p in db.listar_pedidos_admin(solo_en_curso=False)
               if desde <= date.fromisoformat(p["creado"][:10]) <= hasta]
    if not pedidos:
        st.info("No hay pedidos en el periodo seleccionado.")
        return
    df = pd.DataFrame([{
        "Pedido": p["id"], "Día": p["creado"][:10], "Estado": p["estado"], "Cliente": p["cliente_nombre"],
        "Tienda": p["tienda_nombre"], "Repartidor": p["repartidor_nombre"] or "—",
        "Productos": p["subtotal"], "Envío": p["oferta"], "Distancia (km)": p["distancia_km"]} for p in pedidos])
    entregados = df[df["Estado"] == "Entregado"]
    tasa = len(entregados) / len(df) * 100
    kpis = [("Pedidos", len(df), ""), ("Entregados", len(entregados), f"{tasa:.0f}% del total"),
            ("Cancelados", int((df["Estado"] == "Cancelado").sum()), ""),
            ("Ventas de productos", colones(entregados["Productos"].sum()), "solo entregados"),
            ("Envíos pagados", colones(entregados["Envío"].sum()), "a repartidores"),
            ("Ticket promedio", colones((entregados["Productos"] + entregados["Envío"]).mean())
             if len(entregados) else "—", "")]
    for columna, (etiqueta, valor, detalle) in zip(st.columns(6), kpis):
        columna.markdown(estilos.kpi(etiqueta, valor, detalle), unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Pedidos por día")
        st.bar_chart(df.groupby("Día").size())
    with g2:
        st.markdown("#### Pedidos por tienda")
        st.bar_chart(df.groupby("Tienda").size())

    st.markdown("#### Ranking de repartidores")
    if len(entregados):
        ranking = (entregados.groupby("Repartidor").agg(Entregas=("Pedido", "count"), Ganado=("Envío", "sum"))
                   .sort_values("Entregas", ascending=False).reset_index())
        st.dataframe(ranking, hide_index=True)
    else:
        st.caption("Aún no hay entregas completadas en este periodo.")

    st.markdown("#### Detalle")
    st.dataframe(df, hide_index=True)
    st.download_button("⬇️ Exportar reporte CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       "reporte_pedidos.csv", "text/csv")
