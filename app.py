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


# =====================================
# CONFIG
# =====================================

app = Flask(__name__)

DB_NAME = "mapa.db"

TEMP_FOLDER = "temp"

ADMIN_PASSWORD = "@Demferzu2002"

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)


# =====================================
# DATABASE
# =====================================

def iniciar_db():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    # TABLA FOTOS
    cursor.execute("""

        CREATE TABLE IF NOT EXISTS fotos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT UNIQUE,

            lat REAL,
            lon REAL,

            imagen BLOB

        )

    """)

    # CONFIGURACION
    cursor.execute("""

        CREATE TABLE IF NOT EXISTS config (

            id INTEGER PRIMARY KEY,

            uploads_habilitados INTEGER

        )

    """)

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (id, uploads_habilitados)
        VALUES (1, 0)
        """
    )

    conn.commit()
    conn.close()


iniciar_db()


# =====================================
# CONFIG FUNCTIONS
# =====================================

def uploads_habilitados():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT uploads_habilitados
        FROM config
        WHERE id = 1
        """
    )

    valor = cursor.fetchone()[0]

    conn.close()

    return valor == 1


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
    cursor:pointer;
}

img{
    max-width:220px;
    border-radius:10px;
}

.info{
    padding:10px;
    background:#222;
}

</style>

</head>

<body>

{% if uploads %}

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

{% else %}

<div class="info">
    Uploads deshabilitados
</div>

{% endif %}

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


// =====================================
// CLUSTER
// =====================================

let cluster = L.markerClusterGroup();


// =====================================
// MARKERS
// =====================================

for(let foto of fotos){

    let marcador = L.marker(
        [foto.lat, foto.lon]
    );

    marcador.bindPopup(
        `
        <b>${foto.nombre}</b>

        <br><br>

        <img src="/imagen/${foto.nombre}">

        <br><br>

        <a href="/eliminar/${foto.nombre}?password=@Demferzu2002">

            <button>
                Eliminar
            </button>

        </a>
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
        fotos=json.dumps(fotos),
        uploads=uploads_habilitados()
    )


@app.route("/upload", methods=["POST"])
def upload():

    if not uploads_habilitados():
        return "Uploads deshabilitados"

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

        # COMPRIME
        comprimir_imagen(ruta_temp)

        gps = obtener_gps(ruta_temp)

        if gps:

            guardar_foto_db(
                nombre,
                gps["lat"],
                gps["lon"],
                ruta_temp
            )

        # ELIMINA TEMP
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


@app.route("/eliminar/<nombre>")
def eliminar(nombre):

    password = request.args.get("password")

    if password != ADMIN_PASSWORD:
        return "Contraseña incorrecta"

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM fotos
        WHERE nombre = ?
        """,
        (nombre,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/toggle_uploads")
def toggle_uploads():

    password = request.args.get("password")

    if password != ADMIN_PASSWORD:
        return "Contraseña incorrecta"

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT uploads_habilitados
        FROM config
        WHERE id = 1
        """
    )

    estado = cursor.fetchone()[0]

    nuevo_estado = 0 if estado == 1 else 1

    cursor.execute(
        """
        UPDATE config
        SET uploads_habilitados = ?
        WHERE id = 1
        """,
        (nuevo_estado,)
    )

    conn.commit()
    conn.close()

    return f"Uploads habilitados: {nuevo_estado}"


# =====================================
# START
# =====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )