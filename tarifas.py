"""Algoritmo de tarifas de PetFletes (valores en colones costarricenses)."""
import math

TARIFA_BASE = 1500          # ₡ fijos por servicio
COSTO_POR_KM = 300          # ₡ por kilómetro recorrido
PESO_LIBRE_KG = 5.0         # kg incluidos sin recargo
COSTO_POR_KG_EXTRA = 120    # ₡ por cada kg sobre el peso libre
FACTOR_RUTA = 1.3           # la distancia en carretera es ~30% mayor a la línea recta
REDONDEO = 50               # el monto se redondea hacia arriba a múltiplos de ₡50


def distancia_estimada_km(lat1, lon1, lat2, lon2):
    """Distancia estimada por carretera (Haversine x factor de ruta), en km."""
    radio_tierra_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat = p2 - p1
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    linea_recta = 2 * radio_tierra_km * math.asin(math.sqrt(a))
    return round(linea_recta * FACTOR_RUTA, 2)


def calcular_desglose(distancia_km, peso_kg):
    """Devuelve el detalle de la tarifa mínima sugerida (según el algoritmo)."""
    distancia_km = max(0.0, float(distancia_km))
    peso_kg = max(0.0, float(peso_kg))
    costo_distancia = distancia_km * COSTO_POR_KM
    kg_extra = max(0.0, peso_kg - PESO_LIBRE_KG)
    costo_peso = kg_extra * COSTO_POR_KG_EXTRA
    bruto = TARIFA_BASE + costo_distancia + costo_peso
    total = int(math.ceil(bruto / REDONDEO) * REDONDEO)
    return {
        "base": TARIFA_BASE,
        "distancia": round(costo_distancia),
        "peso": round(costo_peso),
        "kg_extra": round(kg_extra, 2),
        "total": total,
    }


def calcular_tarifa_minima(distancia_km, peso_kg):
    """Monto Mínimo Sugerido (en colones) = base + km * 300 + extra por peso."""
    return calcular_desglose(distancia_km, peso_kg)["total"]


def tope_envio(subtotal):
    """Regla del proyecto: el envío nunca puede costar más que los productos."""
    return int(subtotal)


def minimo_efectivo(minimo_algoritmo, subtotal):
    """Mínimo de envío efectivo = el menor entre el mínimo del algoritmo y el tope."""
    return min(int(minimo_algoritmo), tope_envio(subtotal))


if __name__ == "__main__":
    # Ejemplo: 6 km con 12 kg -> 1500 + 1800 + (7 kg extra * 120) = 4140 -> 4150
    print(calcular_tarifa_minima(6, 12))
