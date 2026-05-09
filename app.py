from flask import Flask, render_template_string, request, redirect
from flask import send_from_directory
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# =========================
# GPS FUNCTIONS
# =========================

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


# =========================
# LOAD PHOTOS
# =========================

def cargar_fotos():

    resultados = []

    archivos = os.listdir(UPLOAD_FOLDER)

    for archivo in archivos:

        if archivo.lower().endswith((".jpg", ".jpeg", ".png")):

            ruta = os.path.join(UPLOAD_FOLDER, archivo)

            gps = obtener_gps(ruta)

            if gps:

                resultados.append({
                    "nombre": archivo,
                    "lat": gps["lat"],
                    "lon": gps["lon"]
                })

    return resultados


# =========================
# HTML
# =========================

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

<style>

body{
    margin:0;
    font-family:Arial;
    background:#111;
    color:white;
}

#map{
    width:100%;
    height:80vh;
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
    max-width:200px;
    border-radius:10px;
}

</style>

</head>

<body>

<form method="POST" action="/upload" enctype="multipart/form-data">

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

<script>

const fotos = {{ fotos|safe }};

let mapa = L.map('map').setView([-33.44, -70.65], 11);

L.tileLayer(
    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        maxZoom:19
    }
).addTo(mapa);

for(let foto of fotos){

    let marcador = L.marker(
        [foto.lat, foto.lon]
    ).addTo(mapa);

    marcador.bindPopup(
        `
        <b>${foto.nombre}</b>
        <br><br>

        <img src="/uploads/${foto.nombre}">
        `
    );
}

</script>

</body>
</html>

"""


# =========================
# ROUTES
# =========================

@app.route("/")
def inicio():

    fotos = cargar_fotos()

    return render_template_string(
        HTML,
        fotos=json.dumps(fotos)
    )


@app.route("/upload", methods=["POST"])
def upload():

    if "fotos" not in request.files:
        return redirect("/")

    archivos = request.files.getlist("fotos")

    for archivo in archivos:

        if archivo.filename == "":
            continue

        nombre = secure_filename(
            archivo.filename
        )

        ruta = os.path.join(
            UPLOAD_FOLDER,
            nombre
        )

        archivo.save(ruta)

    return redirect("/")


@app.route("/uploads/<filename>")
def uploads(filename):

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )


# =========================
# START
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )