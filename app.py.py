from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)

# ======================
# ⚙️ CONFIGURACIÓN
# ======================
CARPETA_DOCUMENTOS = "INSCRIPCIONES_DIGITALES"
CONTRASEÑA_SECRETARIA = "SanMartin2026"  # 🔑 CAMBIA TU CONTRASEÑA AQUÍ
os.makedirs(CARPETA_DOCUMENTOS, exist_ok=True)

# ======================
# 📸 CONVERSIÓN FOTO → DOCUMENTO DIGITAL
# ======================
def convertir_a_documento_digital(ruta_entrada, ruta_salida):
    try:
        img = cv2.imread(ruta_entrada)
        alto, ancho = img.shape[:2]

        escala = 500 / alto
        img_pequeña = cv2.resize(img, (0,0), fx=escala, fy=escala)
        gris = cv2.cvtColor(img_pequeña, cv2.COLOR_BGR2GRAY)
        gris = cv2.GaussianBlur(gris, (5,5), 0)

        bordes = cv2.Canny(gris, 75, 200)
        contornos, _ = cv2.findContours(bordes.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:5]

        nuevo_img = img
        for c in contornos:
            perimetro = cv2.arcLength(c, True)
            aproximacion = cv2.approxPolyDP(c, 0.02 * perimetro, True)
            if len(aproximacion) == 4:
                pts = aproximacion.reshape(4,2) / escala
                orden = np.zeros((4,2), dtype="float32")
                s = pts.sum(axis=1)
                orden[0] = pts[np.argmin(s)]
                orden[2] = pts[np.argmax(s)]
                diff = np.diff(pts, axis=1)
                orden[1] = pts[np.argmin(diff)]
                orden[3] = pts[np.argmax(diff)]

                (tl, tr, br, bl) = orden
                ancho_max = max(int(np.linalg.norm(tr - tl)), int(np.linalg.norm(br - bl)))
                alto_max = max(int(np.linalg.norm(bl - tl)), int(np.linalg.norm(br - tr)))

                destino = np.array([[0,0],[ancho_max-1,0],[ancho_max-1,alto_max-1],[0,alto_max-1]], dtype="float32")
                matriz = cv2.getPerspectiveTransform(orden, destino)
                nuevo_img = cv2.warpPerspective(img, matriz, (ancho_max, alto_max))
                break

        img_pil = Image.fromarray(cv2.cvtColor(nuevo_img, cv2.COLOR_BGR2RGB))
        mejorada = img_pil.convert('L')
        mejorada = ImageEnhance.Contrast(mejorada).enhance(1.8)
        mejorada = ImageEnhance.Brightness(mejorada).enhance(1.15)
        mejorada = mejorada.filter(ImageFilter.SHARPEN)
        mejorada.save(ruta_salida, quality=95)
        return True
    except:
        return False

# ======================
# 🖥️ PÁGINAS DEL SITIO WEB
# ======================

PAGINA_INICIO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inscripción Escolar | San Martín de Porres y Padre Jaime Gagnon</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Arial, sans-serif; }
        body { background: linear-gradient(135deg, #1e5799 0%, #2989d8 50%, #207cca 100%); min-height: 100vh; padding: 20px; }
        .contenedor { max-width: 900px; margin: 0 auto; }
        .cabecera { background: white; border-radius: 16px; padding: 30px; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.15); margin-bottom: 25px; }
        h1 { color: #154360; font-size: 28px; margin-bottom: 8px; }
        .subtitulo { color: #2874A6; font-size: 16px; margin-bottom: 15px; }
        .frase { background: linear-gradient(90deg, #F4D03F, #F8C471); color: #784212; padding: 15px 25px; border-radius: 12px; font-size: 18px; font-weight: bold; margin: 15px 0; }
        .motivo { background: #EAF2F8; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: justify; line-height: 1.7; color: #2C3E50; }
        .colegios { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 25px 0; }
        @media (max-width: 700px) { .colegios { grid-template-columns: 1fr; } }
        .colegio { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
        .colegio h3 { color: #1E8449; margin-bottom: 10px; }
        .colegio.sanmartin h3 { color: #2471A3; }
        .colegio.padrejaime h3 { color: #922B21; }
        .botones { display: flex; gap: 20px; margin-top: 30px; flex-wrap: wrap; justify-content: center; }
        .btn { padding: 18px 30px; border: none; border-radius: 12px; font-size: 17px; font-weight: bold; cursor: pointer; transition: all 0.3s; width: 320px; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.2); }
        .btn-secretaria { background: #283747; color: white; }
        .btn-padres { background: #239B56; color: white; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; }
        .modal.mostrar { display: flex; }
        .modal-contenido { background: white; padding: 30px; border-radius: 14px; width: 90%; max-width: 400px; text-align: center; }
        .modal-contenido h2 { margin-bottom: 20px; color: #2C3E50; }
        .modal-contenido input { width: 100%; padding: 12px; font-size: 16px; border: 2px solid #ccc; border-radius: 8px; margin-bottom: 15px; }
        .modal-btn { padding: 10px 25px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 5px; }
        .btn-aceptar { background: #283747; color: white; }
        .btn-cancelar { background: #ccc; color: #333; }
        .mensaje-error { color: red; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <div class="contenedor">
        <div class="cabecera">
            <h1>🎓 SISTEMA DE INSCRIPCIÓN ESCOLAR</h1>
            <p class="subtitulo">Transición: 6to de Primaria → 1ro de Secundaria</p>
            <div class="frase">✨ "De nosotros quieren y esperan grandes cosas" ✨</div>
        </div>

        <div class="motivo">
            <h3>📌 Nuestro Propósito</h3>
            <p>Bienvenidos. Este sistema ha sido creado con el firme propósito de facilitar y dignificar el proceso de inscripción escolar. Sabemos que depositan en nosotros su confianza y la esperanza de un futuro brillante para sus hijos e hijas. Por eso, nos esforzamos en ofrecer un servicio ágil, transparente y lleno de calidez. Aquí podrán presentar toda la documentación de forma sencilla; el sistema transformará sus fotos en documentos digitales perfectos, listos para ser revisados con prontitud.</p>
        </div>

        <div class="colegios">
            <div class="colegio sanmartin">
                <h3>🏫 Colegio San Martín de Porres</h3>
                <p>Una institución que camina con firmeza hacia la excelencia. Formamos corazones y mentes basados en valores, disciplina y respeto. Cada estudiante que pasa por nuestras aulas lleva consigo el compromiso de ser mejor cada día. Aquí se siembran las bases para grandes metas.</p>
            </div>
            <div class="colegio padrejaime">
                <h3>🏫 Unidad Educativa Padre Jaime Gagnon</h3>
                <p>Educar con el corazón y con la verdad. Así hemos trabajado siempre, guiados por principios de fe, solidaridad y amor al prójimo. Creemos en el potencial de cada niño y niña, acompañándolos con dedicación, cercanía y esperanza. Juntos construimos su porvenir.</p>
            </div>
        </div>

        <div class="botones">
            <button class="btn btn-secretaria" onclick="abrirModal()">🔐 ACCESO DE SECRETARÍA</button>
            <button class="btn btn-padres" onclick="window.location.href='/formulario'">✍️ PRESENTAR SOLICITUD</button>
        </div>
    </div>

    <!-- MODAL DE CONTRASEÑA -->
    <div id="modalAcceso" class="modal">
        <div class="modal-contenido">
            <h2>🔑 Acceso Restringido</h2>
            <p style="margin-bottom:15px;">Ingresa la contraseña de Secretaría:</p>
            <input type="password" id="clave" placeholder="Escribe la contraseña...">
            <br>
            <button class="modal-btn btn-cancelar" onclick="cerrarModal()">Cancelar</button>
            <button class="modal-btn btn-aceptar" onclick="verificarClave()">Ingresar</button>
            <p id="mensajeError" class="mensaje-error">Contraseña incorrecta</p>
        </div>
    </div>

    <script>
        function abrirModal() {
            document.getElementById('modalAcceso').classList.add('mostrar');
            document.getElementById('mensajeError').style.display = 'none';
            document.getElementById('clave').value = '';
        }
        function cerrarModal() {
            document.getElementById('modalAcceso').classList.remove('mostrar');
        }
        function verificarClave() {
            const clave = document.getElementById('clave').value;
            fetch('/verificar_clave', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({clave: clave})
            })
            .then(r => r.json())
            .then(datos => {
                if (datos.ok) {
                    window.location.href = '/secretaria';
                } else {
                    document.getElementById('mensajeError').style.display = 'block';
                }
            });
        }
    </script>
</body>
</html>
"""

FORMULARIO_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Formulario de Inscripción</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', Arial, sans-serif; }
        body { background: #f0f7ff; padding:20px; }
        .caja { max-width:750px; margin:0 auto; background:white; border-radius:16px; padding:30px; box-shadow:0 4px 20px rgba(0,0,0,0.1); }
        h1 { text-align:center; color:#1E8449; margin-bottom:25px; }
        .seccion { background:#f8f9fa; border-radius:10px; padding:18px; margin-bottom:18px; }
        h2 { color:#283747; font-size:17px; margin-bottom:12px; border-bottom:2px solid #ddd; padding-bottom:5px; }
        label { display:block; margin:10px 0 4px; font-weight:600; color:#333; }
        input { width:100%; padding:10px; border:2px solid #ccc; border-radius:7px; font-size:15px; }
        .doc-row { display:flex; align-items:center; gap:10px; margin:8px 0; flex-wrap:wrap; }
        .doc-nombre { flex:1; min-width:200px; font-weight:500; }
        .doc-btn { padding:8px 14px; background:#f39c12; color:white; border:none; border-radius:7px; cursor:pointer; font-weight:bold; }
        .doc-estado { padding:6px 10px; border-radius:5px; font-size:14px; }
        .pendiente { background:#ffeaa7; color:#856404; }
        .listo { background:#d4edda; color:#155724; }
        .boton-enviar { width:100%; padding:14px; background:#239B56; color:white; border:none; border-radius:10px; font-size:18px; font-weight:bold; margin-top:15px; cursor:pointer; }
        .boton-volver { display:inline-block; padding:10px 20px; background:#95a5a6; color:white; text-decoration:none; border-radius:8px; margin-bottom:15px; }
        .mensaje { margin-top:15px; padding:15px; border-radius:8px; display:none; }
        .exito { background:#d4edda; color:#155724; display:block !important; }
    </style>
</head>
<body>
    <div class="caja">
        <a href="/" class="boton-volver">← Volver al Inicio</a>
        <h1>✍️ Solicitud de Inscripción</h1>

        <div class="seccion">
            <h2>👤 Datos del Estudiante</h2>
            <label>Nombres y Apellidos Completos</label>
            <input type="text" id="est_nombre" required>
            <label>Fecha de Nacimiento</label>
            <input type="text" id="est_fnac" placeholder="DD/MM/AAAA">
            <label>Dirección Domiciliaria</label>
            <input type="text" id="est_dir">
            <label>Colegio de Procedencia</label>
            <input type="text" id="est_proc">
        </div>

        <div class="seccion">
            <h2>👨‍👩‍👦 Datos del Tutor / Responsable</h2>
            <label>Nombres y Apellidos del Tutor</label>
            <input type="text" id="tut_nombre" required>
            <label>Número de Carnet de Identidad</label>
            <input type="text" id="tut_ci">
            <label>Teléfono / Celular</label>
            <input type="text" id="tut_tel">
            <label>Correo Electrónico</label>
            <input type="email" id="tut_correo">
        </div>

        <div class="seccion">
            <h2>📷 Documentos (Toma foto → se convierte automáticamente)</h2>
            <p style="color:#555; font-size:14px; margin-bottom:10px;">Toma la foto clara, recta y bien iluminada. El sistema la recorta, endereza y mejora automáticamente.</p>
            <div id="lista-docs"></div>
        </div>

        <button class="boton-enviar" onclick="enviarFormulario()">📤 Enviar Solicitud de Inscripción</button>
        <div id="msg" class="mensaje"></div>
    </div>

    <script>
        const docs = [
            "📕 Libreta de Calificaciones",
            "📄 Certificado de Nacimiento",
            "🪪 Carnet de Identidad del Estudiante",
            "🪪 Carnet de Identidad del Tutor",
            "💡 Factura de Luz",
            "💧 Factura de Agua",
            "🗺️ Croquis de Ubicación"
        ];
        let archivos = {};
        const contenedor = document.getElementById('lista-docs');
        docs.forEach((nombre, i) => {
            const fila = document.createElement('div');
            fila.className = 'doc-row';
            fila.innerHTML = `
                <span class="doc-nombre">${nombre}</span>
                <input type="file" id="doc${i}" accept="image/*" onchange="subirArchivo(${i})">
                <span id="estado${i}" class="doc-estado pendiente">Pendiente</span>
            `;
            contenedor.appendChild(fila);
        });

        async function subirArchivo(indice) {
            const input = document.getElementById(`doc${indice}`);
            const estado = document.getElementById(`estado${indice}`);
            if (!input.files.length) return;
            estado.textContent = "⏳ Convirtiendo..."; estado.className = "doc-estado pendiente";
            
            const formData = new FormData();
            formData.append('archivo', input.files[0]);
            formData.append('indice', indice);

            try {
                const res = await fetch('/subir_documento', { method: 'POST', body: formData });
                const datos = await res.json();
                if (datos.ok) {
                    estado.textContent = "✅ Convertido y Guardado";
                    estado.className = "doc-estado listo";
                } else {
                    estado.textContent = "⚠️ Cargado";
                    estado.className = "doc-estado listo";
                }
                archivos[indice] = datos.ruta;
            } catch {
                estado.textContent = "❌ Error";
            }
        }

        async function enviarFormulario() {
            const msg = document.getElementById('msg');
            msg.style.display = 'none';

            const datos = {
                est_nombre: document.getElementById('est_nombre').value.trim(),
                est_fnac: document.getElementById('est_fnac').value.trim(),
                est_dir: document.getElementById('est_dir').value.trim(),
                est_proc: document.getElementById('est_proc').value.trim(),
                tut_nombre: document.getElementById('tut_nombre').value.trim(),
                tut_ci: document.getElementById('tut_ci').value.trim(),
                tut_tel: document.getElementById('tut_tel').value.trim(),
                tut_correo: document.getElementById('tut_correo').value.trim(),
                archivos: archivos
            };

            if (!datos.est_nombre || !datos.tut_nombre) {
                alert('Completa los datos del estudiante y del tutor.');
                return;
            }
            if (Object.keys(archivos).length < 7) {
                alert('Debes cargar los 7 documentos requeridos.');
                return;
            }

            try {
                const res = await fetch('/guardar_solicitud', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(datos)
                });
                const r = await res.json();
                if (r.ok) {
                    msg.className = "mensaje exito";
                    msg.innerHTML = `<strong>✅ ¡SOLICITUD REGISTRADA CON ÉXITO!</strong><br><br>Número de registro: <strong>${r.numero}</strong><br><br>Gracias por confiar en nosotros. Pronto nos comunicaremos contigo.`;
                    msg.style.display = 'block';
                    // Limpiar formulario
                    setTimeout(() => window.location.href = '/', 8000);
                }
            } catch {
                alert('Error al enviar. Inténtalo de nuevo.');
            }
        }
    </script>
</body>
</html>
"""

SECRETARIA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Secretaría — Solicitudes Recibidas</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', Arial, sans-serif; }
        body { background:#f4f6f7; padding:20px; }
        .caja { max-width:1000px; margin:0 auto; background:white; border-radius:16px; padding:30px; box-shadow:0 4px 20px rgba(0,0,0,0.1); }
        h1 { text-align:center; color:#283747; margin-bottom:20px; }
        table { width:100%; border-collapse:collapse; margin-top:15px; }
        th, td { padding:12px; text-align:left; border-bottom:1px solid #ddd; font-size:14px; }
        th { background:#283747; color:white; }
        .fila:hover { background:#f2f2f2; }
        .estado-pendiente { color:#d68910; font-weight:bold; }
        .estado-aprobada { color:#239B56; font-weight:bold; }
        .estado-observada { color:#cb4335; font-weight:bold; }
        .btn { padding:6px 12px; border:none; border-radius:6px; cursor:pointer; font-weight:bold; margin:2px; font-size:13px; }
        .btn-aprobar { background:#239B56; color:white; }
        .btn-observar { background:#f39c12; color:white; }
        .boton-volver { display:inline-block; padding:10px 20px; background:#95a5a6; color:white; text-decoration:none; border-radius:8px; margin-bottom:15px; }
        .aviso { background:#eafaf1; color:#1e8449; padding:12px; border-radius:8px; margin-bottom:15px; }
    </style>
</head>
<body>
    <div class="caja">
        <a href="/" class="boton-volver">← Volver al Inicio</a>
        <h1>📂 SOLICITUDES RECIBIDAS</h1>
        <div class="aviso">🔄 Lista actualizada al momento. Haz clic en "Aprobar" u "Observar" para cambiar el estado.</div>
        <table>
            <thead>
                <tr>
                    <th>Fecha y Hora</th>
                    <th>Estudiante</th>
                    <th>Tutor / CI</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody id="tabla"></tbody>
        </table>
    </div>

    <script>
        async function cargarLista() {
            const res = await fetch('/lista_solicitudes');
            const datos = await res.json();
            const tbody = document.getElementById('tabla');
            tbody.innerHTML = '';

            if (!datos.lista.length) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:30px; color:#666;">📭 Aún no hay solicitudes registradas.</td></tr>';
                return;
            }

            datos.lista.forEach((sol, i) => {
                let clase = 'estado-pendiente';
                if (sol.estado.includes('APROBADA')) clase = 'estado-aprobada';
                else if (sol.estado.includes('OBSERVADA')) clase = 'estado-observada';

                tbody.innerHTML += `
                    <tr class="fila">
                        <td>${sol.fecha}</td>
                        <td>${sol.estudiante}</td>
                        <td>${sol.tutor}</td>
                        <td class="${clase}">${sol.estado}</td>
                        <td>
                            <button class="btn btn-aprobar" onclick="cambiarEstado(${i}, 'APROBADA ✅')">Aprobar</button>
                            <button class="btn btn-observar" onclick="cambiarEstado(${i}, 'OBSERVADA ⚠️')">Observar</button>
                        </td>
                    </tr>
                `;
            });
        }

        async function cambiarEstado(indice, nuevoEstado) {
            await fetch('/cambiar_estado', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({indice, estado: nuevoEstado})
            });
            cargarLista();
        }

        // Cargar al entrar y cada 30 segundos
        cargarLista();
        setInterval(cargarLista, 30000);
    </script>
</body>
</html>
"""

# ======================
# 🛣️ RUTAS DEL SERVIDOR
# ======================

@app.route('/')
def inicio():
    return render_template_string(PAGINA_INICIO)

@app.route('/verificar_clave', methods=['POST'])
def verificar_clave():
    datos = request.get_json()
    if datos.get('clave') == CONTRASEÑA_SECRETARIA:
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route('/formulario')
def formulario():
    return render_template_string(FORMULARIO_HTML)

@app.route('/secretaria')
def secretaria():
    return render_template_string(SECRETARIA_HTML)

@app.route('/subir_documento', methods=['POST'])
def subir_documento():
    archivo = request.files['archivo']
    indice = request.form.get('indice')
    ruta_temporal = os.path.join(CARPETA_DOCUMENTOS, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{indice}.jpg")
    archivo.save(ruta_temporal)
    ruta_destino = os.path.join(CARPETA_DOCUMENTOS, f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{indice}.jpg")
    ok = convertir_a_documento_digital(ruta_temporal, ruta_destino)
    try: os.remove(ruta_temporal)
    except: pass
    return jsonify({"ok": ok, "ruta": ruta_destino})

@app.route('/guardar_solicitud', methods=['POST'])
def guardar_solicitud():
    d = request.get_json()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    numero = datetime.now().strftime("%Y%m%d%H%M%S")
    registro = f"""
============================================
FECHA: {fecha}
ESTUDIANTE: {d['est_nombre']}
F.NACIMIENTO: {d['est_fnac']}
DIRECCIÓN: {d['est_dir']}
PROCEDENCIA: {d['est_proc']}
TUTOR: {d['tut_nombre']}
CI TUTOR: {d['tut_ci']}
TELÉFONO: {d['tut_tel']}
CORREO: {d['tut_correo']}
DOCUMENTOS: {d['archivos']}
ESTADO: PENDIENTE ⏳
"""
    with open(os.path.join(CARPETA_DOCUMENTOS, "solicitudes.txt"), "a", encoding="utf-8") as f:
        f.write(registro)
    return jsonify({"ok": True, "numero": numero})

@app.route('/lista_solicitudes')
def lista_solicitudes():
    ruta = os.path.join(CARPETA_DOCUMENTOS, "solicitudes.txt")
    lista = []
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            bloques = f.read().strip().split("============================================")
            for b in bloques:
                if not b.strip(): continue
                fecha = estudiante = tutor = ci = estado = "---"
                for linea in b.strip().split("\n"):
                    if linea.startswith("FECHA:"): fecha = linea.split(":",1)[1].strip()
                    elif linea.startswith("ESTUDIANTE:"): estudiante = linea.split(":",1)[1].strip()
                    elif linea.startswith("TUTOR:"): tutor = linea.split(":",1)[1].strip()
                    elif linea.startswith("CI TUTOR:"): ci = linea.split(":",1)[1].strip()
                    elif linea.startswith("ESTADO:"): estado = linea.split(":",1)[1].strip()
                lista.append({"fecha":fecha, "estudiante":estudiante, "tutor":f"{tutor} — CI: {ci}", "estado":estado})
    return jsonify({"lista": lista})

@app.route('/cambiar_estado', methods=['POST'])
def cambiar_estado():
    d = request.get_json()
    ruta = os.path.join(CARPETA_DOCUMENTOS, "solicitudes.txt")
    if not os.path.exists(ruta):
        return jsonify({"ok": False})
    with open(ruta, "r", encoding="utf-8") as f:
        bloques = f.read().strip().split("============================================")
    idx = d['indice'] + 1
    if idx < len(bloques):
        lineas = bloques[idx].strip().split("\n")
        nuevas_lineas = []
        for l in lineas:
            nuevas_lineas.append(d['estado'] if l.startswith("ESTADO:") else l)
        bloques[idx] = "\n".join(nuevas_lineas) + "\n"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n============================================\n".join(bloques))
    return jsonify({"ok": True})

# ======================
# 🚀 INICIAR EL SITIO WEB
# ======================
if __name__ == "__main__":
    print("🌐 Sistema de Inscripción Iniciado...")
    print("📍 En tu computadora: http://localhost:5000")
    print("🔑 Contraseña de Secretaría:", CONTRASEÑA_SECRETARIA)
app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
