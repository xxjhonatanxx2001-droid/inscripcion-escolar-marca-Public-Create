from flask import Flask, render_template_string, request, jsonify, send_from_directory, make_response
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
import os
import re
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle

app = Flask(__name__)

# ======================
# ⚙️ CONFIGURACIÓN
# ======================
CARPETA_DOCUMENTOS = "INSCRIPCIONES_DIGITALES"
CONTRASEÑA_SECRETARIA = "SanMartin2026"
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
# 📄 LEER SOLICITUDES
# ======================
def leer_solicitudes():
    ruta = os.path.join(CARPETA_DOCUMENTOS, "solicitudes.txt")
    lista = []
    if not os.path.exists(ruta):
        return lista
    with open(ruta, "r", encoding="utf-8") as f:
        bloques = f.read().strip().split("============================================")
        for idx, b in enumerate(bloques):
            if not b.strip(): continue
            datos = {"indice": idx}
            for linea in b.strip().split("\n"):
                if ":" in linea:
                    clave, valor = linea.split(":", 1)
                    datos[clave.strip()] = valor.strip()
            lista.append(datos)
    return lista

# ======================
# 🔧 PARSEAR DOCUMENTOS
# ======================
def parsear_documentos(texto):
    if not texto or texto.strip() == "":
        return {}
    resultado = {}
    coincidencias = re.findall(r"'(\d+)'\s*:\s*'([^']+)'", texto)
    for clave, valor in coincidencias:
        resultado[int(clave)] = valor
    return resultado

# ======================
# 📄 GENERAR PDF COMPLETO
# ======================
def generar_pdf_solicitud(sol):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Title'], fontSize=18, spaceAfter=12, textColor=colors.HexColor('#154360'))
    estilo_subtitulo = ParagraphStyle('Subtitulo', parent=estilos['Heading2'], fontSize=13, spaceAfter=8, textColor=colors.HexColor('#283747'))
    estilo_normal = ParagraphStyle('Normal', parent=estilos['Normal'], fontSize=11, spaceAfter=4)

    nombres_docs = [
        "Libreta de Calificaciones",
        "Certificado de Nacimiento",
        "Carnet Estudiante — Delantera",
        "Carnet Estudiante — Trasera",
        "Carnet Tutor — Delantera",
        "Carnet Tutor — Trasera",
        "Factura de Luz",
        "Factura de Agua",
        "Croquis de Ubicación"
    ]

    contenido = []
    contenido.append(Paragraph("SOLICITUD DE INSCRIPCIÓN ESCOLAR", estilo_titulo))
    contenido.append(Paragraph("Colegio San Martín de Porres / U.E. Padre Jaime Gagnon", estilo_subtitulo))
    contenido.append(Spacer(1, 0.3*cm))
    contenido.append(Paragraph(f"<b>Número de Registro:</b> {sol.get('NÚMERO REGISTRO', '---')}", estilo_normal))
    contenido.append(Paragraph(f"<b>Fecha y Hora:</b> {sol.get('FECHA', '---')}", estilo_normal))
    contenido.append(Paragraph(f"<b>Estado:</b> {sol.get('ESTADO', 'PENDIENTE')}", estilo_normal))
    contenido.append(Spacer(1, 0.4*cm))

    contenido.append(Paragraph("DATOS DEL ESTUDIANTE", estilo_subtitulo))
    tabla_est = [
        ["Nombre Completo:", sol.get('ESTUDIANTE', '---')],
        ["Fecha de Nacimiento:", sol.get('F.NACIMIENTO', '---')],
        ["Dirección:", sol.get('DIRECCIÓN', '---')],
        ["Colegio de Procedencia:", sol.get('PROCEDENCIA', '---')]
    ]
    t1 = Table(tabla_est, colWidths=[5*cm, 11*cm])
    t1.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f2f2f2')),
        ('FONTWEIGHT', (0,0), (0,-1), 'bold'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    contenido.append(t1)
    contenido.append(Spacer(1, 0.4*cm))

    contenido.append(Paragraph("DATOS DEL TUTOR / RESPONSABLE", estilo_subtitulo))
    tabla_tut = [
        ["Nombre Completo:", sol.get('TUTOR', '---')],
        ["Carnet de Identidad:", sol.get('CI TUTOR', '---')],
        ["Teléfono / Celular:", sol.get('TELÉFONO', '---')],
        ["Correo Electrónico:", sol.get('CORREO', '---')]
    ]
    t2 = Table(tabla_tut, colWidths=[5*cm, 11*cm])
    t2.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f2f2f2')),
        ('FONTWEIGHT', (0,0), (0,-1), 'bold'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    contenido.append(t2)
    contenido.append(Spacer(1, 0.5*cm))

    contenido.append(Paragraph("DOCUMENTOS ADJUNTOS", estilo_subtitulo))
    docs = parsear_documentos(sol.get('DOCUMENTOS', '{}'))
    for clave in sorted(docs.keys()):
        ruta = docs[clave]
        nombre_doc = nombres_docs[int(clave)] if int(clave) < len(nombres_docs) else f"Documento {clave}"
        contenido.append(Paragraph(f"📄 {nombre_doc}", ParagraphStyle('doc', parent=estilo_normal, fontSize=10, spaceAfter=2, textColor=colors.HexColor('#2471A3'))))
        if os.path.exists(ruta):
            try:
                img = RLImage(ruta, width=14*cm, height=9*cm)
                img.hAlign = 'CENTER'
                contenido.append(img)
                contenido.append(Spacer(1, 0.2*cm))
            except:
                contenido.append(Paragraph("⚠️ No se pudo cargar la imagen", estilo_normal))
                contenido.append(Spacer(1, 0.2*cm))

    doc.build(contenido)
    buffer.seek(0)
    return buffer

# ======================
# 🖥️ PÁGINA DE INICIO
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
        .botones { display: flex; gap: 15px; margin-top: 30px; flex-wrap: wrap; justify-content: center; }
        .btn { padding: 16px 24px; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; flex: 1 1 250px; text-align: center; text-decoration: none; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.2); }
        .btn-secretaria { background: #283747; color: white; }
        .btn-padres { background: #239B56; color: white; }
        .btn-seguimiento { background: #D68910; color: white; }
        .btn-publico { background: #8E44AD; color: white; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; z-index: 100; }
        .modal.mostrar { display: flex; }
        .modal-contenido { background: white; padding: 30px; border-radius: 14px; width: 90%; max-width: 450px; max-height: 90vh; overflow-y: auto; }
        .modal-contenido h2 { margin-bottom: 20px; color: #2C3E50; }
        .modal-contenido input { width: 100%; padding: 12px; font-size: 16px; border: 2px solid #ccc; border-radius: 8px; margin-bottom: 15px; }
        .modal-btn { padding: 10px 25px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 5px; }
        .btn-aceptar { background: #283747; color: white; }
        .btn-cancelar { background: #ccc; color: #333; }
        .mensaje-error { color: red; margin-top: 10px; display: none; }
        .resultado { margin-top:15px; padding:15px; border-radius:8px; display:none; }
        .aprobada { background:#d4edda; color:#155724; display:block !important; }
        .pendiente { background:#fff3cd; color:#856404; display:block !important; }
        .observada { background:#f8d7da; color:#721c24; display:block !important; }
        .lista-publica { margin-top:15px; text-align:left; }
        .lista-publica h4 { margin-top:12px; color:#2C3E50; }
        .ok-item { color:#239B56; padding:4px 0; }
        .obs-item { color:#cb4335; padding:4px 0; }
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
            <p>Bienvenidos. Este sistema facilita el proceso de inscripción escolar. Aquí puedes presentar documentación, dar seguimiento y revisar el estado de cada solicitud.</p>
        </div>
        <div class="colegios">
            <div class="colegio sanmartin">
                <h3>🏫 Colegio San Martín de Porres</h3>
                <p>Formamos corazones y mentes basados en valores, disciplina y respeto.</p>
            </div>
            <div class="colegio padrejaime">
                <h3>🏫 U.E. Padre Jaime Gagnon</h3>
                <p>Educar con el corazón y con la verdad. Fe, solidaridad y amor al prójimo.</p>
            </div>
        </div>
        <div class="botones">
            <button class="btn btn-padres" onclick="window.location.href='/formulario'">✍️ PRESENTAR SOLICITUD</button>
            <button class="btn btn-seguimiento" onclick="abrirSeguimiento()">🔍 SEGUIMIENTO DE SOLICITUD</button>
            <button class="btn btn-publico" onclick="abrirPublico()">📋 LISTA DE APROBADOS</button>
            <button class="btn btn-secretaria" onclick="abrirModal()">🔐 ACCESO DE SECRETARÍA</button>
        </div>
    </div>
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
    <div id="modalSeguimiento" class="modal">
        <div class="modal-contenido">
            <h2>🔍 Seguimiento de Solicitud</h2>
            <p style="margin-bottom:10px;">Escribe el Número de Registro:</p>
            <input type="text" id="numeroRegistro" placeholder="Ej: 20260827143022">
            <button class="modal-btn btn-aceptar" onclick="consultarEstado()">Consultar</button>
            <button class="modal-btn btn-cancelar" onclick="cerrarSeguimiento()">Cerrar</button>
            <div id="resultadoSeg" class="resultado"></div>
        </div>
    </div>
    <div id="modalPublico" class="modal">
        <div class="modal-contenido lista-publica">
            <h2>📋 Estado de Solicitudes</h2>
            <div id="contenidoPublico"></div>
            <button class="modal-btn btn-cancelar" onclick="cerrarPublico()" style="margin-top:15px;">Cerrar</button>
        </div>
    </div>
    <script>
        function abrirModal() { document.getElementById('modalAcceso').classList.add('mostrar'); document.getElementById('mensajeError').style.display='none'; document.getElementById('clave').value=''; }
        function cerrarModal() { document.getElementById('modalAcceso').classList.remove('mostrar'); }
        function verificarClave() {
            fetch('/verificar_clave', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({clave: document.getElementById('clave').value}) })
            .then(r=>r.json()).then(d=>{ if(d.ok) window.location.href='/secretaria'; else document.getElementById('mensajeError').style.display='block'; });
        }
        function abrirSeguimiento() { document.getElementById('modalSeguimiento').classList.add('mostrar'); document.getElementById('resultadoSeg').style.display='none'; document.getElementById('numeroRegistro').value=''; }
        function cerrarSeguimiento() { document.getElementById('modalSeguimiento').classList.remove('mostrar'); }
        function consultarEstado() {
            fetch('/consultar_registro?numero='+encodeURIComponent(document.getElementById('numeroRegistro').value.trim()))
            .then(r=>r.json()).then(d=>{
                const res=document.getElementById('resultadoSeg'); res.style.display='none';
                if(!d.encontrado){ res.className='resultado observada'; res.innerHTML='❌ No encontrado. Verifica el número.'; }
                else if(d.estado.includes('APROBADA')){ res.className='resultado aprobada'; res.innerHTML='✅ ¡SOLICITUD APROBADA! Pronto nos comunicaremos.'; }
                else if(d.estado.includes('OBSERVADA')){ res.className='resultado observada'; res.innerHTML='⚠️ Tu solicitud está OBSERVADA. Revisa los documentos.'; }
                else { res.className='resultado pendiente'; res.innerHTML='⏳ PENDIENTE. En revisión por Secretaría.'; }
                res.style.display='block';
            });
        }
        function abrirPublico() { document.getElementById('modalPublico').classList.add('mostrar'); cargarPublico(); }
        function cerrarPublico() { document.getElementById('modalPublico').classList.remove('mostrar'); }
        function cargarPublico() {
            fetch('/lista_publica').then(r=>r.json()).then(d=>{
                let html='<h4 style=\"color:#239B56;\">✅ APROBADAS</h4>';
                html += d.aprobadas.length?d.aprobadas.map(n=>`<p class=\"ok-item\">✅ ${n}</p>`).join(''):'<p style=\"color:#666;\">Aún no hay solicitudes aprobadas.</p>';
                html += '<h4 style=\"color:#cb4335; margin-top:15px;\">⚠️ OBSERVADAS</h4>';
                html += d.observadas.length?d.observadas.map(n=>`<p class=\"obs-item\">⚠️ ${n}</p>`).join(''):'<p style=\"color:#666;\">Aún no hay solicitudes observadas.</p>';
                document.getElementById('contenidoPublico').innerHTML=html;
            });
        }
    </script>
</body>
</html>
"""

# ======================
# 📝 FORMULARIO
# ======================
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
        .doc-nombre { flex:1; min-width:260px; font-weight:500; }
        .doc-estado { padding:6px 10px; border-radius:5px; font-size:14px; }
        .pendiente { background:#ffeaa7; color:#856404; }
        .listo { background:#d4edda; color:#155724; }
        .boton-enviar { width:100%; padding:14px; background:#239B56; color:white; border:none; border-radius:10px; font-size:18px; font-weight:bold; margin-top:15px; cursor:pointer; }
        .boton-volver { display:inline-block; padding:10px 20px; background:#95a5a6; color:white; text-decoration:none; border-radius:8px; margin-bottom:15px; }
        .mensaje { margin-top:15px; padding:15px; border-radius:8px; display:none; }
        .exito { background:#d4edda; color:#155724; display:block !important; }
        .aviso-doc { font-size:14px; color:#555; margin-bottom:8px; background:#fff3cd; padding:8px; border-radius:5px; }
    </style>
</head>
<body>
    <div class="caja">
        <a href="/" class="boton-volver">← Volver al Inicio</a>
        <h1>✍️ Solicitud de Inscripción</h1>
        <div class="seccion">
            <h2>👤 Datos del Estudiante</h2>
            <label>Nombres y Apellidos Completos</label><input type="text" id="est_nombre" required>
            <label>Fecha de Nacimiento</label><input type="text" id="est_fnac" placeholder="DD/MM/AAAA">
            <label>Dirección Domiciliaria</label><input type="text" id="est_dir">
            <label>Colegio de Procedencia</label><input type="text" id="est_proc">
        </div>
        <div class="seccion">
            <h2>👨‍👩‍👦 Datos del Tutor / Responsable</h2>
            <label>Nombres y Apellidos del Tutor</label><input type="text" id="tut_nombre" required>
            <label>Número de Carnet de Identidad</label><input type="text" id="tut_ci">
            <label>Teléfono / Celular</label><input type="text" id="tut_tel">
            <label>Correo Electrónico</label><input type="email" id="tut_correo">
        </div>
        <div class="seccion">
            <h2>📷 Documentos</h2>
            <p class="aviso-doc">💡 Toma la foto clara y bien iluminada. El sistema la mejora automáticamente.</p>
            <div id="lista-docs"></div>
        </div>
        <button class="boton-enviar" onclick="enviarFormulario()">📤 Enviar Solicitud de Inscripción</button>
        <div id="msg" class="mensaje"></div>
    </div>
    <script>
        const docs = [
            "📕 Libreta de Calificaciones",
            "📄 Certificado de Nacimiento",
            "🪪 Carnet Estudiante — Delantera",
            "🪪 Carnet Estudiante — Trasera",
            "🪪 Carnet Tutor — Delantera",
            "🪪 Carnet Tutor — Trasera",
            "💡 Factura de Luz",
            "💧 Factura de Agua",
            "🗺️ Croquis de Ubicación"
        ];
        let archivos = {};
        const contenedor = document.getElementById('lista-docs');
        docs.forEach((nombre,i)=>{
            const fila=document.createElement('div'); fila.className='doc-row';
            fila.innerHTML=`<span class="doc-nombre">${nombre}</span><input type="file" id="doc${i}" accept="image/*" onchange="subirArchivo(${i})"><span id="estado${i}" class="doc-estado pendiente">Pendiente</span>`;
            contenedor.appendChild(fila);
        });
        async function subirArchivo(indice){
            const input=document.getElementById(`doc${indice}`);
            const estado=document.getElementById(`estado${indice}`);
            if(!input.files.length) return;
            estado.textContent="⏳ Convirtiendo..."; estado.className="doc-estado pendiente";
            const fd=new FormData(); fd.append('archivo',input.files[0]); fd.append('indice',indice);
            try{
                const r=await fetch('/subir_documento',{method:'POST',body:fd});
                const d=await r.json();
                estado.textContent=d.ok?"✅ Convertido":"⚠️ Cargado"; estado.className="doc-estado listo";
                archivos[indice]=d.ruta;
            }catch{ estado.textContent="❌ Error"; }
        }
        async function enviarFormulario(){
            const msg=document.getElementById('msg'); msg.style.display='none';
            const datos={
                est_nombre:document.getElementById('est_nombre').value.trim(),
                est_fnac:document.getElementById('est_fnac').value.trim(),
                est_dir:document.getElementById('est_dir').value.trim(),
                est_proc:document.getElementById('est_proc').value.trim(),
                tut_nombre:document.getElementById('tut_nombre').value.trim(),
                tut_ci:document.getElementById('tut_ci').value.trim(),
                tut_tel:document.getElementById('tut_tel').value.trim(),
                tut_correo:document.getElementById('tut_correo').value.trim(),
                archivos:archivos
            };
            if(!datos.est_nombre||!datos.tut_nombre) return alert('Completa los datos obligatorios.');
            if(Object.keys(archivos).length<docs.length) return alert(`Debes cargar los ${docs.length} documentos.`);
            try{
                const r=await fetch('/guardar_solicitud',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datos)});
                const d=await r.json();
                if(d.ok){
                    msg.className="mensaje exito";
                    msg.innerHTML=`<strong>✅ ¡SOLICITUD REGISTRADA!</strong><br><br>📌 N° Registro:<br><h2 style=\"font-size:22px\">${d.numero}</h2>Guárdalo para seguimiento.<br><br>Serás redirigido en 15 segundos.`;
                    msg.style.display='block';
                    setTimeout(()=>window.location.href='/',15000);
                }
            }catch{ alert('Error al enviar. Inténtalo de nuevo.'); }
        }
    </script>
</body>
</html>
"""

# ======================
# 🔐 PANEL DE SECRETARÍA — CON BOTÓN DE DESCARGA PDF
# ======================
SECRETARIA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Secretaría</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', Arial, sans-serif; }
        body { background:#f4f6f7; padding:20px; }
        .caja { max-width:1400px; margin:0 auto; background:white; border-radius:16px; padding:30px; box-shadow:0 4px 20px rgba(0,0,0,0.1); }
        h1 { text-align:center; color:#283747; margin-bottom:20px; }
        table { width:100%; border-collapse:collapse; margin-top:15px; }
        th, td { padding:10px; text-align:left; border-bottom:1px solid #ddd; font-size:14px; }
        th { background:#283747; color:white; }
        .fila:hover { background:#f2f2f2; }
        .estado-pendiente { color:#d68910; font-weight:bold; }
        .estado-aprobada { color:#239B56; font-weight:bold; }
        .estado-observada { color:#cb4335; font-weight:bold; }
        .btn { padding:6px 10px; border:none; border-radius:6px; cursor:pointer; font-weight:bold; margin:2px; font-size:13px; }
        .btn-ver { background:#3498db; color:white; }
        .btn-aprobar { background:#239B56; color:white; }
        .btn-observar { background:#f39c12; color:white; }
        .btn-pdf { background:#9B59B6; color:white; }
        .boton-volver { display:inline-block; padding:10px 20px; background:#95a5a6; color:white; text-decoration:none; border-radius:8px; margin-bottom:15px; }
        .aviso { background:#eafaf1; color:#1e8449; padding:12px; border-radius:8px; margin-bottom:15px; }
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); align-items:flex-start; justify-content:center; z-index:200; padding:20px; overflow-y:auto; }
        .modal.mostrar { display:flex; }
        .modal-contenido { background:white; padding:30px; border-radius:14px; width:98%; max-width:1200px; }
        .cerrar-modal { float:right; font-size:28px; cursor:pointer; color:#888; margin-top:-10px; }
        .cerrar-modal:hover { color:red; }
        .bloque-datos { background:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:20px; }
        .bloque-datos p { margin:5px 0; font-size:15px; }
        .bloque-datos strong { color:#2C3E50; }
        .titulo-fotos { font-size:18px; font-weight:bold; color:#2C3E50; margin:20px 0 10px; padding-bottom:8px; border-bottom:2px solid #3498db; }
        .galeria { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:20px; }
        .tarjeta-foto { border:2px solid #e0e0e0; border-radius:12px; padding:12px; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,0.08); }
        .tarjeta-foto h5 { font-size:14px; color:#2C3E50; margin-bottom:10px; text-align:center; }
        .tarjeta-foto img { width:100%; height:auto; border-radius:8px; cursor:pointer; }
        .imagen-grande { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.92); z-index:300; align-items:center; justify-content:center; }
        .imagen-grande.mostrar { display:flex; }
        .imagen-grande img { max-width:90%; max-height:90%; border-radius:8px; }
        .cerrar-grande { position:absolute; top:20px; right:30px; color:white; font-size:35px; cursor:pointer; }
        .acciones { margin-top:20px; padding-top:15px; border-top:1px solid #ddd; text-align:center; }
        .acciones .btn { padding:10px 20px; font-size:15px; margin:5px; }
        .sin-foto { padding:30px; text-align:center; color:#888; background:#f9f9f9; border-radius:8px; border:2px dashed #ccc; }
    </style>
</head>
<body>
    <div class="caja">
        <a href="/" class="boton-volver">← Volver al Inicio</a>
        <h1>📂 SOLICITUDES RECIBIDAS</h1>
        <div class="aviso">🔄 Pulsa 👁️ Ver para consultar datos y fotos. 📄 Descargar genera un PDF con TODA la solicitud incluyendo las fotos.</div>
        <table>
            <thead><tr><th>Fecha</th><th>Estudiante</th><th>Tutor / CI</th><th>Estado</th><th>Acciones</th></tr></thead>
            <tbody id="tabla"></tbody>
        </table>
    </div>

    <div id="modalVer" class="modal">
        <div class="modal-contenido">
            <span class="cerrar-modal" onclick="cerrarModalVer()">&times;</span>
            <h2>👁️ DETALLE COMPLETO DE LA SOLICITUD</h2>
            <div id="contenidoDetalle"></div>
            <div class="acciones">
                <button class="btn btn-pdf" id="btnDescargarPDF">📄 Descargar Formulario Completo (PDF)</button>
                <button class="btn btn-aprobar" id="btnAprobarModal">✅ Aprobar Solicitud</button>
                <button class="btn btn-observar" id="btnObservarModal">⚠️ Marcar como Observada</button>
                <button class="btn" style="background:#ccc; color:#333;" onclick="cerrarModalVer()">Cerrar</button>
            </div>
        </div>
    </div>

    <div id="visorGrande" class="imagen-grande" onclick="cerrarImagenGrande()">
        <span class="cerrar-grande">&times;</span>
        <img id="fotoAmpliada" src="">
    </div>

    <script>
        let indiceActual = null;
        const nombresDocs = [
            "📕 Libreta de Calificaciones",
            "📄 Certificado de Nacimiento",
            "🪪 Carnet Estudiante — Delantera",
            "🪪 Carnet Estudiante — Trasera",
            "🪪 Carnet Tutor — Delantera",
            "🪪 Carnet Tutor — Trasera",
            "💡 Factura de Luz",
            "💧 Factura de Agua",
            "🗺️ Croquis de Ubicación"
        ];

        async function cargarLista() {
            const r=await fetch('/lista_solicitudes');
            const d=await r.json();
            const tb=document.getElementById('tabla'); tb.innerHTML='';
            if(!d.lista.length){ tb.innerHTML='<tr><td colspan="5" style="text-align:center; padding:30px; color:#666;">📭 Aún no hay solicitudes.</td></tr>'; return; }
            d.lista.forEach((sol,i)=>{
                let clase='estado-pendiente';
                if(sol.ESTADO&&sol.ESTADO.includes('APROBADA')) clase='estado-aprobada';
                else if(sol.ESTADO&&sol.ESTADO.includes('OBSERVADA')) clase='estado-observada';
                const est=sol.ESTUDIANTE||'---', tut=sol.TUTOR||'---', ci=sol['CI TUTOR']||'---', estdo=sol.ESTADO||'PENDIENTE ⏳';
                tb.innerHTML += `<tr class="fila"><td>${sol.FECHA||'---'}</td><td>${est}</td><td>${tut}<br><small>CI: ${ci}</small></td><td class="${clase}">${estdo}</td><td><button class="btn btn-ver" onclick="verDetalle(${i})">👁️ Ver</button> <button class="btn btn-pdf" onclick="descargarPDF(${i})">📄 PDF</button> <button class="btn btn-aprobar" onclick="cambiarEstado(${i},'APROBADA ✅')">Aprobar</button> <button class="btn btn-observar" onclick="cambiarEstado(${i},'OBSERVADA ⚠️')">Observar</button></td></tr>`;
            });
        }

        async function verDetalle(indice){
            indiceActual=indice;
            const r=await fetch('/ver_solicitud?indice='+indice);
            const d=await r.json(); if(!d.ok) return;
            const s=d.solicitud;
            let html = `
                <div class="bloque-datos">
                    <p><strong>📅 Fecha:</strong> ${s.FECHA||'---'}</p>
                    <p><strong>📌 N° Registro:</strong> ${s['NÚMERO REGISTRO']||'---'}</p>
                    <p><strong>👤 Estudiante:</strong> ${s.ESTUDIANTE||'---'}</p>
                    <p><strong>🎂 F. Nacimiento:</strong> ${s['F.NACIMIENTO']||'---'}</p>
                    <p><strong>🏠 Dirección:</strong> ${s.DIRECCIÓN||'---'}</p>
                    <p><strong>🏫 Procedencia:</strong> ${s.PROCEDENCIA||'---'}</p>
                    <hr style="margin:8px 0; border:none; border-top:1px solid #ddd;">
                    <p><strong>👨‍👩‍👦 Tutor:</strong> ${s.TUTOR||'---'}</p>
                    <p><strong>🪪 CI Tutor:</strong> ${s['CI TUTOR']||'---'}</p>
                    <p><strong>📞 Teléfono:</strong> ${s.TELÉFONO||'---'}</p>
                    <p><strong>📧 Correo:</strong> ${s.CORREO||'---'}</p>
                    <p style="font-size:16px; font-weight:bold; margin-top:10px; color:#d68910;">📌 Estado actual: ${s.ESTADO||'PENDIENTE ⏳'}</p>
                </div>
                <h3 class="titulo-fotos">📷 DOCUMENTOS — Haz clic para ampliar</h3>
                <div class="galeria">
            `;
            const archivos=s.documentos_parseados||{};
            if(Object.keys(archivos).length===0) html += `<div class="sin-foto">⚠️ No se encontraron documentos</div>`;
            else for(const clave in archivos){
                const ruta=archivos[clave], nom=nombresDocs[clave]||`Documento ${clave}`;
                html += `<div class="tarjeta-foto"><h5>${nom}</h5><img src="/ver_foto?archivo=${encodeURIComponent(ruta)}" alt="${nom}" loading="lazy" onclick="mostrarGrande('/ver_foto?archivo=${encodeURIComponent(ruta)}')"></div>`;
            }
            html += `</div>`;
            document.getElementById('contenidoDetalle').innerHTML=html;
            document.getElementById('modalVer').classList.add('mostrar');
            document.getElementById('btnAprobarModal').onclick=()=>{cambiarEstado(indice,'APROBADA ✅');cerrarModalVer();};
            document.getElementById('btnObservarModal').onclick=()=>{cambiarEstado(indice,'OBSERVADA ⚠️');cerrarModalVer();};
            document.getElementById('btnDescargarPDF').onclick=()=>descargarPDF(indice);
        }

        function descargarPDF(indice){
            window.open('/descargar_pdf?indice='+indice,'_blank');
        }

        function mostrarGrande(url){ document.getElementById('fotoAmpliada').src=url; document.getElementById('visorGrande').classList.add('mostrar'); }
        function cerrarImagenGrande(){ document.getElementById('visorGrande').classList.remove('mostrar'); }
        function cerrarModalVer(){ document.getElementById('modalVer').classList.remove('mostrar'); indiceActual=null; }
        async function cambiarEstado(i,estado){
            await fetch('/cambiar_estado',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indice:i,estado:estado})});
            cargarLista();
        }
        cargarLista();
        setInterval(cargarLista,30000);
    </script>
</body>
</html>
"""

# ======================
# 🛣️ RUTAS DEL SERVIDOR
# ======================

@app.route('/ver_foto')
def ver_foto():
    archivo = request.args.get('archivo', '')
    nombre_archivo = os.path.basename(archivo)
    return send_from_directory(CARPETA_DOCUMENTOS, nombre_archivo)

@app.route('/descargar_pdf')
def descargar_pdf():
    idx = int(request.args.get('indice', 0))
    lista = leer_solicitudes()
    if not (0 <= idx < len(lista)):
        return "Solicitud no encontrada", 404
    sol = lista[idx]
    pdf = generar_pdf_solicitud(sol)
    nombre_reg = sol.get('NÚMERO REGISTRO', 'solicitud')
    resp = make_response(pdf.read())
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="Solicitud_{nombre_reg}.pdf"'
    return resp

@app.route('/')
def inicio():
    return render_template_string(PAGINA_INICIO)

@app.route('/verificar_clave', methods=['POST'])
def verificar_clave():
    datos = request.get_json()
    return jsonify({"ok": datos.get('clave') == CONTRASEÑA_SECRETARIA})

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
    ruta_temporal = os.path.join(CARPETA_DOCUMENTOS, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{indice}.jpg")
    archivo.save(ruta_temporal)
    ruta_destino = os.path.join(CARPETA_DOCUMENTOS, f"doc_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{indice}.jpg")
    ok = convertir_a_documento_digital(ruta_temporal, ruta_destino)
    try: os.remove(ruta_temporal)
    except: pass
    return jsonify({"ok": ok, "ruta": ruta_destino})

@app.route('/guardar_solicitud', methods=['POST'])
def guardar_solicitud():
    d = request.get_json()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    numero = datetime.now().strftime("%Y%m%d%H%M%S%f")[:18]
    registro = f"""
============================================
FECHA: {fecha}
ESTUDIANTE: {d['est_nombre']}
F.NACIMIENTO: {d
