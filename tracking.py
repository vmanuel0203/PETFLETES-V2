"""Simulación de tracking del repartidor, ETAs y enlaces de navegación externa.

La ubicación del repartidor es SIMULADA (avanza en línea recta a una velocidad urbana
constante: primero hacia la tienda y luego hacia el destino). Con GPS real haría falta un
componente de geolocalización del navegador, que no es 100% Python.
"""
import math
import random
from datetime import datetime

import tarifas

VELOCIDAD_KMH = 25.0
FMT = "%Y-%m-%d %H:%M:%S"


def enlace_waze(lat, lon):
    return f"https://waze.com/ul?ll={lat:.6f},{lon:.6f}&navigate=yes"


def enlace_google_maps(lat, lon):
    return f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lon:.6f}&travelmode=driving"


def segundos_desde(fecha, ahora=None):
    ahora = ahora or datetime.now()
    return max(0.0, (ahora - datetime.strptime(fecha, FMT)).total_seconds())


def posicion_inicial_repartidor(pedido_id, lat, lon):
    """Punto de partida del repartidor: 1.5 a 4 km de la tienda (determinista por pedido)."""
    rnd = random.Random(pedido_id)
    km = rnd.uniform(1.5, 4.0)
    rumbo = rnd.uniform(0, 2 * math.pi)
    d_lat = km * math.cos(rumbo) / 111.2
    d_lon = km * math.sin(rumbo) / (111.32 * math.cos(math.radians(lat)))
    return lat + d_lat, lon + d_lon


def _interpolar(a, b, f):
    f = min(1.0, max(0.0, f))
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def _minutos(segundos):
    return int(math.ceil(max(0.0, segundos) / 60.0))


def estado_tracking(pedido, factor=1.0):
    """Posición simulada, fase y ETAs. factor > 1 acelera la simulación (modo demo)."""
    origen = (pedido["origen_lat"], pedido["origen_lon"])
    destino = (pedido["destino_lat"], pedido["destino_lon"])
    inicio = posicion_inicial_repartidor(pedido["id"], *origen)

    t1 = tarifas.distancia_estimada_km(*inicio, *origen) / VELOCIDAD_KMH * 3600
    t2 = pedido["distancia_km"] / VELOCIDAD_KMH * 3600

    if pedido["estado"] == "Entregado":
        transcurrido = t1 + t2
    else:
        referencia = pedido.get("aceptado_en") or pedido["creado"]
        transcurrido = segundos_desde(referencia) * factor

    if transcurrido < t1:
        fase = "hacia_tienda"
        pos = _interpolar(inicio, origen, transcurrido / t1)
        eta_tienda, eta_destino = t1 - transcurrido, t2
        mensaje = "El repartidor va en camino a la tienda."
    elif transcurrido < t1 + t2:
        fase = "hacia_destino"
        pos = _interpolar(origen, destino, (transcurrido - t1) / t2)
        eta_tienda, eta_destino = 0.0, t1 + t2 - transcurrido
        mensaje = "Pedido recogido: el repartidor va en camino al destino."
    else:
        fase = "llego"
        pos = destino
        eta_tienda, eta_destino = 0.0, 0.0
        mensaje = "El repartidor llegó al destino."

    return {"lat": pos[0], "lon": pos[1], "fase": fase, "mensaje": mensaje,
            "eta_tienda_min": _minutos(eta_tienda), "eta_destino_min": _minutos(eta_destino)}
