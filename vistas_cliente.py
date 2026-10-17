"""Pantallas del cliente: tiendas y catálogo, carrito/cotización, seguimiento y mapa."""
import streamlit as st

import db
import estilos
import tarifas
from componentes import (COLOR_TIENDA, ESTADOS, NAV_CARRITO, NAV_PEDIDOS, NAV_TIENDAS, ZONA_DEFECTO,
                         ZONAS, chat_pedido, mostrar_mapa, panel_pedido, puntos_ruta, selector_pin)
from estilos import colones

# ------------------------------------------------------------------ Carrito (estado)
CAT_ETIQUETAS = ["🏷️ Todas"] + [f"{emoji} {nombre}" for nombre, (emoji, _) in estilos.CATEGORIAS.items()]


def _categoria_de(etiqueta):
    for nombre in estilos.CATEGORIAS:
        if etiqueta and etiqueta.endswith(nombre):
            return nombre
    return None


def agregar_al_carrito(producto_id, tienda_id):
    carrito = st.session_state.carrito
    if carrito and st.session_state.tienda_carrito not in (None, tienda_id):
        carrito.clear()
        st.toast("Tu carrito era de otra tienda y se reinició.")
    st.session_state.tienda_carrito = tienda_id
    carrito[producto_id] = carrito.get(producto_id, 0) + 1
    st.toast("Añadido al carrito 🛒")


def cambiar_cantidad(producto_id, delta):
    carrito = st.session_state.carrito
    cantidad = carrito.get(producto_id, 0) + delta
    if cantidad <= 0:
        carrito.pop(producto_id, None)
    else:
        carrito[producto_id] = cantidad
    if not carrito:
        st.session_state.tienda_carrito = None


def vaciar_carrito():
    st.session_state.carrito.clear()
    st.session_state.tienda_carrito = None


def ir_a_carrito():
    st.session_state["nav"] = NAV_CARRITO


def ir_a_tiendas():
    st.session_state["nav"] = NAV_TIENDAS


def ver_tienda(tienda_id):
    st.session_state.tienda_sel = tienda_id


# ------------------------------------------------------- Tiendas y catálogo
def _grid_productos(productos, mostrar_tienda):
    if not productos:
        st.info("No hay productos para mostrar con ese filtro.")
        return
    for inicio in range(0, len(productos), 3):
        columnas = st.columns(3)
        for columna, p in zip(columnas, productos[inicio:inicio + 3]):
            with columna:
                with st.container(key=f"card_prod_{p['id']}"):
                    estilos.html(estilos.tarjeta_producto(p, mostrar_tienda))
                    st.button("🛒 Añadir", key=f"add_{p['id']}", type="primary", use_container_width=True,
                              on_click=agregar_al_carrito, args=(p["id"], p["tienda_id"]))


def _barra_carrito():
    carrito = st.session_state.carrito
    if not carrito:
        return
    productos = db.obtener_productos(list(carrito))
    unidades = sum(carrito.values())
    subtotal = sum(productos[pid]["precio"] * q for pid, q in carrito.items() if pid in productos)
    with st.container(key="card_barra"):
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.markdown(f"🛒 **{unidades}** producto(s) en tu carrito · Subtotal **{colones(subtotal)}**")
        c2.button("Ir al carrito →", key="ir_carrito_barra", type="primary", use_container_width=True,
                  on_click=ir_a_carrito)


def vista_tiendas():
    zona = st.session_state.get("zona_actual", ZONA_DEFECTO)
    zlat, zlon = ZONAS[zona]
    consulta = st.session_state.get("busqueda", "").strip()
    st.session_state.setdefault("cat", CAT_ETIQUETAS[0])

    if not consulta:
        estilos.html(estilos.hero(
            "Tú propones la tarifa", "Todo lo que tu mascota necesita, a tu puerta",
            "Elige una tienda, arma tu carrito y ofrece el precio del envío: los repartidores compiten por llevarte tu pedido."))

    seleccion = st.pills("Categorías", CAT_ETIQUETAS, selection_mode="single", key="cat",
                         label_visibility="collapsed")
    categoria = _categoria_de(seleccion)
    _barra_carrito()

    if consulta:
        st.markdown(f"#### Resultados para «{consulta}»")
        _grid_productos(db.buscar_productos(consulta, categoria), True)
        return

    tiendas = db.listar_tiendas()
    if not tiendas:
        st.info("Aún no hay tiendas disponibles.")
        return
    for t in tiendas:
        t["km"] = tarifas.distancia_estimada_km(zlat, zlon, t["lat"], t["lon"])
    tiendas.sort(key=lambda t: t["km"])
    ids = [t["id"] for t in tiendas]
    sel_id = st.session_state.get("tienda_sel")
    if sel_id not in ids:
        sel_id = ids[0]

    st.markdown(f"#### Tiendas cerca de {zona}")
    for inicio in range(0, len(tiendas), 3):
        columnas = st.columns(3)
        for columna, t in zip(columnas, tiendas[inicio:inicio + 3]):
            with columna:
                elegida = t["id"] == sel_id
                with st.container(key=f"{'cardsel' if elegida else 'card'}_tienda_{t['id']}"):
                    estilos.html(estilos.tarjeta_tienda(t, t["km"]))
                    st.button("Viendo su catálogo ✓" if elegida else "Ver catálogo", key=f"ver_{t['id']}",
                              type="primary" if elegida else "secondary", use_container_width=True,
                              on_click=ver_tienda, args=(t["id"],))

    tienda = next(t for t in tiendas if t["id"] == sel_id)
    st.markdown(f"#### Productos de {tienda['nombre']}")
    _grid_productos(db.listar_productos(sel_id, categoria), False)


# ------------------------------------------------------ Carrito y cotización
def vista_carrito():
    usuario = st.session_state.usuario
    st.markdown("## 🛒 Tu carrito")
    carrito = st.session_state.carrito
    if not carrito:
        with st.container(key="card_vacio"):
            st.markdown("### Tu carrito está vacío 🐾")
            st.write("Explora las tiendas y añade lo que tu mascota necesita.")
            st.button("Ver tiendas", type="primary", on_click=ir_a_tiendas)
        return

    tienda = db.obtener_tienda(st.session_state.tienda_carrito)
    productos = db.obtener_productos(list(carrito))
    for pid in [pid for pid in carrito if pid not in productos]:  # productos que ya no están disponibles
        carrito.pop(pid)
    if not carrito or tienda is None:
        vaciar_carrito()
        st.rerun()
    subtotal = sum(productos[pid]["precio"] * q for pid, q in carrito.items())
    peso = round(sum(productos[pid]["peso_kg"] * q for pid, q in carrito.items()), 2)

    col_main, col_res = st.columns([3, 2], gap="large")
    with col_main:
        # 1. Productos
        estilos.html(estilos.seccion(1, f"Productos · {tienda['nombre']}"))
        for pid, cantidad in list(carrito.items()):
            p = productos[pid]
            with st.container(key=f"card_linea_{pid}"):
                c1, c2, c3, c4, c5 = st.columns([6, 1.3, 1, 1.3, 1.3], vertical_alignment="center")
                c1.markdown(f"**{p['nombre']}**  \n{colones(p['precio'])} · {p['peso_kg']:g} kg")
                c2.button("−", key=f"menos_{pid}", on_click=cambiar_cantidad, args=(pid, -1))
                c3.markdown(f"<div style='text-align:center;font-weight:800'>{cantidad}</div>",
                            unsafe_allow_html=True)
                c4.button("+", key=f"mas_{pid}", on_click=cambiar_cantidad, args=(pid, 1))
                c5.button("🗑️", key=f"del_{pid}", on_click=cambiar_cantidad, args=(pid, -cantidad))
        st.caption(f"Subtotal {colones(subtotal)} · Peso total {peso:g} kg")

        # 2. Dirección de entrega
        estilos.html(estilos.seccion(2, "Dirección de entrega"))
        origen_lat = origen_lon = dest_lat = dest_lon = None
        origen_nombre = destino_nombre = ""
        with st.container(key="card_entrega"):
            st.markdown("**Punto de inicio**")
            modo_origen = st.radio("Inicio", ["Tienda", "Pin en el mapa"], horizontal=True,
                                   label_visibility="collapsed")
            if modo_origen == "Tienda":
                origen_lat, origen_lon, origen_nombre = tienda["lat"], tienda["lon"], tienda["nombre"]
                st.caption(f"📍 Se retira en {tienda['nombre']} · {tienda['direccion']}")
            else:
                pin = selector_pin("pin_origen", (tienda["lat"], tienda["lon"]), "Punto de inicio", "green")
                if pin:
                    origen_lat, origen_lon = pin
                    origen_nombre = "Pin de inicio ({:.4f}, {:.4f})".format(*pin)

            st.markdown("**Punto de entrega**")
            modo_destino = st.radio("Entrega", ["Pin en el mapa", "Zona rápida"], horizontal=True,
                                    label_visibility="collapsed")
            if modo_destino == "Zona rápida":
                zona = st.selectbox("Zona", list(ZONAS), key="zona_entrega")
                dest_lat, dest_lon = ZONAS[zona]
                destino_nombre = zona
            else:
                centro = (origen_lat, origen_lon) if origen_lat is not None else (tienda["lat"], tienda["lon"])
                pin = selector_pin("pin_destino", centro, "Punto de entrega", "red")
                if pin:
                    dest_lat, dest_lon = pin
                    destino_nombre = "Pin de entrega ({:.4f}, {:.4f})".format(*pin)
            senas = st.text_input("Señas exactas de entrega",
                                  placeholder="Ej: casa blanca, portón negro, 100 m sur de la escuela")

        # 3. Tarifa de envío
        estilos.html(estilos.seccion(3, "Tarifa de envío"))
        listo = origen_lat is not None and dest_lat is not None
        oferta, minimo, distancia = None, None, None
        if not listo:
            st.info("Fija el punto de inicio y el de entrega (paso 2) para cotizar el envío.")
        else:
            distancia = tarifas.distancia_estimada_km(origen_lat, origen_lon, dest_lat, dest_lon)
            desglose = tarifas.calcular_desglose(distancia, peso)
            minimo = tarifas.minimo_efectivo(desglose["total"], subtotal)  # nunca mayor al costo de los productos
            with st.container(key="card_tarifa"):
                estilos.html(
                    estilos.fila("Tarifa base", colones(desglose["base"]))
                    + estilos.fila(f"Distancia ({distancia:g} km × {colones(tarifas.COSTO_POR_KM)})",
                                   colones(desglose["distancia"]))
                    + estilos.fila(f"Peso extra ({desglose['kg_extra']:g} kg × {colones(tarifas.COSTO_POR_KG_EXTRA)})",
                                   colones(desglose["peso"]))
                    + estilos.fila("Mínimo sugerido", colones(minimo), fuerte=True)
                    + estilos.fila("Máximo (costo de los productos)", colones(subtotal)))
                if minimo >= subtotal:
                    oferta = int(subtotal)
                    st.info(f"El envío se fija en {colones(subtotal)}: no puede costar más que los productos.")
                else:
                    oferta = st.number_input("Tu oferta por el envío (₡)", min_value=int(minimo),
                                             max_value=int(subtotal), value=int(minimo), step=100,
                                             help="Una oferta mayor al mínimo suele ser aceptada más rápido, "
                                                  "pero no puede superar el costo de los productos. "
                                                  "Podrás subirla o bajarla de ₡100 en ₡100 mientras buscas repartidor.")
            mostrar_mapa([
                {"lat": origen_lat, "lon": origen_lon, "color": COLOR_TIENDA, "size": 250},
                {"lat": dest_lat, "lon": dest_lon, "color": "#D32F2F", "size": 250},
            ])

    # Resumen fijo y confirmación
    with col_res:
        with st.container(key="card_resumen"):
            st.markdown("### Resumen del pedido")
            unidades = sum(carrito.values())
            envio_txt = colones(oferta) if oferta else "Por cotizar"
            estilos.html(
                estilos.fila("Tienda", tienda["nombre"])
                + estilos.fila(f"Productos ({unidades})", colones(subtotal))
                + estilos.fila("Envío (tu oferta)", envio_txt)
                + estilos.total("Total estimado", colones(subtotal + (oferta or 0))))
            faltan = []
            if not listo:
                faltan.append("fijar inicio y entrega")
            if not senas.strip():
                faltan.append("escribir las señas")
            if faltan:
                st.caption("Falta: " + " y ".join(faltan) + ".")
            st.caption("Pagas los productos directo a la tienda (ella confirma tu pedido) y el envío al repartidor "
                       "al recibir. PetFletes no cobra ni procesa tarjetas.")
            if st.button("✅ Confirmar pedido", type="primary", use_container_width=True, disabled=bool(faltan)):
                items = [{"producto_id": pid, "nombre": productos[pid]["nombre"], "cantidad": q,
                          "precio": productos[pid]["precio"], "peso_kg": productos[pid]["peso_kg"]}
                         for pid, q in carrito.items()]
                try:
                    pedido_id = db.crear_pedido(
                        usuario["id"], tienda["id"], items, peso, subtotal, distancia, minimo, int(oferta),
                        origen_nombre, origen_lat, origen_lon, destino_nombre, senas.strip(), dest_lat, dest_lon)
                except ValueError as error:
                    st.error(str(error))
                    st.stop()
                st.session_state.pedido_id = pedido_id
                vaciar_carrito()
                st.session_state.pop("pin_origen", None)
                st.session_state.pop("pin_destino", None)
                st.session_state.ir_a = NAV_PEDIDOS
                st.rerun()
            st.button("Vaciar carrito", on_click=vaciar_carrito, use_container_width=True)




def vista_seguimiento():
    usuario = st.session_state.usuario
    st.header("📦 Seguimiento y entrega")
    pedidos = db.listar_pedidos_usuario(usuario["id"])
    if not pedidos:
        st.info("Aún no tienes pedidos. Crea uno desde «Tiendas».")
        return

    ids = [p["id"] for p in pedidos]
    por_id = {p["id"]: p for p in pedidos}
    indice = ids.index(st.session_state.pedido_id) if st.session_state.pedido_id in ids else 0
    seleccionado = st.selectbox(
        "Tus pedidos", ids, index=indice,
        format_func=lambda i: f"{ESTADOS[por_id[i]['estado']]} Pedido #{i} · {por_id[i]['tienda_nombre']} · {por_id[i]['estado']}",
    )
    pedido = por_id[seleccionado]
    activo = pedido["estado"] in ("Esperando tienda", "Buscando repartidor", "Tiempo agotado", "Aceptado")
    st.fragment(run_every=3 if activo else None)(panel_pedido)(pedido["id"], pedido["estado"])

    if pedido["estado"] == "Aceptado":
        with st.expander("💬 Chat con el repartidor", expanded=True):
            if pedido["repartidor_usuario_id"] is None:
                st.caption("Este repartidor es una cuenta de demostración y no responderá mensajes.")
            chat_pedido(pedido["id"])
        st.caption("¿Algún problema con el viaje? Reporta la incidencia en «Soporte».")


def vista_mapa():
    usuario = st.session_state.usuario
    st.header("🗺️ Mapa")
    tiendas = db.listar_tiendas()
    pedidos = db.listar_pedidos_usuario(usuario["id"])

    opciones = {0: "Solo tiendas"}
    for p in pedidos:
        opciones[p["id"]] = f"Pedido #{p['id']} · {p['origen_nombre']} → {p['destino_nombre']}"
    elegido = st.selectbox("Qué querés ver", list(opciones), format_func=lambda k: opciones[k])

    puntos = [{"lat": t["lat"], "lon": t["lon"], "color": COLOR_TIENDA, "size": 250} for t in tiendas]
    if elegido:
        puntos = puntos_ruta(next(p for p in pedidos if p["id"] == elegido))
    mostrar_mapa(puntos)

    st.subheader("Tiendas disponibles")
    for t in tiendas:
        with st.container(border=True):
            st.markdown(f"**{t['nombre']}**")
            st.caption(f"📍 {t['direccion']}")
            st.write(t["descripcion"])
