from flask import (
    Flask,
    render_template_string,
    request,
    redirect
)

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from werkzeug.utils import secure_filename

from supabase import create_client

import os
import json
import io


# =====================================
# CONFIG
# =====================================

app = Flask(__name__)

SUPABASE_URL = "https://hibosiwdcybnkkjvaxzt.supabase.co"

SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpYm9zaXdkY3libmtranZheHp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgzODQ1MDEsImV4cCI6MjA5Mzk2MDUwMX0.XRNkxB4ym71V43mYnWsQrlyDHH5TZtvlGKx9ResZKt0"

BUCKET = "fotos"

ADMIN_PASSWORD = "@Demferzu2002"

TEMP_FOLDER = "temp"

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =====================================
# GPS
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

    except Exception as e:

        print("ERROR GPS:", e)

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
# SUPABASE FUNCTIONS
# =====================================

def guardar_foto_supabase(
    nombre,
    lat,
    lon,
    ruta_imagen
):

    with open(ruta_imagen, "rb") as f:

        contenido = f.read()

    # SUBIR STORAGE
    supabase.storage.from_(BUCKET).upload(
        nombre,
        contenido,
        {
            "content-type": "image/jpeg"
        }
    )

    # URL PUBLICA
    url_imagen = (
        supabase
        .storage
        .from_(BUCKET)
        .get_public_url(nombre)
    )

    # GUARDAR DB
    supabase.table("fotos").insert({

        "nombre": nombre,
        "lat": lat,
        "lon": lon,
        "url": url_imagen

    }).execute()


def cargar_fotos():

    respuesta = (
        supabase
        .table("fotos")
        .select("*")
        .execute()
    )

    return respuesta.data


def eliminar_foto(nombre):

    # ELIMINAR STORAGE
    supabase.storage.from_(BUCKET).remove([
        nombre
    ])

    # ELIMINAR DB
    supabase.table("fotos") \
        .delete() \
        .eq("nombre", nombre) \
        .execute()


# =====================================
# HTML
# =====================================

HTML = """

<!DOCTYPE html>
<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Mapa GPS</title>

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

        <img src="${foto.url}">

        <br><br>

        <a href="/eliminar/${foto.nombre}?password=1234">

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

    fotos = cargar_fotos()

    return render_template_string(
        HTML,
        fotos=json.dumps(fotos)
    )


import traceback
import time


@app.route("/upload", methods=["POST"])
def upload():

    try:

        print("INICIO UPLOAD")

        if "fotos" not in request.files:
            print("NO HAY ARCHIVOS")
            return redirect("/")

        archivos = request.files.getlist("fotos")

        print("CANTIDAD:", len(archivos))

        for archivo in archivos:

            print("PROCESANDO")

            if archivo.filename == "":
                print("VACIO")
                continue

            nombre = (
                str(int(time.time()))
                + "_"
                + secure_filename(archivo.filename)
            )

            print("NOMBRE:", nombre)

            ruta_temp = os.path.join(
                TEMP_FOLDER,
                nombre
            )

            archivo.save(ruta_temp)

            print("GUARDADO TEMP")

            gps = obtener_gps(ruta_temp)

            print("GPS:", gps)

            if gps:

                comprimir_imagen(ruta_temp)

                print("COMPRESION OK")

                guardar_foto_supabase(
                    nombre,
                    gps["lat"],
                    gps["lon"],
                    ruta_temp
                )

                print("SUPABASE OK")

            else:

                print("SIN GPS")

            if os.path.exists(ruta_temp):
                os.remove(ruta_temp)

                print("TEMP ELIMINADO")

        print("UPLOAD TERMINADO")

        return redirect("/")

    except Exception as e:

        print("ERROR CRITICO:")
        print(str(e))

        traceback.print_exc()

        return f"ERROR: {e}"


@app.route("/eliminar/<nombre>")
def eliminar(nombre):

    password = request.args.get("password")

    if password != ADMIN_PASSWORD:
        return "Contraseña incorrecta"

    eliminar_foto(nombre)

    return redirect("/")


# =====================================
# START
# =====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )