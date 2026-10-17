"""Fondo ilustrado de la pantalla de ingreso.

Si existe un archivo  assets/fondo.jpg  (o .jpeg, .png, .webp)  se usa como fondo.
Si no, se dibuja una escena ilustrada de respaldo (sala con perro, gato y repartidor).
"""
import base64
import os

import streamlit as st

DIR_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
EXTENSIONES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

SVG_FONDO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
<defs>
<linearGradient id="pared" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EFDDC0"/><stop offset="1" stop-color="#E0C49A"/></linearGradient>
<linearGradient id="piso" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#D9AF77"/><stop offset="1" stop-color="#B7844E"/></linearGradient>
<linearGradient id="luz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFF9E6"/><stop offset="1" stop-color="#F4DFB0"/></linearGradient>
</defs>
<rect width="1600" height="900" fill="url(#pared)"/>
<rect x="540" y="20" width="560" height="14" rx="7" fill="#8A5A2B"/>
<rect x="640" y="44" width="360" height="470" rx="14" fill="#CFA06B"/>
<rect x="662" y="66" width="316" height="426" rx="8" fill="url(#luz)"/>
<rect x="813" y="66" width="14" height="426" fill="#CFA06B"/>
<rect x="662" y="266" width="316" height="14" fill="#CFA06B"/>
<rect x="560" y="36" width="92" height="490" rx="18" fill="#D9A25E"/>
<rect x="988" y="36" width="92" height="490" rx="18" fill="#D9A25E"/>
<path d="M590 50V510M620 50V510M1018 50V510M1048 50V510" stroke="#C48D47" stroke-width="5"/>
<rect x="70" y="60" width="250" height="300" rx="10" fill="#9C6B3F"/>
<rect x="92" y="82" width="206" height="256" rx="4" fill="#F4E4C8"/>
<circle cx="195" cy="170" r="38" fill="#E9A84F"/>
<path d="M92 338L150 240L205 300L245 250L298 338Z" fill="#C4824A"/>
<rect x="1400" y="40" width="130" height="260" rx="10" fill="#9C6B3F"/>
<rect x="1418" y="58" width="94" height="224" rx="4" fill="#F4E4C8"/>
<circle cx="1465" cy="140" r="26" fill="#E9A84F"/>
<path d="M1418 282L1450 210L1480 250L1512 215L1512 282Z" fill="#C4824A"/>
<path d="M0 150Q170 270 330 195T560 150" fill="none" stroke="#7A5A3A" stroke-width="3"/>
<g fill="#FFE08A"><circle cx="30" cy="195" r="9"/><circle cx="95" cy="228" r="9"/><circle cx="160" cy="243" r="9"/><circle cx="225" cy="242" r="9"/><circle cx="290" cy="222" r="9"/><circle cx="355" cy="197" r="9"/><circle cx="420" cy="176" r="9"/><circle cx="490" cy="160" r="9"/></g>
<g fill="#FFE08A" opacity="0.35"><circle cx="30" cy="195" r="20"/><circle cx="95" cy="228" r="20"/><circle cx="160" cy="243" r="20"/><circle cx="225" cy="242" r="20"/><circle cx="290" cy="222" r="20"/><circle cx="355" cy="197" r="20"/><circle cx="420" cy="176" r="20"/><circle cx="490" cy="160" r="20"/></g>
<g fill="#3F7A4A"><ellipse cx="400" cy="480" rx="36" ry="120" transform="rotate(-28 400 480)"/><ellipse cx="450" cy="470" rx="34" ry="130" transform="rotate(8 450 470)"/><ellipse cx="500" cy="500" rx="32" ry="115" transform="rotate(32 500 500)"/><ellipse cx="430" cy="540" rx="30" ry="100" transform="rotate(-8 430 540)"/></g>
<g fill="#4E9159"><ellipse cx="420" cy="500" rx="22" ry="95" transform="rotate(-14 420 500)"/><ellipse cx="480" cy="520" rx="20" ry="90" transform="rotate(20 480 520)"/></g>
<rect x="395" y="630" width="110" height="120" rx="14" fill="#C0703E"/>
<g fill="#3F7A4A"><ellipse cx="1240" cy="430" rx="34" ry="115" transform="rotate(-22 1240 430)"/><ellipse cx="1290" cy="410" rx="32" ry="125" transform="rotate(10 1290 410)"/><ellipse cx="1340" cy="450" rx="30" ry="110" transform="rotate(30 1340 450)"/></g>
<rect x="1245" y="560" width="100" height="120" rx="14" fill="#C0703E"/>
<rect x="680" y="540" width="560" height="200" rx="40" fill="#C98B4A"/>
<rect x="0" y="730" width="1600" height="170" fill="url(#piso)"/>
<rect x="-60" y="580" width="560" height="340" rx="60" fill="#B8742E"/>
<rect x="-20" y="520" width="320" height="150" rx="44" fill="#C98B4A"/>
<rect x="90" y="610" width="170" height="150" rx="28" fill="#D9532E" transform="rotate(-8 175 685)"/>
<rect x="-10" y="720" width="150" height="150" rx="30" fill="#2F7F6F" transform="rotate(10 65 795)"/>
<ellipse cx="940" cy="830" rx="190" ry="130" fill="#E7B25A"/>
<ellipse cx="800" cy="610" rx="38" ry="78" transform="rotate(22 800 610)" fill="#B6772B"/>
<ellipse cx="1000" cy="610" rx="38" ry="78" transform="rotate(-22 1000 610)" fill="#B6772B"/>
<circle cx="900" cy="620" r="108" fill="#EFBE68"/>
<ellipse cx="900" cy="672" rx="66" ry="48" fill="#F7DBA6"/>
<ellipse cx="900" cy="645" rx="22" ry="15" fill="#3A2A1F"/>
<circle cx="860" cy="595" r="10" fill="#3A2A1F"/><circle cx="940" cy="595" r="10" fill="#3A2A1F"/>
<circle cx="864" cy="591" r="3.5" fill="#fff"/><circle cx="944" cy="591" r="3.5" fill="#fff"/>
<path d="M868 688Q900 722 932 688" fill="none" stroke="#3A2A1F" stroke-width="5" stroke-linecap="round"/>
<ellipse cx="922" cy="712" rx="19" ry="28" fill="#F08A9B"/>
<path d="M800 720Q900 765 1000 720" fill="none" stroke="#C0392B" stroke-width="18" stroke-linecap="round"/>
<circle cx="900" cy="764" r="15" fill="#F2C14E"/>
<ellipse cx="1190" cy="835" rx="100" ry="105" fill="#D9A56B"/>
<polygon points="1128,664 1138,596 1176,650" fill="#E2B27A"/><polygon points="1196,650 1234,596 1244,664" fill="#E2B27A"/>
<polygon points="1140,652 1144,616 1166,648" fill="#F0A6A6"/><polygon points="1206,648 1228,616 1232,652" fill="#F0A6A6"/>
<circle cx="1186" cy="710" r="76" fill="#E2B27A"/>
<path d="M1160 650L1168 668M1186 644V664M1212 650L1204 668" stroke="#A8743E" stroke-width="6" stroke-linecap="round"/>
<ellipse cx="1160" cy="705" rx="8" ry="11" fill="#2D2A25"/><ellipse cx="1212" cy="705" rx="8" ry="11" fill="#2D2A25"/>
<polygon points="1176,728 1196,728 1186,740" fill="#E77F8B"/>
<path d="M1186 740Q1170 756 1156 748M1186 740Q1202 756 1216 748" fill="none" stroke="#6B4A2B" stroke-width="3.5" stroke-linecap="round"/>
<rect x="1300" y="570" width="320" height="340" rx="64" fill="#8A4F2A"/>
<rect x="1400" y="545" width="90" height="120" rx="20" fill="#F4EDE0"/>
<circle cx="1445" cy="470" r="80" fill="#F2B58C"/>
<path d="M1368 462Q1445 330 1522 462Z" fill="#D9382E"/>
<ellipse cx="1500" cy="462" rx="72" ry="16" fill="#B82B22"/>
<circle cx="1440" cy="418" r="20" fill="#fff"/><circle cx="1440" cy="418" r="9" fill="#F4B1A6"/>
<circle cx="1418" cy="486" r="7" fill="#2D2A25"/><circle cx="1472" cy="486" r="7" fill="#2D2A25"/>
<path d="M1412 514Q1445 552 1480 514Z" fill="#7A2E1E"/>
<rect x="1240" y="660" width="320" height="250" rx="20" fill="#D2A36A"/>
<path d="M1240 700H1560" stroke="#B98550" stroke-width="6"/>
<circle cx="1400" cy="790" r="42" fill="#fff"/><circle cx="1400" cy="796" r="18" fill="#E9A84F"/>
<g fill="#E9A84F"><circle cx="1376" cy="768" r="9"/><circle cx="1400" cy="760" r="9"/><circle cx="1424" cy="768" r="9"/></g>
<circle cx="1330" cy="650" r="44" fill="#A6683A"/><circle cx="1298" cy="618" r="16" fill="#A6683A"/><circle cx="1362" cy="618" r="16" fill="#A6683A"/>
<ellipse cx="1330" cy="662" rx="20" ry="15" fill="#E2B58A"/>
</svg>"""


@st.cache_data(show_spinner=False)
def url_fondo():
    """URL (data URI) de la imagen de fondo: assets/fondo.* si existe, o la escena de respaldo."""
    for extension, mime in EXTENSIONES.items():
        ruta = os.path.join(DIR_ASSETS, "fondo" + extension)
        if os.path.exists(ruta):
            with open(ruta, "rb") as archivo:
                return f"data:{mime};base64," + base64.b64encode(archivo.read()).decode()
    return "data:image/svg+xml;base64," + base64.b64encode(SVG_FONDO.encode("utf-8")).decode()
