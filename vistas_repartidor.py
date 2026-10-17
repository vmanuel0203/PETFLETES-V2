"""Pantallas del repartidor: viajes disponibles, en curso y ganancias."""
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import db
import estilos
from componentes import (ESTADOS, NAV_EN_CURSO, botones_navegacion, chat_pedido, fmt_mmss,
                         form_calificacion, mostrar_mapa, puntos_ruta, texto_calificacion,
                         tracking_repartidor)
from estilos import colones


# ------------------------------------------------------------ Viajes disponibles
@st.fragment(run_every=4)
def _lista_disponibles():
    usuario = st.session_state.usuario
    rid = usuario["repartidor_id"]
    pedidos = db.listar_pedidos_disponibles()
    if not pedidos:
        st.info("No hay viajes con puja abierta ahora mismo. La lista se actualiza sola.")
    for inicio in range(0, len(pedidos), 2):
        columnas = st.columns(2)
        for columna, p in zip(columnas, pedidos[inicio:inicio + 2]):
            with columna:
                with st.container(key=f"card_viaje_{p['id']}"):
                    promedio, n = db.promedio_usuario(p["usuario_id"])
                    estilos.html(estilos.tarjeta_viaje(p, texto_calificacion(promedio, n),
                                                       fmt_mmss(p["segundos_restantes"])))
                    mia = db.obtener_oferta_repartidor(p["id"], rid)
                    if mia:
                        st.info(f"Tu contraoferta: {colones(mia['monto'])} · esperando al cliente.")
                    if st.button(f"✅ Aceptar viaje · {colones(p['oferta'])}", key=f"acep_{p['id']}",
                                 type="primary", use_container_width=True):
                        try:
                            if db.aceptar_viaje(p["id"], rid):
                                st.session_state.ir_a = NAV_EN_CURSO
                                st.rerun()
                            else:
                                st.warning("Otro repartidor ya tomó este viaje o la puja se cerró.")
                        except ValueError as error:
                            st.error(str(error))
                    with st.expander("Contraofertar y ver ruta"):
                        c1, c2 = st.columns([2, 1], vertical_alignment="center")
                        tope = max(500, int(p["tope_envio"]))
                        monto = c1.number_input("Tu contraoferta (₡)", min_value=500, max_value=tope, step=100,
                                                value=min(tope, int(mia["monto"] if mia else p["oferta"])),
                                                key=f"of_{p['id']}", label_visibility="collapsed")
                        if c2.button("Enviar", key=f"env_{p['id']}", use_container_width=True):
                            try:
                                db.enviar_oferta(p["id"], rid, monto)
                                st.toast("Contraoferta enviada ✅")
                                st.rerun(scope="fragment")
                            except ValueError as error:
                                st.error(str(error))
                        st.caption(f"Señas: {p['destino_senas']}")
                        for item in p["items"]:
                            st.write(f"• {item['cantidad']} × {item['nombre']}")
                        mostrar_mapa(puntos_ruta(p))
                        botones_navegacion(p)


def vista_disponibles():
    usuario = st.session_state.usuario
    st.markdown("## 🧭 Viajes disponibles")
    if usuario["repartidor_id"] is None:
        st.error("Tu cuenta no tiene perfil de repartidor.")
        return
    st.caption("Acepta un viaje a la tarifa del cliente o envía una contraoferta; "
               "si el cliente elige la tuya, el viaje es tuyo.")
    _lista_disponibles()


# ----------------------------------------------------------------- En curso
def vista_en_curso():
    usuario = st.session_state.usuario
    rid = usuario["repartidor_id"]
    st.markdown("## 🚚 Viajes en curso")
    if rid is None:
        st.error("Tu cuenta no tiene perfil de repartidor.")
        return
    c1, c2 = st.columns(2)
    c1.button("🔄 Actualizar", use_container_width=True)
    c2.toggle("⏩ Acelerar simulación x10 (demo)", key="acel_demo")

    entregas = db.listar_entregas_repartidor(rid)
    activas = [e for e in entregas if e["estado"] == "Aceptado"]
    if not activas:
        st.info("No tienes viajes en curso. Acepta uno en «Viajes disponibles».")
    for e in activas:
        with st.container(key=f"card_curso_{e['id']}"):
            estilos.html(estilos.chip_estado(e["estado"]) + estilos.chip(f"Pedido #{e['id']}", "gris"))
            st.markdown(f"**{e['origen_nombre']} → {e['destino_nombre']}**")
            st.caption(f"{e['distancia_km']:g} km · {e['peso_total']:g} kg · Señas: {e['destino_senas']}")
            st.write(f"Cliente: {e['cliente_nombre']} · Tel: {e['cliente_telefono'] or '—'}")
            estilos.html(
                estilos.fila("Productos (ya pagados a la tienda)", colones(e["subtotal"]))
                + estilos.fila("Cobrar al cliente: solo el envío", colones(e["oferta"]), fuerte=True))
            tracking_repartidor(e["id"])
            botones_navegacion(e)
            with st.expander("💬 Chat con el cliente"):
                chat_pedido(e["id"])
            if st.button("📦 Marcar como entregado", key=f"ent_{e['id']}", type="primary",
                         use_container_width=True):
                db.marcar_entregado_repartidor(e["id"], rid)
                st.rerun()

    por_calificar = [e for e in entregas
                     if e["estado"] == "Entregado" and not db.obtener_calificacion(e["id"], "repartidor")]
    if por_calificar:
        st.markdown("### ⭐ Pendientes de calificar")
        for e in por_calificar:
            with st.container(key=f"card_cal_{e['id']}"):
                st.caption(f"Pedido #{e['id']} · {e['destino_nombre']}")
                form_calificacion(e["id"], "repartidor", rid, f"al cliente {e['cliente_nombre']}")


# ---------------------------------------------------------------- Ganancias
def vista_ganancias():
    usuario = st.session_state.usuario
    rid = usuario["repartidor_id"]
    st.markdown("## 💰 Ganancias")
    if rid is None:
        st.error("Tu cuenta no tiene perfil de repartidor.")
        return
    periodo = st.pills("Periodo", ["Hoy", "7 días", "30 días", "Todo"], selection_mode="single",
                       key="periodo_ganancias", label_visibility="collapsed") or "Todo"
    dias = {"Hoy": 0, "7 días": 6, "30 días": 29}.get(periodo)
    desde = date.today() - timedelta(days=dias) if dias is not None else date(2000, 1, 1)

    entregas = [e for e in db.listar_entregas_repartidor(rid) if e["estado"] == "Entregado"
                and date.fromisoformat((e.get("entregado_en") or e["creado"])[:10]) >= desde]
    total = sum(e["oferta"] for e in entregas)
    promedio, n = db.promedio_repartidor(rid)
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(estilos.kpi("Ganado en envíos", colones(total)), unsafe_allow_html=True)
    k2.markdown(estilos.kpi("Viajes completados", len(entregas)), unsafe_allow_html=True)
    k3.markdown(estilos.kpi("Promedio por viaje", colones(total / len(entregas)) if entregas else "—"),
                unsafe_allow_html=True)
    k4.markdown(estilos.kpi("Calificación", f"{promedio:.1f} ⭐" if n else "—", f"{n} reseñas" if n else ""),
                unsafe_allow_html=True)

    if not entregas:
        st.info("Aún no hay viajes completados en este periodo.")
        return
    df = pd.DataFrame([{
        "Fecha": (e.get("entregado_en") or e["creado"])[:16], "Pedido": e["id"], "Tienda": e["tienda_nombre"],
        "Destino": e["destino_nombre"], "Distancia (km)": e["distancia_km"], "Ganado": e["oferta"],
    } for e in entregas])
    st.markdown("#### Ganancias por día")
    por_dia = df.assign(Día=df["Fecha"].str[:10]).groupby("Día")["Ganado"].sum()
    st.bar_chart(por_dia)
    st.markdown("#### Historial de viajes")
    st.dataframe(df, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       "mis_ganancias.csv", "text/csv")
