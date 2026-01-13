import streamlit as st
import requests
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from io import BytesIO
from streamlit_drawable_canvas import st_canvas
from PIL import Image

# --- Configuración de página
st.set_page_config(page_title="Formulario S-205b", layout="centered")

# --- Estilos CSS personalizados ---
custom_css = """
<style>
    body {
        font-family: 'Segoe UI', sans-serif;
    }
    .container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .section-title {
        font-size: 30px;
        font-weight: bold;
        color: #1f3a93;
        margin-top: 20px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .section-title::before {
        content: "🔹";
        margin-right: 10px;
    }
    .resumen-box {
        background-color: #e8f5e9;
        padding: 15px;
        border-left: 5px solid #4caf50;
        border-radius: 10px;
        margin-top: 10px;
        margin-bottom: 20px;
        font-size: 24px;
    }
    hr {
        border: 1px solid #ddd;
        margin-top: 20px;
        margin-bottom: 20px;
    }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# --- Título principal ---
st.title("📄 Formulario S-205b")
st.subheader("Solicitud para el Servicio de Precursor Auxiliar")

# --- Meses en español ---
meses_espanol = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# --- Función para dibujar checkbox en PDF ---
def dibujar_checkbox(can, x, y, marcado=False, size=10):
    """Dibuja un checkbox cuadrado con X si está marcado"""
    can.rect(x, y, size, size, stroke=1, fill=0)
    if marcado:
        can.setFont("Helvetica-Bold", size - 1)
        can.drawString(x + 2, y + 1, "X")

# --- Función para dividir texto largo ---
def dividir_texto(texto, max_length=80):
    """Divide texto largo en múltiples líneas"""
    palabras = texto.split()
    lineas = []
    linea_actual = ""
    
    for palabra in palabras:
        if len(linea_actual + palabra) <= max_length:
            linea_actual += palabra + " "
        else:
            if linea_actual:
                lineas.append(linea_actual.strip())
            linea_actual = palabra + " "
    
    if linea_actual:
        lineas.append(linea_actual.strip())
    
    return lineas


#FUNCION PARA ENVIAR NOTIFICACIONES A TELEGRAM
# FUNCION PARA ENVIAR NOTIFICACIONES Y EL PDF A TELEGRAM
def enviar_notificacion_telegram(nombre, meses_lista, es_continuo, pdf_file, nombre_archivo): # <---- AJUSTE (Añadidos pdf_file y nombre_archivo)
    try:
        # 1. Extraer credenciales de forma segura
        token = str(st.secrets["TELEGRAM_TOKEN"]).strip()
        chat_id = str(st.secrets["TELEGRAM_CHAT_ID"]).strip()
        
        # 2. Preparar el texto de meses y hashtags
        texto_meses = "SERVICIO CONTINUO" if es_continuo else " Y ".join(meses_lista).upper()
        
        if es_continuo:
            hashtags = "#PA_CONTINUO"
        else:
            hashtags = " ".join([f"#PA_{mes.upper()}" for mes in meses_lista])
        
        # 3. Construir mensaje en HTML
        cuerpo_mensaje = (
            "🎉 <b>¡Tenemos nuevos Precursores Auxiliares!</b> 🎉\n\n"
            f"👤 <b>{nombre}</b>\n"
            f"🗓️ <b>{texto_meses}</b>\n\n"
            f"{hashtags}"
        )
        
        # --- ENVÍO DEL MENSAJE DE TEXTO ---
        url_msg = f"https://api.telegram.org/bot{token}/sendMessage"
        payload_msg = {
            "chat_id": chat_id,
            "text": cuerpo_mensaje,
            "parse_mode": "HTML"
        }
        response_msg = requests.post(url_msg, json=payload_msg, timeout=10)
        
        # --- ENVÍO DEL ARCHIVO PDF (NUEVA SECCIÓN) --- # <---- NUEVO
        url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
        
        # Reiniciar el puntero del PDF para que Telegram lo lea desde el principio
        pdf_file.seek(0) # <---- NUEVO
        
        # Preparamos el archivo para el envío
        files = {
            'document': (nombre_archivo, pdf_file, 'application/pdf')
        } # <---- NUEVO
        
        # Enviamos el documento
        response_doc = requests.post(url_doc, data={'chat_id': chat_id}, files=files, timeout=15) # <---- NUEVO
        
        # --- LÓGICA DE AVISO ACTUALIZADA ---
        if response_msg.status_code == 200 and response_doc.status_code == 200: # <---- AJUSTE (Verifica ambos envíos)
            st.success("✅ Notificación y Formulario generado exitosamente ✅.")
        else:
            st.error(f"Error parcial - Msg: {response_msg.status_code}, Doc: {response_doc.status_code}")
            
    except Exception as e:
        st.error(f"Error en notificación completa: {e}")




# --- Funciones auxiliares para firmas ---
def procesar_firma(firma_data):
    """Procesa la firma del canvas y la convierte en imagen"""
    try:
        if firma_data is not None and isinstance(firma_data, object):
            # Convertir el array numpy a imagen PIL
            firma_img = Image.fromarray(firma_data.astype('uint8'), 'RGBA')
            img_stream = BytesIO()
            firma_img.save(img_stream, format="PNG")
            img_stream.seek(0)
            return img_stream
        return None
    except Exception as e:
        print(f"Error procesando firma: {e}")
        return None

# --- Función para crear PDF desde cero ---
def crear_pdf_s205b(meses_seleccionados, continuo, fecha_solicitud, nombre_solicitante, 
                    iniciales_1, iniciales_2, iniciales_3, firma_data,titulo_metadatos):
    """Crea el PDF S-205b completo desde cero"""
    buffer = BytesIO()
    can = canvas.Canvas(buffer, pagesize=landscape(letter))
    # --- AJUSTE DE METADATOS PARA MÓVILES ---
    can.setTitle(titulo_metadatos) # <--- NUEVA INSTRUCCIÓN
    # ----------------------------------------
                        
    # Dimensiones de página
    width, height = landscape(letter)
    
    # --- ENCABEZADO ---
    y = height - 50
    can.setFont("Helvetica-Bold", 14)
    can.drawCentredString(width / 2, y, "SOLICITUD PARA EL SERVICIO DE PRECURSOR AUXILIAR")
    
    # --- PÁRRAFO INTRODUCTORIO ---
    y -= 35
    can.setFont("Helvetica", 10)
    texto_intro = ("Debido a mi amor a Jehová y mi deseo de ayudar al prójimo a aprender acerca de él y sus amorosos propósitos, "
                   "quisiera aumentar mi participación en el servicio del campo siendo precursor auxiliar durante el período indicado abajo:")
    
    lineas = dividir_texto(texto_intro, max_length=95)
    for linea in lineas:
        can.drawString(72, y, linea)
        y -= 14
    
    # --- MESES DE SERVICIO ---
    y -= 10
    can.setFont("Helvetica-Bold", 10)
    can.drawString(72, y, "El (los) mes(es) de:")
    
    # Mostrar meses seleccionados
    if meses_seleccionados:
        # AJUSTE AQUÍ: Convertimos cada mes a mayúsculas antes de unirlos
        meses_texto = ", ".join([m.upper() for m in meses_seleccionados]) # <---- AJUSTE
        can.setFont("Helvetica", 10)
        
        # Dibujar línea para los meses
        lineas_meses = dividir_texto(meses_texto, max_length=75)
        x_meses = 200
        for i, linea_mes in enumerate(lineas_meses):
            can.drawString(x_meses, y - (i * 12), linea_mes)
        
        y -= (len(lineas_meses) * 12) + 5
    else:
        y -= 12
    
    # Línea decorativa
    can.line(200, y + 5, width - 72, y + 5)
    y -= 15
    
    # --- CHECKBOX SERVICIO CONTINUO ---
    dibujar_checkbox(can, 72, y - 2, marcado=continuo, size=10)
    can.setFont("Helvetica", 9)
    can.drawString(90, y, "Marque la casilla si desea ser precursor auxiliar de continuo hasta nuevo aviso.")
    
    # --- DECLARACIÓN ---
    y -= 30
    can.setFont("Helvetica", 10)
    texto_declaracion = ("Gozo de una buena reputación moral y tengo buenos hábitos. He hecho planes para satisfacer el requisito de horas. "
                        "(Vea Nuestro Ministerio del Reino de junio de 2013, página 2).")
    
    lineas_decl = dividir_texto(texto_declaracion, max_length=95)
    for linea in lineas_decl:
        can.drawString(72, y, linea)
        y -= 14
    
    # --- DISEÑO DE DOS COLUMNAS: FECHA (izquierda) y FIRMA (derecha) ---
    y -= 58
    
    # Definir ancho de las líneas (mismo para fecha y firma)
    ancho_linea = 250
    
    # COLUMNA IZQUIERDA: Fecha
    x_left = 72
    can.setFont("Helvetica-Bold", 10)
    # "Fecha:" en negrita ANTES de la línea, a la misma altura
    can.drawString(x_left, y, "Fecha:")
    # La fecha y la línea
    x_fecha_inicio = x_left + 45  # Después de "Fecha:"
    can.setFont("Helvetica", 10)
    can.drawString(x_fecha_inicio, y, fecha_solicitud)
    can.line(x_fecha_inicio, y - 2, x_fecha_inicio + ancho_linea, y - 2)
    
    # COLUMNA DERECHA: Firma (en la MISMA línea que fecha)
    x_right = x_fecha_inicio + ancho_linea + 50
    
    # Línea de firma (MISMA altura que línea de fecha)
    can.line(x_right, y - 2, x_right + ancho_linea, y - 2)
    
    # Insertar firma si existe - AJUSTADA para aparecer ENCIMA de la línea
    if firma_data is not None:
        try:
            firma_stream = procesar_firma(firma_data)
            if firma_stream is not None:
                firma_width = 200
                firma_height = 50
                # Dibujar firma ENCIMA de la línea (y - 2 es donde está la línea)
                # La firma debe empezar en y (la línea) y extenderse hacia arriba
                can.drawImage(ImageReader(firma_stream), x_right + 25, y, 
                             width=firma_width, height=firma_height, preserveAspectRatio=True)
        except Exception as e:
            print(f"Error al insertar firma: {e}")
    
    # Texto entre paréntesis bajo la línea de firma
    can.setFont("Helvetica-Oblique", 8)
    can.drawString(x_right + 50, y - 15, "(Firma del solicitante)")
    
    # --- NOMBRE EN LETRA DE MOLDE (debajo de la firma, MISMO ANCHO) ---
    y_nombre = y - 58
    can.setFont("Helvetica-Bold", 16)
    # Centrar el nombre dentro del ancho de la línea de firma
    text_width = can.stringWidth(nombre_solicitante, "Helvetica-Bold", 16)
    x_nombre_centrado = x_right + (ancho_linea - text_width) / 2
    can.drawString(x_nombre_centrado, y_nombre+3, nombre_solicitante)
    can.line(x_right, y_nombre - 2, x_right + ancho_linea, y_nombre - 2)
    
    # Texto entre paréntesis bajo el nombre
    can.setFont("Helvetica-Oblique", 8)
    texto_parentesis = "(Nombre en letra de molde)"
    text_width_p = can.stringWidth(texto_parentesis, "Helvetica-Oblique", 8)
    x_parentesis_centrado = x_right + (ancho_linea - text_width_p) / 2
    can.drawString(x_parentesis_centrado, y_nombre - 15, texto_parentesis)
    
    # --- NOTA Y APROBACIÓN EN DOS COLUMNAS ---
    y -= 102
    
    # COLUMNA IZQUIERDA: NOTA (letra más pequeña y más cerca)
    can.setFont("Helvetica-Bold", 8)
    can.drawString(128, y, "NOTA:")
    can.setFont("Helvetica", 7)
    nota_texto = ("Después de llenar esta solicitud, entréguela al coordinador del cuerpo de ancianos. Si es posible, "
                 "hágalo por lo menos una semana antes de la fecha en que desea comenzar el servicio de precursor auxiliar. "
                 "No debe enviarse esta solicitud a la sucursal, sino más bien guardarse en los archivos de la congregación.")
    
    lineas_nota = dividir_texto(nota_texto, max_length=55)
    y_nota = y - 2
    for linea in lineas_nota:
        can.drawString(159, y_nota, linea)
        y_nota -= 9
    
    # SECCIÓN DE PREGUNTAS DEL COMITÉ (debajo de la nota, letra más pequeña)
    y_comite = y_nota - 5
    can.setFont("Helvetica-Bold", 8)
    can.drawString(128, y_comite, "Para el Comité de Servicio")
    can.drawString(128, y_comite - 10, "de la Congregación:")
    
    # Preguntas con letra más pequeña
    y_comite -= 20
    can.setFont("Helvetica", 7)
    can.drawString(128, y_comite, "1. ¿Es el solicitante un buen ejemplo")
    y_comite -= 8
    can.drawString(136, y_comite, "del vivir cristiano?")
    
    y_comite -= 11
    can.drawString(128, y_comite, "2. Quienes hayan sido censurados o")
    y_comite -= 8
    can.drawString(136, y_comite, "readmitidos durante el pasado año o")
    y_comite -= 8
    can.drawString(128, y_comite, "todavía estén bajo restricciones no")
    y_comite -= 8
    can.drawString(136, y_comite, "satisfacen los requisitos.")
    
    y_comite -= 11
    can.drawString(128, y_comite, "3. ¿Han consultado con su")
    y_comite -= 8
    can.drawString(136, y_comite, "superintendente de grupo?")
    
    # COLUMNA DERECHA: APROBACIÓN (a la misma altura que NOTA)
    x_aprobacion = 450
    can.setFont("Helvetica-Bold", 9)
    can.drawString(x_aprobacion, y, "Aprobado por los miembros")
    can.drawString(x_aprobacion, y - 12, "del comité de servicio:")
    can.setFont("Helvetica-Oblique", 8)
    can.drawString(x_aprobacion, y - 24, "(Basta con las iniciales)")
    
    # Tres líneas para las iniciales (centradas)
    y_iniciales = y - 76
    ancho_linea_iniciales = 130
    x_linea_inicio = x_aprobacion
    x_linea_fin = x_aprobacion + ancho_linea_iniciales

    if iniciales_1:
        can.setFont("Helvetica", 14)
        text_width = can.stringWidth(iniciales_1, "Helvetica", 10)
        x_centrado = x_linea_inicio + (ancho_linea_iniciales - text_width) / 2
        can.drawString(x_centrado, y_iniciales, iniciales_1)
    can.line(x_linea_inicio, y_iniciales - 2, x_linea_fin, y_iniciales - 2)

    y_iniciales -= 30
    if iniciales_2:
        can.setFont("Helvetica", 14)
        text_width = can.stringWidth(iniciales_2, "Helvetica", 10)
        x_centrado = x_linea_inicio + (ancho_linea_iniciales - text_width) / 2
        can.drawString(x_centrado, y_iniciales, iniciales_2)
    can.line(x_linea_inicio, y_iniciales - 2, x_linea_fin, y_iniciales - 2)

    y_iniciales -= 30
    if iniciales_3:
        can.setFont("Helvetica", 14)
        text_width = can.stringWidth(iniciales_3, "Helvetica", 10)
        x_centrado = x_linea_inicio + (ancho_linea_iniciales - text_width) / 2
        can.drawString(x_centrado, y_iniciales, iniciales_3)
    can.line(x_linea_inicio, y_iniciales - 2, x_linea_fin, y_iniciales - 2)
    
    # --- PIE DE PÁGINA ---
    can.setFont("Helvetica-Bold", 8)
    can.drawString(72, 30, "S-205b-S  4/15")
    
    can.save()
    buffer.seek(0)
    return buffer

# --- Formulario principal ---
with st.form("formulario_s205b"):
    st.markdown('<div class="container">', unsafe_allow_html=True)
    
    # Sección 1: Período de servicio
    st.markdown('<div class="section-title">📅 Período de Servicio</div>', unsafe_allow_html=True)
    
    st.write("**Selecciona el (los) mes(es) de servicio:**")
    
    # Crear tabla 4x3 para los meses
    cols = st.columns(4)
    meses_seleccionados = []
    
    for i, mes in enumerate(meses_espanol):
        with cols[i % 4]:
            if st.checkbox(mes, key=f"mes_{i}"):
                meses_seleccionados.append(mes)
    
    continuo = st.checkbox(
        "✓ Deseo ser precursor auxiliar de continuo hasta nuevo aviso",
        help="Marca esta casilla si deseas servir continuamente (ignora la selección de meses específicos)"
    )
    
    if continuo:
        st.info("ℹ️ Has seleccionado servicio continuo. No es necesario seleccionar meses específicos.")
        meses_seleccionados = ["CONTINUO"]
    
    st.markdown('<hr>', unsafe_allow_html=True)
    
    # Sección 2: Datos del solicitante (AHORA PRIMERO)
    st.markdown('<div class="section-title">👤 Datos del Solicitante</div>', unsafe_allow_html=True)
    
    nombre_solicitante = st.text_input(
        "Nombre completo del solicitante:",
        placeholder="Escribe el nombre completo",
        help="El nombre del hermano o hermana que solicita"
    ).upper()
    
    fecha_seleccionada = st.date_input(
        "Fecha de la solicitud:",
        value=date.today(),
        min_value=date(2020, 1, 1),
        max_value=date(2030, 12, 31),
        format="DD/MM/YYYY",
        help="Selecciona la fecha en que se presenta esta solicitud"
    )
    
    # Formatear fecha en español (sin "de")
    meses_esp_lower = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    fecha_str = f"{fecha_seleccionada.day} de {meses_esp_lower[fecha_seleccionada.month - 1]} de {fecha_seleccionada.year}"
    st.success(f"✅ **Fecha seleccionada:** {fecha_str}")
    
    st.markdown('<hr>', unsafe_allow_html=True)
    
    # Sección: Firma del solicitante (AHORA DESPUÉS)
    st.markdown('<div class="section-title">✍️ Firma del Solicitante</div>', unsafe_allow_html=True)
    
    st.info("✏️ Dibuja la firma con el dedo o mouse en el recuadro blanco.")
    
    firma_canvas = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=2,
        stroke_color="black",
        background_color="white",
        height=200,
        width=600,
        drawing_mode="freedraw",
        key="firma_solicitante",
    )
    
    st.markdown('<hr>', unsafe_allow_html=True)
    
    # Sección 3: Aprobación del comité
    st.markdown('<div class="section-title">✔️ Aprobación del Comité de Servicio</div>', unsafe_allow_html=True)
    
    st.info("ℹ️ Ingresa las iniciales de los miembros del comité que aprueban la solicitud.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        iniciales_1 = st.text_input(
            "Iniciales miembro 1:",
            max_chars=10,
            placeholder="Ej: JMP"
        ).upper()
    
    with col2:
        iniciales_2 = st.text_input(
            "Iniciales miembro 2:",
            max_chars=10,
            placeholder="Ej: ASR"
        ).upper()
    
    with col3:
        iniciales_3 = st.text_input(
            "Iniciales miembro 3:",
            max_chars=10,
            placeholder="Ej: LFG"
        ).upper()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Botón de envío
    enviado = st.form_submit_button(
        "📤 Generar PDF",
        help="Genera el formulario S-205b completo"
    )

# --- Procesamiento al enviar ---
if enviado:
    # Validaciones
    if not meses_seleccionados:
        st.error("❌ Debes seleccionar al menos un mes o marcar 'servicio continuo'.")
    elif not nombre_solicitante:
        st.error("❌ Debes ingresar el nombre completo del solicitante.")
    elif firma_canvas.image_data is None:
        st.error("❌ Debes dibujar la firma del solicitante en el recuadro.")
    else:
        try:
            # --- 1. MOVER EL CÁLCULO DEL NOMBRE HACIA ARRIBA --- # <--- AJUSTE
            if continuo:
                mes_archivo = "CONTINUO"
            elif len(meses_seleccionados) == 1:
                mes_archivo = meses_seleccionados[0].upper()
            else:
                mes_archivo = f"{meses_seleccionados[0].upper()}-{meses_seleccionados[-1].upper()}"
            
            nombre_archivo = f"{mes_archivo}-{nombre_solicitante.replace(' ', '_').upper()}.pdf"

            # --- 2. CREAR EL PDF PASANDO EL NOMBRE_ARCHIVO --- # <--- AJUSTE
            pdf_buffer = crear_pdf_s205b(
                meses_seleccionados,
                continuo,
                fecha_str,
                nombre_solicitante,
                iniciales_1,
                iniciales_2,
                iniciales_3,
                firma_canvas.image_data,
                nombre_archivo # <--- NUEVO: Se añade aquí como último dato
            )
            
            # Mostrar resumen
            st.markdown('<div class="resumen-box">', unsafe_allow_html=True)
            st.subheader("💡 Resumen de la Solicitud")
            
            if continuo:
                st.write(f"**Período:** Servicio continuo desde {fecha_seleccionada}")
            else:
                st.write(f"**Período:** {', '.join(meses_seleccionados)} ")
            
            st.write(f"**Fecha de solicitud:** {fecha_str}")
            st.write(f"**Solicitante:** {nombre_solicitante}")
            
            if iniciales_1 or iniciales_2 or iniciales_3:
                iniciales_list = [i for i in [iniciales_1, iniciales_2, iniciales_3] if i]
                st.write(f"**Aprobado por:** {', '.join(iniciales_list)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Nota informativa
            st.markdown("""
            <div style="border:1px solid #ccc; padding:10px; border-radius:10px; background:#f9f9f9">
            ⚠️ <b>Antes de descargar</b><br>
            Verifica que toda la información esté correcta.<br><br>
            📱 <b>¿Usas un celular?</b><br>
            El archivo puede descargarse con un nombre genérico. Puedes renombrarlo después.<br><br>
            Para <b>compartir</b> el archivo, abre el PDF desde tu dispositivo y usa el botón de <i>Compartir</i>.
            </div>
            """, unsafe_allow_html=True)

            #envio de info a telegram
            enviar_notificacion_telegram(
                nombre_solicitante, 
                meses_seleccionados, 
                continuo,
                pdf_buffer,
                nombre_archivo
            )
            # ------------------------------------------
            
            # Botón de descarga
            st.download_button(
                "📥 Descargar Formulario S-205b",
                data=pdf_buffer.getvalue(),
                file_name=nombre_archivo,
                mime="application/pdf"
            )
            
        except Exception as e:
            st.error(f"❌ Ocurrió un error al generar el PDF: {e}")

st.write(f"Longitud del token: {len(st.secrets['TELEGRAM_TOKEN'])}")
