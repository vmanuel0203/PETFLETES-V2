"""Pantallas de la tienda aliada: pedidos por confirmar, catálogo y datos de la tienda."""
import pandas as pd
import streamlit as st

import db
import estilos
from estilos import colones


def _tienda_o_aviso():
    usuario = st.session_state.usuario
    tienda = db.obtener_tienda_de_usuario(usuario["id"])
    if tienda is None:
        st.error("Tu cuenta no tiene una tienda asociada. Contacta al administrador.")
    elif not tienda["activa"]:
        st.warning("⏳ Tu tienda está pendiente de aprobación: todavía no aparece para los clientes.")
    return tienda


# ------------------------------------------------------------------ Pedidos
def _tarjeta_confirmar(p, uid):
    with st.container(key=f"card_tconf_{p['id']}"):
        estilos.html(estilos.chip_estado(p["estado"]) + estilos.chip(f"Pedido #{p['id']}", "gris"))
        st.write(f"**Cliente:** {p['cliente_nombre']} · Tel: {p['cliente_telefono'] or '—'}")
        for item in p["items"]:
            st.write(f"• {item['cantidad']} × {item['nombre']} ({colones(item['precio'] * item['cantidad'])})")
        estilos.html(estilos.fila("Productos (lo que debe pagarte el cliente)", colones(p["subtotal"]), fuerte=True)
                     + estilos.fila("Envío (lo cobra el repartidor, no tú)", colones(p["oferta"])))
        st.caption("Confirma solo cuando hayas recibido el pago de los productos (SINPE Móvil o efectivo). "
                   "Al confirmar, el pedido se prepara y se abre la búsqueda de repartidor.")
        if st.button("✅ Confirmar pago y preparar", key=f"conf_{p['id']}", type="primary",
                     use_container_width=True):
            if db.confirmar_pedido_tienda(p["id"], uid):
                st.toast("Pedido confirmado ✅")
            else:
                st.warning("Este pedido ya no está esperando confirmación.")
            st.rerun(scope="fragment")
        with st.expander("No puedo atender este pedido / no recibí el pago"):
            nota = st.text_input("Motivo (opcional, lo verá el cliente)", key=f"nota_{p['id']}", max_chars=300)
            if st.button("Rechazar pedido", key=f"rech_{p['id']}", use_container_width=True):
                db.rechazar_pedido_tienda(p["id"], uid, nota)
                st.rerun(scope="fragment")


def _tarjeta_preparacion(p, uid):
    with st.container(key=f"card_tprep_{p['id']}"):
        estilos.html(estilos.chip_estado(p["estado"]) + estilos.chip(f"Pedido #{p['id']}", "gris")
                     + (estilos.chip("📦 Listo para recoger", "verde") if p["listo_en"] else ""))
        for item in p["items"]:
            st.write(f"• {item['cantidad']} × {item['nombre']}")
        st.caption(f"Cliente: {p['cliente_nombre']} · Repartidor: {p['repartidor_nombre'] or 'aún sin asignar'}")
        if not p["listo_en"] and st.button("📦 Marcar listo para recoger", key=f"listo_{p['id']}",
                                           type="primary", use_container_width=True):
            db.marcar_listo_tienda(p["id"], uid)
            st.rerun(scope="fragment")


@st.fragment(run_every=5)
def _lista_pedidos(uid):
    pedidos = db.listar_pedidos_tienda(uid)
    por_confirmar = [p for p in pedidos if p["estado"] == db.E_ESPERA]
    activos = [p for p in pedidos if p["estado"] in (db.E_BUSCANDO, db.E_AGOTADO, db.E_ACEPTADO)]
    historial = [p for p in pedidos if p["estado"] in (db.E_ENTREGADO, db.E_CANCELADO)]

    st.markdown(f"### 🔔 Por confirmar ({len(por_confirmar)})")
    if not por_confirmar:
        st.info("No hay pedidos esperando tu confirmación. Esta lista se actualiza sola.")
    for p in por_confirmar:
        _tarjeta_confirmar(p, uid)
    st.markdown(f"### 🧑‍🍳 En preparación y en camino ({len(activos)})")
    if not activos:
        st.caption("Nada en preparación por ahora.")
    for p in activos:
        _tarjeta_preparacion(p, uid)
    if historial:
        st.markdown("### 🗂️ Historial")
        st.dataframe(pd.DataFrame([{
            "Pedido": p["id"], "Fecha": p["creado"][:16], "Estado": p["estado"], "Cliente": p["cliente_nombre"],
            "Productos": p["subtotal"], "Nota": p["nota_tienda"] or ""} for p in historial]), hide_index=True)


def vista_pedidos_tienda():
    st.markdown("## 📥 Pedidos")
    if _tienda_o_aviso() is None:
        return
    _lista_pedidos(st.session_state.usuario["id"])


# ----------------------------------------------------------------- Catálogo
def vista_catalogo_tienda():
    uid = st.session_state.usuario["id"]
    st.markdown("## 🛍️ Mi catálogo")
    if _tienda_o_aviso() is None:
        return
    tienda = db.obtener_tienda_de_usuario(uid)
    productos = db.listar_productos(tienda["id"], solo_activos=False)
    if productos:
        st.dataframe(pd.DataFrame([{
            "ID": p["id"], "Producto": p["nombre"], "Categoría": p["categoria"], "Precio": p["precio"],
            "Peso (kg)": p["peso_kg"], "Estado": "Activo" if p["activo"] else "Oculto"} for p in productos]),
            hide_index=True)
        with st.expander("✏️ Editar producto"):
            sel = st.selectbox("Producto", [p["id"] for p in productos],
                               format_func=lambda i: next(p["nombre"] for p in productos if p["id"] == i),
                               key="tienda_editar_producto")
            p = next(x for x in productos if x["id"] == sel)
            with st.form(f"form_tienda_editar_{sel}"):
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
                    db.actualizar_producto_tienda(uid, sel, nombre, precio, peso, categoria, activo)
                    st.success("Producto actualizado.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    else:
        st.info("Aún no tienes productos. Agrega el primero abajo.")
    with st.expander("➕ Agregar producto", expanded=not productos):
        with st.form("form_tienda_nuevo_producto", clear_on_submit=True):
            nombre = st.text_input("Nombre del producto")
            c1, c2, c3 = st.columns(3)
            precio = c1.number_input("Precio (₡)", min_value=100, step=100, value=5000)
            peso = c2.number_input("Peso (kg)", min_value=0.0, step=0.1, value=1.0)
            categoria = c3.selectbox("Categoría", db.CATEGORIAS)
            crear = st.form_submit_button("Agregar producto", type="primary")
        if crear:
            try:
                db.crear_producto_tienda(uid, nombre, precio, peso, categoria)
                st.success("Producto agregado.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))


# --------------------------------------------------------------- Mi tienda
def vista_mi_tienda():
    uid = st.session_state.usuario["id"]
    st.markdown("## 🏪 Mi tienda")
    tienda = _tienda_o_aviso()
    if tienda is None:
        return
    st.caption("El número SINPE Móvil es el que verá el cliente para pagarte los productos.")
    with st.form("form_mi_tienda"):
        nombre = st.text_input("Nombre de la tienda", value=tienda["nombre"])
        direccion = st.text_input("Dirección", value=tienda["direccion"])
        descripcion = st.text_input("Descripción", value=tienda["descripcion"] or "")
        c1, c2 = st.columns(2)
        sinpe = c1.text_input("SINPE Móvil de la tienda", value=tienda["sinpe"] or "", placeholder="8888-0000")
        telefono = c2.text_input("Teléfono de contacto", value=tienda["telefono"] or "")
        guardar = st.form_submit_button("Guardar cambios", type="primary")
    if guardar:
        try:
            db.actualizar_mi_tienda(uid, nombre, direccion, descripcion, sinpe, telefono)
            st.success("Datos actualizados.")
            st.rerun()
        except ValueError as error:
            st.error(str(error))
