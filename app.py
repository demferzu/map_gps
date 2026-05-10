from flask import (
    Flask,
    render_template_string,
    request,
    redirect
)

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from werkzeug.utils import secure_filename

import sqlite3
import os
import json
import io


# =====================================
# CONFIG
# =====================================

app = Flask(__name__)

DB_NAME = "mapa.db"

TEMP_FOLDER = "temp"

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)


# =====================================
# DATABASE
# =====================================

def iniciar_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS fotos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT UNIQUE,

            lat REAL,
            lon REAL,

            imagen BLOB

        )

    """)

    conn.commit()
    conn.close()


iniciar_db()


# =====================================
# GPS FUNCTIONS
# =====================================

def convertir_coordenadas(valor):

    grados = float(valor[0])
    minutos = float(valor[1])
    segundos = float(valor[2])

    return grados + (minutos / 60.0) + (segundos / 3600.0)


def obtener_gps(imagen_path):

    try:

        imagen = Image.open(imagen_path)

        exif = imagen._getexif()

        if not exif:
            return None

        gps_info = None

        for tag, valor in exif.items():

            nombre = TAGS.get(tag, tag)

            if nombre == "GPSInfo":
                gps_info = valor
                break

        if not gps_info:
            return None

        datos_gps = {}

        for clave in gps_info:

            nombre = GPSTAGS.get(clave, clave)

            datos_gps[nombre] = gps_info[clave]

        latitud = convertir_coordenadas(
            datos_gps["GPSLatitude"]
        )

        if datos_gps["GPSLatitudeRef"] == "S":
            latitud = -latitud

        longitud = convertir_coordenadas(
            datos_gps["GPSLongitude"]
        )

        if datos_gps["GPSLongitudeRef"] == "W":
            longitud = -longitud

        return {
            "lat": latitud,
            "lon": longitud
        }

    except:
        return None


# =====================================
# IMAGE COMPRESS
# =====================================

def comprimir_imagen(ruta):

    imagen = Image.open(ruta)

    imagen.thumbnail((1200, 1200))

    imagen.save(
        ruta,
        quality=70,
        optimize=True
    )


# =====================================
# DATABASE FUNCTIONS
# =====================================

def guardar_foto_db(
    nombre,
    lat,
    lon,
    ruta_imagen
):

    with open(ruta_imagen, "rb") as f:

        imagen_binaria = f.read()

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO fotos
        (nombre, lat, lon, imagen)
        VALUES (?, ?, ?, ?)
        """,
        (
            nombre,
            lat,
            lon,
            imagen_binaria
        )
    )

    conn.commit()
    conn.close()


def cargar_fotos_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT nombre, lat, lon
        FROM fotos
        """
    )

    datos = cursor.fetchall()

    conn.close()

    resultados = []

    for fila in datos:

        resultados.append({
            "nombre": fila[0],
            "lat": fila[1],
            "lon": fila[2]
        })

    return resultados


# =====================================
# HTML
# =====================================

HTML = """

<!DOCTYPE html>
<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Mapa GPS Fotos</title>

<link
rel="stylesheet"
href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
/>

<link
rel="stylesheet"
href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
/>

<link
rel="stylesheet"
href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
/>

<style>

body{
    margin:0;
    font-family:Arial;
    background:#111;
    color:white;
}

#map{
    width:100%;
    height:85vh;
}

form{
    padding:10px;
    background:#222;
}

button{
    padding:10px;
    border:none;
    border-radius:10px;
}

img{
    max-width:220px;
    border-radius:10px;
}

</style>

</head>

<body>

<form method="POST"
      action="/upload"
      enctype="multipart/form-data">

    <input
        type="file"
        name="fotos"
        multiple
        accept=".jpg,.jpeg,.png"
    >

    <button type="submit">
        Subir Fotos
    </button>

</form>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>

<script>

const fotos = {{ fotos|safe }};

let mapa = L.map('map').setView(
    [-33.44, -70.65],
    11
);

L.tileLayer(
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        maxZoom:19
    }
).addTo(mapa);


// ============================
// CLUSTER
// ============================

let cluster = L.markerClusterGroup();


// ============================
// MARKERS
// ============================

for(let foto of fotos){

    let marcador = L.marker(
        [foto.lat, foto.lon]
    );

    marcador.bindPopup(
        `
        <b>${foto.nombre}</b>

        <br><br>

        <img src="/imagen/${foto.nombre}">
        `
    );

    cluster.addLayer(marcador);
}

mapa.addLayer(cluster);

</script>

</body>
</html>

"""


# =====================================
# ROUTES
# =====================================

@app.route("/")
def inicio():

    fotos = cargar_fotos_db()

    return render_template_string(
        HTML,
        fotos=json.dumps(fotos)
    )


@app.route("/upload", methods=["POST"])
def upload():

    if "fotos" not in request.files:
        return redirect("/")

    archivos = request.files.getlist("fotos")

    if len(archivos) > 20:
        return "Máximo 20 fotos"

    for archivo in archivos:

        if archivo.filename == "":
            continue

        nombre = secure_filename(
            archivo.filename
        )

        ruta_temp = os.path.join(
            TEMP_FOLDER,
            nombre
        )

        archivo.save(ruta_temp)

        # Comprimir
        comprimir_imagen(ruta_temp)

        gps = obtener_gps(ruta_temp)

        if gps:

            guardar_foto_db(
                nombre,
                gps["lat"],
                gps["lon"],
                ruta_temp
            )

        # Elimina temporal
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)

    return redirect("/")


@app.route("/imagen/<nombre>")
def imagen(nombre):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT imagen
        FROM fotos
        WHERE nombre = ?
        """,
        (nombre,)
    )

    dato = cursor.fetchone()

    conn.close()

    if not dato:
        return "No encontrada", 404

    imagen_binaria = dato[0]

    return imagen_binaria, 200, {
        "Content-Type": "image/jpeg"
    }


# =====================================
# START
# =====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )