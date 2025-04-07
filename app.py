from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from sklearn.base import defaultdict
from generador_practicas import GeneradorPracticasExtendido, Practica, Usuario
from modelo_ml_scikit import GeneradorPracticasML
from generar_retroalimentacion import generar_retroalimentacion
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from config import DB_CONFIG, APP_CONFIG
from datetime import datetime
import json
import os
import re
import mysql.connector
import random

# Inicializar aplicación Flask
port = 5000
app = Flask(__name__)
app.secret_key = APP_CONFIG["SECRET_KEY"]
app.config['DEBUG'] = APP_CONFIG["DEBUG"]
app.config['MAX_CONTENT_LENGTH'] = APP_CONFIG["MAX_CONTENT_LENGTH"]

generador = GeneradorPracticasExtendido(DB_CONFIG)

modelo_ml = GeneradorPracticasML()

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'tu_correo_.com'
app.config['MAIL_PASSWORD'] = 'contraseña_de_aplicacion'

mail = Mail(app)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='generador_practicas'  
    )
    return connection

def generar_numero_cuenta():
    while True:
        numero_cuenta = random.randint(100000000, 999999999)  
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE numero_cuenta = %s", (numero_cuenta,))
        existe = cursor.fetchone()[0]
        if existe == 0:  
            return numero_cuenta

def enviar_correo(email, nombre, numero_cuenta, password):
    try:
        msg = Message(
            "Cuenta Aprobada",
            sender="tu_correo@gmail.com",
            recipients=[email]
        )
        msg.body = f"""Hola {nombre},

Tu cuenta ha sido aprobada.

No. de cuenta: {numero_cuenta}
Clave: {password}

Saludos."""
        
        msg.body = msg.body.encode("utf-8").decode("utf-8")
        msg.charset = "utf-8"  

        mail.send(msg)
        print("Correo enviado correctamente")
    except Exception as e:
        print(f"Error al enviar correo: {str(e)}")

@app.route('/registro', methods=['GET'])
def registro():
    return render_template('registro.html')

@app.route('/registro', methods=['POST'])
def registrar_solicitud():
    connection = None  
    try:
        data = request.json
        nombre = data['nombre']
        email = data['email']
        password = data['password']
        rol_solicitado = data['rol']  

        password_hash = generate_password_hash(password)

        connection = get_db_connection()  
        cursor = connection.cursor()
        query = """
        INSERT INTO solicitudes_registro (nombre, email, password_hash, rol_solicitado, password)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nombre, email, password_hash, rol_solicitado, password))  
        connection.commit()  

        return jsonify({"message": "Solicitud enviada correctamente"}), 201
    except Exception as e:
        if connection:  
            connection.rollback()  
        return jsonify({"error": str(e)}), 500
    finally:
        if connection:  
            connection.close()

@app.route('/gestionar_solicitudes', methods=['GET', 'POST'])
def gestionar_solicitudes():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'GET':
        query = "SELECT * FROM solicitudes_registro WHERE estado = 'pendiente'"
        cursor.execute(query)
        solicitudes = cursor.fetchall()
        return render_template('solicitudes.html', solicitudes=solicitudes)  

    if request.method == 'POST':
        data = request.json
        solicitud_id = data['id']
        accion = data['accion']  

        try:
            if accion == 'aprobar':
                query = "UPDATE solicitudes_registro SET estado = 'aprobada' WHERE id = %s"
                cursor.execute(query, (solicitud_id,))
                connection.commit()
                
                cursor.execute("SELECT nombre, email, password_hash, rol_solicitado, password FROM solicitudes_registro WHERE id = %s", (solicitud_id,))
                solicitud = cursor.fetchone()

                if not solicitud:
                    return jsonify({"error": "Solicitud no encontrada."}), 404

                numero_cuenta = generar_numero_cuenta()

                insert_query = """
                INSERT INTO usuarios (nombre, email, password_hash, rol, numero_cuenta)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (solicitud['nombre'], solicitud['email'], solicitud['password_hash'], solicitud['rol_solicitado'], numero_cuenta))
                connection.commit()

                enviar_correo(solicitud['email'], solicitud['nombre'], numero_cuenta, solicitud['password']) 

                print(f"Solicitud {solicitud_id} aprobada y correo enviado.") 
                return jsonify({"message": "Solicitud aprobada correctamente"}), 200

            elif accion == 'rechazar':
                query = "UPDATE solicitudes_registro SET estado = 'rechazada' WHERE id = %s"
                cursor.execute(query, (solicitud_id,))
                connection.commit()
                print(f"Solicitud {solicitud_id} rechazada.")  
                return jsonify({"message": "Solicitud rechazada correctamente"}), 200

        except Exception as e:
            connection.rollback()  
            print(f"Error al actualizar la solicitud: {str(e)}") 
            return jsonify({"error": str(e)}), 500
        finally:
            connection.close()  

@app.route('/api/evaluate', methods=['POST'])
def evaluar_entrega_api():
    """API para evaluar entregas de estudiantes"""
    try:
        if 'archivo' not in request.files:
            return jsonify({"error": "No se proporcionó ningún archivo"}), 400
            
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
            
        if not allowed_file(archivo.filename):
            return jsonify({"error": "Tipo de archivo no permitido. Solo se aceptan PDF, DOCX y TXT."}), 400
            
        if request.content_length > APP_CONFIG["MAX_CONTENT_LENGTH"]:
            return jsonify({"error": "El archivo es demasiado grande. El tamaño máximo es 10MB."}), 400
            
        practica_id = request.form.get('practica_id')
        estudiante_id = request.form.get('estudiante_id')
        
        if not practica_id or not estudiante_id:
            return jsonify({"error": "Faltan datos requeridos (practica_id o estudiante_id)"}), 400
            
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        try:
            archivo.save(filepath)
            print(f"Archivo guardado en {filepath}")
        except Exception as e:
            print(f"Error al guardar archivo: {str(e)}")
            return jsonify({"error": f"Error al guardar archivo: {str(e)}"}), 500
            
        contenido = leer_contenido_archivo(filepath)
        
        if not contenido:
            return jsonify({"error": "No se pudo leer el contenido del archivo"}), 400
            
        practica = generador.obtener_practica_por_id(int(practica_id))
        if not practica:
            return jsonify({"error": "Práctica no encontrada"}), 404
            
        resultado = modelo_ml.analizar_contenido(contenido, practica.titulo, practica.objetivo)
        
        retroalimentacion = generar_retroalimentacion(
            resultado['calificacion'],
            contenido,
            practica.titulo,
            practica.objetivo
        )
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query_eval = """
        SELECT id FROM evaluaciones
        WHERE practica_id = %s AND estudiante_id = %s
        """
        cursor.execute(query_eval, (practica_id, estudiante_id))
        eval_result = cursor.fetchone()
        evaluacion_id = eval_result['id'] if eval_result else None
        connection.close()
        
        entrega = {
            'practica_id': int(practica_id),
            'estudiante_id': int(estudiante_id),
            'contenido': contenido,
            'fecha_entrega': datetime.now(),
            'estado': 'entregado',
            'archivos_url': filename,
            'evaluacion_id': evaluacion_id  
        }
        
        try:
            entrega_id = generador.registrar_entrega(entrega)
            
            comentarios_completos = {
                "comentarios": resultado['comentarios'],
                "sugerencias": resultado['sugerencias'],
                "retroalimentacion_positiva": retroalimentacion['positivo'],
                "areas_mejora": retroalimentacion['mejoras'],
                "relevancia": resultado['relevancia']
            }
            
            comentarios_json = json.dumps(comentarios_completos)
            
            query_eval = """
                UPDATE evaluaciones 
                SET calificacion = %s, comentarios = %s, estado = 'calificado' 
                WHERE id = %s
            """
            generador.cursor.execute(query_eval, (
                resultado['calificacion'], 
                comentarios_json, 
                evaluacion_id
            ))
            generador.connection.commit()
            
            print(f"Evaluación actualizada con ID: {evaluacion_id}")
            
        except Exception as e:
            print(f"Error al registrar entrega en la base de datos: {str(e)}")
            return jsonify({"error": f"Error al registrar entrega: {str(e)}"}), 500
        
        # Devolver el resultado de la evaluación
        return jsonify({
            "success": True,
            "evaluacion": {
                "calificacion": resultado['calificacion'],
                "comentarios": resultado['comentarios'],
                "sugerencias": resultado['sugerencias'],
                "relevancia": resultado['relevancia'],
                "retroalimentacion_positiva": retroalimentacion['mejoras'],
                "areas_mejora": retroalimentacion['mejoras']
            }
        }), 200
        
    except Exception as e:
        print(f"Error en la API de evaluación: {str(e)}")
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 500

@app.route('/evaluar_entrega_automatica', methods=['POST'])
def evaluar_entrega_automatica():
  """Califica automáticamente una entrega usando la red neuronal."""
  try:
      data = request.json
      evaluacion_id = data.get('evaluacion_id')
      
      if not evaluacion_id:
          return jsonify({"success": False, "error": "No se proporcionó ID de evaluación"}), 400
          
      print(f"Evaluando entrega automáticamente para evaluación ID: {evaluacion_id}")
      
      evaluacion = generador.obtener_evaluacion_por_id(evaluacion_id)
      
      if not evaluacion:
          return jsonify({"success": False, "error": f"Evaluación con ID {evaluacion_id} no encontrada"}), 404
          
      print(f"Información de evaluación obtenida: {evaluacion}")
      
      print(f"Buscando entrega asociada a la evaluación con ID: {evaluacion_id}")
      entrega = generador.obtener_entrega_por_evaluacion(evaluacion_id)
      print(f"Resultado de obtener_entrega_por_evaluacion: {entrega}")
      
      if not entrega:
          print(f"Intentando buscar entrega por practica_id: {evaluacion['practica_id']} y estudiante_id: {evaluacion['estudiante_id']}")
          connection = get_db_connection()
          cursor = connection.cursor(dictionary=True)
          query = """
          SELECT id, archivos_url, contenido
          FROM entregas
          WHERE practica_id = %s AND estudiante_id = %s
          ORDER BY fecha_entrega DESC
          LIMIT 1
          """
          cursor.execute(query, (evaluacion['practica_id'], evaluacion['estudiante_id']))
          entrega = cursor.fetchone()
          connection.close()
          
          if not entrega:
              return jsonify({"success": False, "error": f"No se encontró una entrega asociada a la evaluación con ID: {evaluacion_id}"}), 404
      
      archivo_url = entrega['archivos_url']
      ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], archivo_url)
      
      if not os.path.exists(ruta_archivo):
          return jsonify({"success": False, "error": f"Archivo no encontrado: {archivo_url}"}), 404
          
      contenido_entrega = leer_contenido_archivo(ruta_archivo)
      
      if not contenido_entrega:
          return jsonify({"success": False, "error": "No se pudo leer el contenido del archivo"}), 400
      
      print("Contenido del archivo de texto:")
      print(contenido_entrega[:200] + "..." if len(contenido_entrega) > 200 else contenido_entrega)
      
      resultado_ml = modelo_ml.analizar_contenido(
          contenido_entrega,
          evaluacion['practica_titulo'],
          evaluacion.get('practica_objetivo', '')
      )
      
      calificacion = resultado_ml['calificacion']
      comentarios = resultado_ml['comentarios']
      
      print("Calificación y comentarios generados:")
      print("Calificación:", calificacion)
      print("Comentarios:", comentarios)
      
      generador.actualizar_evaluacion(evaluacion_id, comentarios, calificacion)
      
      connection = get_db_connection()
      cursor = connection.cursor()
      query_update_entrega = """
      UPDATE entregas
      SET evaluacion_id = %s, estado = 'calificado'
      WHERE id = %s
      """
      cursor.execute(query_update_entrega, (evaluacion_id, entrega['id']))
      connection.commit()
      connection.close()
      
      return jsonify({
          "success": True,
          "calificacion": calificacion,
          "comentarios": comentarios
      }), 200
  
  except Exception as e:
      print(f"Error en evaluar_entrega_automatica: {str(e)}")
      return jsonify({"success": False, "error": str(e)}), 500

@app.route('/entrenar_modelo', methods=['POST'])
def entrenar_modelo():
    try:
        # Datos de entrenamiento
        entradas = [
            "Crear una base de datos relacional con MySQL.",
            "Diseñar un sistema de gestión de inventarios.",
            "Escribir consultas SQL para manipular datos en una base de datos.",
            "Crear tablas y relaciones en una base de datos relacional.",
            "Optimizar consultas SQL para mejorar el rendimiento.",
            "Resolver ecuaciones diferenciales de primer orden.",
            "Desarrollar una aplicación web con Django.",
            "Analizar datos utilizando pandas y matplotlib.",
            "Diseñar un circuito electrónico para un sensor de temperatura.",
            "Escribir un ensayo sobre la literatura del siglo XX.",
            "Estudiar las propiedades químicas de los compuestos orgánicos.",
            "Crear un modelo de predicción utilizando machine learning.",
            "Implementar un sistema de autenticación con JWT.",
            "Realizar un análisis estadístico de datos financieros.",
            "Desarrollar un videojuego 2D utilizando Unity.",
            "Diseñar un experimento para medir la velocidad de reacción química.",
            "Crear un chatbot utilizando procesamiento de lenguaje natural."
        ]

        salidas = [
            9.0, 8.5, 9.5, 9.0, 8.5, 8.0, 9.5, 8.0, 8.5, 7.0, 8.0, 9.0, 8.5, 8.0, 9.0, 8.5, 9.0
        ]

        # Entrenar el modelo
        generador.modelo_ml.entrenar_modelo(entradas, salidas, epochs=10, batch_size=4)

        return jsonify({"success": True, "message": "Modelo entrenado correctamente."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def leer_contenido_archivo(filepath):
    """
    Lee el contenido de un archivo según su tipo.
    Soporta: .txt, .pdf, .docx
    """
    try:
        extension = os.path.splitext(filepath)[1].lower()
        
        if extension == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
                
        elif extension == '.pdf':
            try:
                # Use PyPDF2 to read PDF
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                return text
            except ImportError:
                print("PyPDF2 no está instalado. No se puede leer el archivo PDF.")
                return "No se pudo leer el contenido del archivo PDF. PyPDF2 no está instalado."
            
        elif extension == '.docx':
            try:
                import docx
                doc = docx.Document(filepath)
                return " ".join([paragraph.text for paragraph in doc.paragraphs])
            except ImportError:
                print("python-docx no está instalado. No se puede leer el archivo DOCX.")
                return "No se pudo leer el contenido del archivo DOCX. python-docx no está instalado."
            
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
                
    except Exception as e:
        print(f"Error al leer el archivo {filepath}: {str(e)}")
        return ""

def calificar_entrega(titulo, objetivo, entrega):
    # Implementa la lógica para calificar la entrega
    # Aquí puedes usar un modelo de ML o lógica basada en reglas
    # Por simplicidad, asignaremos una calificación fija
    return 8.5  # Cambia esto por la lógica real

def dividir_texto_en_fragmentos(texto, max_palabras=100):
    """Divide el texto en fragmentos de un número máximo de palabras."""
    palabras = texto.split()
    for i in range(0, len(palabras), max_palabras):
        yield ' '.join(palabras[i:i + max_palabras])

def preprocesar_texto(texto):
    """Elimina caracteres especiales y convierte el texto a minúsculas."""
    texto = re.sub(r'[^\w\s]', '', texto.lower())
    return texto.strip()

@app.route('/cargar_modelo', methods=['GET'])
def cargar_modelo():
    """
    Carga el modelo entrenado desde un archivo.
    """
    try:
        generador.modelo_ml.cargar_modelo()
        return jsonify({"success": True, "message": "Modelo cargado correctamente."}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/estudiante/<int:estudiante_id>')
def vista_estudiante(estudiante_id):
    """Muestra las prácticas activas de un estudiante y sus entregas."""
    practicas = generador.obtener_practicas_estudiante(estudiante_id)
    entregas = generador.obtener_entregas_por_estudiante(estudiante_id)  
    
    evaluaciones_calificadas = generador.obtener_evaluaciones_calificadas(estudiante_id)
    
    año_actual = datetime.now().year
    return render_template('estudiante.html', 
                          practicas=practicas, 
                          entregas=entregas, 
                          evaluaciones_calificadas=evaluaciones_calificadas,
                          año_actual=año_actual)

@app.route('/')
def index():
    if 'usuario_id' in session:
        if session['rol'] == 'administrador':
            return redirect(url_for('admin_dashboard'))
        elif session['rol'] == 'profesor':
            return redirect(url_for('profesor_dashboard'))
        else:
            return redirect(url_for('usuario_dashboard'))
    return render_template('index.html')

@app.route('/practicas', methods=['POST'])
def crear_practica():
    """Guarda una nueva práctica con la opción de calificación automática."""
    titulo = request.form['titulo']
    materia_id = int(request.form['materia_id'])
    nivel_id = int(request.form['nivel_id'])
    autor_id = int(request.form['autor_id'])
    objetivo = request.form['objetivo']
    fecha_entrega = request.form['fecha_entrega']
    tiempo_estimado = int(request.form['tiempo_estimado'])
    concepto_id = int(request.form['concepto_id'])
    herramienta_id = int(request.form['herramienta_id'])
    uso_ia = bool(int(request.form['uso_ia'])) 
    grupo_id = int(request.form['grupo_id'])

    practica = Practica(
        titulo=titulo,
        materia_id=materia_id,
        nombre_materia="",  # Se asigna después
        nivel_id=nivel_id,
        autor_id=int(autor_id), 
        objetivo=objetivo,
        fecha_entrega=datetime.strptime(fecha_entrega, '%Y-%m-%d'),
        estado='pendiente',
        concepto_id=concepto_id,
        herramienta_id=herramienta_id,
        tiempo_estimado=tiempo_estimado,
        uso_ia=uso_ia,  
        grupo_id=grupo_id,

    )

    generador.crear_practica(practica)
    flash("Práctica creada exitosamente", "success")
    return redirect(url_for('practicas'))

@app.route('/practicas', methods=['GET', 'POST'])
def practicas():
    nombre_grupo = ""  

    if request.method == 'POST':
        titulo = request.form['titulo']
        materia_id = int(request.form['materia_id'])
        nivel_id = int(request.form['nivel_id'])
        objetivo = request.form['objetivo']
        fecha_entrega = request.form['fecha_entrega']
        tiempo_estimado = int(request.form['tiempo_estimado'])
        concepto_id = int(request.form['concepto_id'])
        herramienta_id = int(request.form['herramienta_id'])
        estudiante_id = int(request.form['estudiante_id'])  
        uso_ia = bool(int(request.form['uso_ia']))  
        grupo_id = int(request.form['grupo_id'])

        autor_id = request.form.get('autor_id') 
        if not autor_id and session.get('rol') == 'profesor':
            autor_id = session.get('usuario_id') 

        if not autor_id:
            flash("Error: No se pudo determinar el autor de la práctica.", "error")
            return redirect(url_for('practicas'))

        # Crear la práctica
        practica = Practica(
            titulo=titulo,
            materia_id=materia_id,
            nombre_materia="", 
            nivel_id=nivel_id,
            autor_id=int(autor_id), 
            objetivo=objetivo,
            fecha_entrega=datetime.strptime(fecha_entrega, '%Y-%m-%d'),
            estado='pendiente',
            concepto_id=concepto_id,
            herramienta_id=herramienta_id,
            tiempo_estimado=tiempo_estimado,
            uso_ia=uso_ia,  
            grupo_id=grupo_id
        )

        practica_id = generador.crear_practica(practica)

        nombre_clase = generador.obtener_nombre_clase_por_practica(practica_id)

        generador.crear_evaluacion_para_practica(practica_id, estudiante_id)
        
        flash("Práctica creada exitosamente", "success")
        return redirect(url_for('practicas'))

    profesor_id = session['usuario_id']  
    materias = generador.obtener_materias()
    niveles = generador.obtener_niveles()
    conceptos = generador.obtener_conceptos()
    grupos = generador.obtener_grupos_por_profesor(profesor_id)
    herramientas = generador.obtener_herramientas()
    autorizados = generador.obtetener_usuarios_autorizados() 

    return render_template(
        'practicas.html',
        materias=materias,
        niveles=niveles,
        conceptos=conceptos,
        herramientas=herramientas,
        autorizados=autorizados,
        practicas=generador.obtener_practicas(),
        usuario_nombre=session.get('usuario_nombre'),
        rol=session.get('rol'),
        grupos=grupos,
        nombre_clase=nombre_clase if 'nombre_clase' in locals() else None 
    )

@app.route('/calificar_automatico', methods=['POST'])
def calificar_automatico():
    """Califica automáticamente las entregas usando la red neuronal y actualiza evaluaciones."""
    try:
        query = "SELECT id, practica_id, estudiante_id, archivos_url FROM entregas WHERE estado = 'pendiente'"
        generador.cursor.execute(query)
        entregas = generador.cursor.fetchall()
        
        if not entregas:
            flash("No hay entregas pendientes para calificar.", "info")
            return redirect(url_for('evaluacion'))
        
        for entrega in entregas:
            entrega_id = entrega['id']
            practica_id = entrega['practica_id']
            estudiante_id = entrega['estudiante_id']
            archivos_url = entrega['archivos_url']  
            
            practica = generador.obtener_practica_por_id(practica_id)
            
            if not practica:
                flash(f"Práctica ID {practica_id} no encontrada.", "warning")
                continue  
            
            if not practica.uso_ia:
                continue  
            
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], archivos_url)
            if not os.path.exists(ruta_archivo):
                flash(f"Archivo no encontrado para la entrega ID {entrega_id}: {archivos_url}", "warning")
                continue
                
            contenido_entrega = leer_contenido_archivo(ruta_archivo)
            
            if not contenido_entrega:
                flash(f"No se pudo leer el contenido del archivo para la entrega ID {entrega_id}", "warning")
                continue
            
            resultado_ml = modelo_ml.analizar_contenido(
                contenido_entrega,
                practica.titulo,
                practica.objetivo
            )
            
            calificacion = resultado_ml.get('calificacion')
            comentarios = resultado_ml.get('comentarios')
            
            if calificacion is None or comentarios is None:
                flash(f"No se pudo generar calificación para la entrega ID {entrega_id}.", "warning")
                continue
            
            query_eval = """
                UPDATE evaluaciones 
                SET calificacion = %s, comentarios = %s, estado = 'calificado' 
                WHERE practica_id = %s AND estudiante_id = %s
            """
            generador.cursor.execute(query_eval, (calificacion, comentarios, practica_id, estudiante_id))
            
            query_update = "UPDATE entregas SET estado = 'calificado' WHERE id = %s"
            generador.cursor.execute(query_update, (entrega_id,))
        
        generador.connection.commit()
        flash("Entregas calificadas automáticamente.", "success")
    except Exception as e:
        generador.connection.rollback()
        flash(f"Error en la calificación automática: {str(e)}", "error")
    
    return redirect(url_for('evaluacion'))

@app.route('/eliminar_evaluacion/<int:evaluacion_id>', methods=['POST'])
def eliminar_evaluacion(evaluacion_id):
    try:
        generador.eliminar_evaluacion(evaluacion_id)  
        flash("Evaluación eliminada correctamente", "success")
    except Exception as e:
        flash(f"Error al eliminar evaluación: {str(e)}", "error")

    return redirect(url_for('evaluacion'))

@app.route('/eliminar_practica/<int:practica_id>', methods=['POST'])
def eliminar_practica(practica_id):
    try:
        generador.eliminar_practica(practica_id)  
        flash("Práctica eliminada correctamente", "success")
    except Exception as e:
        flash(f"Error al eliminar práctica: {str(e)}", "error")

    return redirect(url_for('practicas'))

@app.route('/generar_practica', methods=['GET', 'POST'])
def generar_practica_view():
    if request.method == 'POST':
        titulo = request.form['titulo']
        objetivo = request.form['objetivo']
        
        try:
            practica_generada = modelo_ml.generar_practica(titulo, objetivo)
            
            return render_template('resultado.html', 
                                   practica=practica_generada, 
                                   titulo=titulo, 
                                   objetivo=objetivo)
        except Exception as e:
            flash(f"Error al generar práctica: {str(e)}", "error")
            return redirect(url_for('generar_practica_view'))
    
    return render_template('generar_practica.html')

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        rol = request.form['rol']
        
        usuario = Usuario(
            id=None,
            nombre=nombre,
            email=email,
            rol=rol
        )
        
        try:
            generador.agregar_usuario(usuario)
            flash("Usuario agregado exitosamente", "success")
        except Exception as e:
            flash(f"Error al agregar usuario: {str(e)}", "error")
        
        return redirect(url_for('usuarios'))
    
    usuarios = generador.obtener_usuarios()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/evaluacion', methods=['GET', 'POST'])
def evaluacion():
    if request.method == 'POST':
        evaluacion_id = int(request.form['evaluacion_id'])
        comentario = request.form['comentarios']  
        
        calificacion_str = request.form.get('calificacion', '').strip()
        calificacion = float(calificacion_str) if calificacion_str else None  
        
        try:
            generador.actualizar_evaluacion(evaluacion_id, comentario, calificacion)
            flash("Evaluación actualizada exitosamente", "success")
        except Exception as e:
            flash(f"Error al actualizar evaluación: {str(e)}", "error")
        
        return redirect(url_for('evaluacion'))

    todas_practicas = generador.obtener_practicas()

    practicas_por_materia = defaultdict(list)
    for practica in todas_practicas:
        materia_id = practica.materia_id
        estudiantes = generador.obtener_estudiantes_por_practica(practica.id)
        
        for estudiante in estudiantes:
            if 'archivo_url' not in estudiante:
                estudiante['archivo_url'] = estudiante.get('archivos_url', '')  
            if 'estado' not in estudiante:
                estudiante['estado'] = estudiante.get('estado', 'pendiente')  
        practica.estudiantes = estudiantes
        practicas_por_materia[materia_id].append(practica)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM materias")
    materias = cursor.fetchall()

    cursor.execute("""
        SELECT e.id AS entrega_id, e.practica_id, e.estudiante_id, e.evaluacion_id, e.fecha_entrega, e.estado, 
               e.archivos_url, e.calificacion, e.contenido, 
               p.titulo AS practica_titulo, p.uso_ia, u.nombre AS estudiante_nombre
        FROM entregas e
        JOIN practicas p ON e.practica_id = p.id
        JOIN usuarios u ON e.estudiante_id = u.id
    """)
    entregas = cursor.fetchall()

    for entrega in entregas:
        practica_id = entrega['practica_id']
        for practica in practicas_por_materia[practica_id]:
            for estudiante in practica.estudiantes:
                if estudiante['id'] == entrega['estudiante_id']:
                    estudiante['estado'] = entrega['estado']
                    estudiante['archivo_url'] = entrega['archivos_url']
                    estudiante['evaluacion_id'] = entrega['evaluacion_id']
                    estudiante['uso_ia'] = entrega['uso_ia']  

    connection.close()

    todas_evaluaciones = generador.obtener_evaluaciones()
    
    evaluaciones_pendientes = [ev for ev in todas_evaluaciones if ev['calificacion'] is None]
    evaluaciones_calificadas = [ev for ev in todas_evaluaciones if ev['calificacion'] is not None]

    return render_template(
        'evaluacion.html',
        practicas_por_materia=practicas_por_materia,
        materias=materias,
        evaluaciones=evaluaciones_pendientes,
        evaluaciones_calificadas=evaluaciones_calificadas,
        todas_evaluaciones=todas_evaluaciones  
    )

@app.route('/guardar_calificacion', methods=['POST'])
def guardar_calificacion():
    """Guarda la calificación y los comentarios de una evaluación manual."""
    try:
        evaluacion_id = request.form['evaluacion_id']
        calificacion = request.form['calificacion']
        comentarios = request.form['comentarios']

        with closing(get_db_connection()) as connection:
            cursor = connection.cursor()
            query = """
            UPDATE evaluaciones
            SET calificacion = %s, comentarios = %s, estado = 'calificado'
            WHERE id = %s
            """
            cursor.execute(query, (calificacion, comentarios, evaluacion_id))
            connection.commit()

        flash("Calificación guardada exitosamente.", "success")
    except Exception as e:
        flash(f"Error al guardar la calificación: {str(e)}", "error")

    return redirect(url_for('evaluacion'))

@app.route('/practica/<int:practica_id>', methods=['GET'])
def ver_practica(practica_id):
    practica = generador.obtener_practica_por_id(practica_id)
    contenido_generado = generador.obtener_contenido_generado(practica_id)
    
    if not practica:
        flash("Práctica no encontrada.", "error")
        return redirect(url_for('practicas'))  

    titulo = practica.titulo
    objetivo = practica.objetivo
    practica_generada = modelo_ml.generar_practica(titulo, objetivo)
    
    prediccion_exito = 'Alta'  
    recomendaciones_personalizadas = 'Recomendaciones personalizadas generadas por IA'  
    
    modelo_ml_data = {
        'prediccion_exito': prediccion_exito,
        'recomendaciones_personalizadas': recomendaciones_personalizadas
    }
    
    contenido_generado = {
        'descripcion': practica_generada['descripcion'],
        'objetivos_especificos': practica_generada['objetivos_especificos'],
        'actividades': practica_generada['actividades'],
        'recursos': practica_generada['recursos'],
        'criterios_evaluacion': practica_generada['criterios_evaluacion'],
        'recomendaciones': practica_generada['recomendaciones']
    }
    
    print(f"Práctica: {practica}")
    print(f"Contenido generado: {contenido_generado}")
    print(f"Datos generados por IA: {modelo_ml_data}")
    
    return render_template('ver_practica.html', practica=practica, contenido=contenido_generado, modelo_ml=modelo_ml_data)

@app.route('/api/generar_practica', methods=['POST'])
def api_generar_practica():
    """API para generar prácticas automáticamente"""
    datos = request.get_json()
    
    if not datos or 'titulo' not in datos or 'objetivo' not in datos:
        return jsonify({'error': 'Se requieren título y objetivo'}), 400
    
    try:
        practica_generada = modelo_ml.generar_practica(datos['titulo'], datos['objetivo'])
        return jsonify({'practica': practica_generada}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/usuarios', methods=['GET'])
def obtener_usuarios():
    try:
        usuarios = generador.obtener_usuarios()
        return jsonify({'usuarios': usuarios}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/inicio')
def inicio():
    # Obtener estadísticas para el dashboard
    practicas_activas = generador.obtener_practicas_activas()
    entregas_pendientes = generador.obtener_entregas_pendientes()
    usuarios_registrados = generador.obtener_usuarios_registrados()
    actividades_recientes = generador.obtener_actividades_recientes()
    
    return render_template('inicio.html', 
                           practicas_activas=practicas_activas, 
                           entregas_pendientes=entregas_pendientes, 
                           usuarios_registrados=usuarios_registrados,
                           actividades_recientes=actividades_recientes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        numero_cuenta = request.form['numero_cuenta']
        password = request.form['password']
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre, rol, password_hash FROM usuarios WHERE numero_cuenta = %s", (numero_cuenta,))
        usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario['password_hash'], password):
            session['usuario_id'] = usuario['id']
            session['usuario_nombre'] = usuario['nombre']
            session['rol'] = usuario['rol']
            session['inicio_sesion'] = datetime.now()  
            
            if usuario['rol'] == 'administrador':
                return redirect(url_for('admin_dashboard'))
            elif usuario['rol'] == 'profesor':
                return redirect(url_for('profesor_dashboard'))
            elif usuario['rol'] == 'estudiante':
                return redirect(url_for('usuario_dashboard'))
            else:
                flash('Rol desconocido. Contacta al administrador.', 'error')
                return redirect(url_for('login'))
        else:
            flash('Credenciales inválidas', 'error')
    
    return render_template('index.html')

@app.route('/aulas', methods=['GET', 'POST'])
def aulas():
    if request.method == 'POST':
        materia_id = request.form['materia_id']
        semestre_id = request.form['semestre_id']
        grupo_numero = request.form['grupo_numero']  
        profesor_id = session['usuario_id']

        materia = generador.obtener_materia_por_id(materia_id) 
        nombre_materia = materia['nombre'] 

        turno = request.form['turno']
        turno_letra = 'A' if turno == 'matutino' else 'B'

        nombre_grupo = f"{nombre_materia} {turno_letra}-{semestre_id}{grupo_numero}"

        try:
            query = """
            INSERT INTO grupos (nombre, descripcion, materia_id, semestre_id, profesor_id, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(query, (nombre_grupo, request.form['descripcion'], materia_id, semestre_id, profesor_id))
            connection.commit()
            flash("Grupo creado exitosamente", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Error al crear grupo: {str(e)}", "error")
        finally:
            connection.close()

        return redirect(url_for('aulas'))  

    grupos = generador.obtener_grupos_con_estudiantes()
    materias = generador.obtener_materias()
    semestres = generador.obtener_semestres()
    print("Grupos:", grupos)
    print("Materias:", materias)
    print("Semestres:", semestres)
    return render_template('aulas.html', grupos=grupos, materias=materias, semestres=semestres)

@app.route('/editar_grupo/<int:grupo_id>', methods=['GET', 'POST'])
def editar_grupo(grupo_id):
    if request.method == 'POST':
        descripcion = request.form['descripcion']
        turno = request.form['turno']
        semestre_id = request.form['semestre_id']

        try:
            query = """
            UPDATE grupos
            SET descripcion = %s, turno = %s, semestre_id = %s
            WHERE id = %s
            """
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(query, (descripcion, turno, semestre_id, grupo_id))
            connection.commit()
            flash("Grupo actualizado exitosamente", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Error al actualizar grupo: {str(e)}", "error")
        finally:
            connection.close()

        return redirect(url_for('aulas'))  

    grupo = generador.obtener_grupo_por_id(grupo_id) 
    semestres = generador.obtener_semestres()
    return render_template('editar_grupo.html', grupo=grupo, semestres=semestres)

@app.route('/ver_detalles_grupo/<int:grupo_id>', methods=['GET'])
def ver_detalles_grupo(grupo_id):
    grupo = generador.obtener_grupo_por_id(grupo_id)  
    estudiantes = generador.obtener_estudiantes_por_grupo(grupo_id) 

    return render_template('ver_detalles_grupo.html', grupo=grupo, estudiantes=estudiantes)

@app.route('/gestionar_estudiantes/<int:grupo_id>', methods=['GET', 'POST'])
def gestionar_estudiantes(grupo_id):
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() 
            usuario_id = data.get('usuario_id')  
            accion = data.get('accion') 
        else:
            usuario_id = request.form.get('usuario_id')
            accion = request.form.get('accion')

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            if accion == 'agregar':
                query = """
                SELECT * FROM grupo_miembros
                WHERE grupo_id = %s AND usuario_id = %s
                """
                cursor.execute(query, (grupo_id, usuario_id))
                if cursor.fetchone():
                    return jsonify(success=False, message="El estudiante ya está inscrito"), 400

                query = """
                INSERT INTO grupo_miembros (grupo_id, usuario_id, rol)
                VALUES (%s, %s, 'miembro')
                """
                cursor.execute(query, (grupo_id, usuario_id))
                connection.commit()
                return jsonify(success=True, message="Estudiante agregado exitosamente"), 200

            elif accion == 'eliminar':
                query = """
                DELETE FROM grupo_miembros
                WHERE grupo_id = %s AND usuario_id = %s
                """
                cursor.execute(query, (grupo_id, usuario_id))
                connection.commit()
                return jsonify(success=True, message="Estudiante eliminado exitosamente"), 200

        except Exception as e:
            connection.rollback()  
            return jsonify(success=False, error=str(e)), 500
        finally:
            cursor.close()
            connection.close()

    grupo = generador.obtener_grupo_por_id(grupo_id)
    estudiantes = generador.obtener_estudiantes_por_grupo(grupo_id)  
    todos_estudiantes = generador.obtener_estudiantes()  

    return render_template('gestionar_estudiantes.html', grupo=grupo, estudiantes=estudiantes, todos_estudiantes=todos_estudiantes)
    
@app.route('/profesor_usuarios', methods=['GET', 'POST'])
def profesor_usuarios():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            email = request.form['email']
            password = request.form['password']

            if not nombre.strip() or not email.strip() or not password.strip():
                flash("Todos los campos son obligatorios.", "error")
                return redirect(url_for('profesor_usuarios'))

            password_hash = generate_password_hash(password)

            rol = 'estudiante'  
            generador.registrar_usuario(nombre, email, password_hash, rol)
            flash("Estudiante agregado correctamente.", "success")
        except Exception as e:
            flash(f"Error al agregar estudiante: {str(e)}", "error")

        return redirect(url_for('profesor_usuarios'))

    estudiantes = generador.obtener_usuarios_por_rol('estudiante') 
    return render_template('profesor_usuarios.html', estudiantes=estudiantes)

@app.route('/profesor_dashboard')
def profesor_dashboard():
    if 'usuario_id' not in session or session.get('rol') != 'profesor':
        return redirect(url_for('login'))
    return render_template('profesor_dashboard.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'usuario_id' not in session or session.get('rol') != 'administrador':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/usuario_dashboard')
def usuario_dashboard():
    estudiante_id = session.get('usuario_id') 
    if not estudiante_id:
        return redirect(url_for('login')) 

    return render_template('usuario_dashboard.html', estudiante_id=estudiante_id)

@app.route('/admin_usuarios', methods=['GET', 'POST'])
def admin_usuarios():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            email = request.form['email']
            rol = request.form['rol']
            password = request.form['password']

            if not nombre.strip() or not email.strip() or not rol.strip() or not password.strip():
                flash("Todos los campos son obligatorios.", "error")
                return redirect(url_for('admin_usuarios'))

            password_hash = generate_password_hash(password)

            generador.registrar_usuario(nombre, email, password_hash, rol)
            flash("Usuario agregado correctamente.", "success")
        except Exception as e:
            flash(f"Error al agregar usuario: {str(e)}", "error")

        return redirect(url_for('admin_usuarios'))

    usuarios = generador.obtener_usuarios()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/actualizar_rol', methods=['POST'])
def actualizar_rol():
    print("Solicitud recibida en /actualizar_rol") 
    usuario_id = request.form.get('usuario_id')
    nuevo_rol = request.form.get('nuevo_rol')

    if not usuario_id or not nuevo_rol:
        print("Faltan datos en el formulario")  
        return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
    
    generador = GeneradorPracticasExtendido(DB_CONFIG)
    
    nuevo_rol_verificado = generador.actualizar_rol_usuario(int(usuario_id), nuevo_rol)

    if nuevo_rol_verificado:
        print(f"Rol actualizado a {nuevo_rol_verificado}")  
        if 'usuario_id' in session and session['usuario_id'] == int(usuario_id):
            session['rol'] = nuevo_rol_verificado
            session.modified = True  
        return jsonify({'success': True, 'nuevo_rol': nuevo_rol_verificado})
    
    print("Error al actualizar el rol en la base de datos") 
    return jsonify({'success': False, 'error': 'No se pudo actualizar el rol'}), 500

@app.before_request
def actualizar_sesion_usuario():
    if 'usuario_id' in session:
        usuario_id = session['usuario_id']
        generador = GeneradorPracticasExtendido(DB_CONFIG)
        nuevo_rol = generador.actualizar_rol_usuario(usuario_id, session.get('rol'))

        if nuevo_rol and session.get('rol') != nuevo_rol:
            session['rol'] = nuevo_rol
            session.modified = True

@app.route('/actualizar_sesion', methods=['POST'])
def actualizar_sesion():
    usuario_id = session.get('usuario_id')
    nuevo_rol = session.get('rol') 

    if usuario_id and nuevo_rol:
        generador.actualizar_rol_usuario(usuario_id, nuevo_rol)
        flash("Rol actualizado correctamente.", "success")
    else:
        flash("Error: No se pudo actualizar el rol.", "error")

    return redirect(url_for('index'))  

@app.route('/obtener_grupos/<int:semestre_id>')
def obtener_grupos(semestre_id):
    grupos = generador.obtener_grupos_por_semestre(semestre_id) 
    return jsonify(grupos)


@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}

@app.route('/subir_archivo/<int:practica_id>', methods=['POST'])
def subir_archivo(practica_id):
    """
    Sube un archivo de entrega y lo evalúa utilizando el modelo mejorado.
    """
    estudiante_id = session.get('usuario_id')
    if not estudiante_id:
        flash('Debes iniciar sesión para realizar esta acción.', 'error')
        return redirect(url_for('login')) 

    if 'archivo' not in request.files:
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))
    
    if archivo and allowed_file(archivo.filename):
        filename = secure_filename(archivo.filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            archivo.save(filepath) 
            print(f"Archivo guardado en {filepath}")
        except Exception as e:
            flash(f'Error al guardar el archivo: {str(e)}', 'error')
            return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))

        contenido_archivo = leer_contenido_archivo(filepath)

        if not contenido_archivo or not contenido_archivo.strip():
            flash('El archivo está vacío o no contiene texto válido.', 'error')
            return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))

        try:
            practica = generador.obtener_practica_por_id(practica_id)
            if not practica:
                flash('Práctica no encontrada.', 'error')
                return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            query_eval = """
            SELECT id FROM evaluaciones
            WHERE practica_id = %s AND estudiante_id = %s
            """
            cursor.execute(query_eval, (practica_id, estudiante_id))
            eval_result = cursor.fetchone()
            evaluacion_id = eval_result['id'] if eval_result else None
            connection.close()

            entrega = {
                'practica_id': practica_id,
                'estudiante_id': estudiante_id,
                'contenido': contenido_archivo,
                'fecha_entrega': datetime.now(),
                'estado': 'entregado',  
                'archivos_url': filename,
                'evaluacion_id': evaluacion_id 
            }

            entrega_id = generador.registrar_entrega(entrega)
            print(f"Entrega registrada con estado 'entregado' para practica_id={practica_id}, estudiante_id={estudiante_id}, evaluacion_id={evaluacion_id}")

            connection = get_db_connection()
            cursor = connection.cursor()
            query_evaluaciones = """
                UPDATE evaluaciones
                SET estado = 'entregado'
                WHERE practica_id = %s AND estudiante_id = %s
            """
            cursor.execute(query_evaluaciones, (practica_id, estudiante_id))
            connection.commit()
            cursor.close()
            connection.close()

            print(f"Estado de la evaluación actualizado a 'entregado' para practica_id={practica_id}, estudiante_id={estudiante_id}")

            flash('Archivo subido correctamente. La entrega y evaluación están actualizadas.', 'success')

        except Exception as e:
            flash(f'Error al registrar la entrega o actualizar la evaluación: {str(e)}', 'error')
            
    return redirect(url_for('vista_estudiante', estudiante_id=estudiante_id))

@app.route('/estudiante/<int:estudiante_id>/evaluaciones')
def estudiante_evaluacion(estudiante_id):
    """Muestra las evaluaciones calificadas de un estudiante."""
    evaluaciones_calificadas = generador.obtener_evaluaciones_calificadas(estudiante_id)
    
    entregas = generador.obtener_entregas_por_estudiante(estudiante_id)
    
    año_actual = datetime.now().year
    return render_template('estudiante.html', 
                          practicas=[], 
                          entregas=entregas, 
                          evaluaciones_calificadas=evaluaciones_calificadas,
                          estudiante_id=estudiante_id,
                          año_actual=año_actual)

@app.route('/ver_entrega/<int:evaluacion_id>')
def ver_entrega(evaluacion_id):
    """Muestra los detalles de una entrega específica."""
    evaluacion = generador.obtener_evaluacion_por_id(evaluacion_id)
    
    if not evaluacion:
        flash('Evaluación no encontrada.', 'error')
        return redirect(url_for('usuario_dashboard'))
    
    entrega = generador.obtener_entrega_por_evaluacion(evaluacion_id)
    
    estudiante_id = session.get('usuario_id')
    
    if evaluacion['estudiante_id'] != estudiante_id:
        flash('No tienes permiso para ver esta evaluación.', 'error')
        return redirect(url_for('usuario_dashboard'))
    
    año_actual = datetime.now().year
    return render_template('estudiante.html',
                          practicas=[],  
                          entregas=[entrega] if entrega else [], 
                          evaluaciones_calificadas=[evaluacion], 
                          estudiante_id=estudiante_id,
                          año_actual=año_actual,
                          ver_entrega=True)  

@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def error_servidor(e):
    return render_template('500.html'), 500

# Punto de entrada
if __name__ == '__main__':
    os.makedirs(APP_CONFIG["UPLOAD_FOLDER"], exist_ok=True)
    print("Iniciando servidor Flask...")
    print(f"Server running on: http://127.0.0.1:{port}")
    try:
        app.run(debug=APP_CONFIG["DEBUG"], host='127.0.0.1', port=port)
    except Exception as e:
        print(f"Error al iniciar el servidor: {e}")

from generador_practicas import GeneradorPracticasExtendido

def obtener_evaluaciones_calificadas(self, estudiante_id):
    """Obtiene las evaluaciones calificadas de un estudiante."""
    try:
        query = """
        SELECT e.id, e.practica_id, e.estudiante_id, e.calificacion, e.comentarios, 
               e.estado, e.fecha_evaluacion, p.titulo as practica_titulo
        FROM evaluaciones e
        JOIN practicas p ON e.practica_id = p.id
        WHERE e.estudiante_id = %s AND e.calificacion IS NOT NULL
        ORDER BY e.fecha_evaluacion DESC
        """
        self.cursor.execute(query, (estudiante_id,))
        evaluaciones = self.cursor.fetchall()
        return evaluaciones
    except Exception as e:
        print(f"Error al obtener evaluaciones calificadas: {str(e)}")
        return []

def actualizar_estado_practica(self, practica_id, estudiante_id, estado):
    """Actualiza el estado de una práctica para un estudiante específico."""
    try:
        query = """
        UPDATE evaluaciones
        SET estado = %s
        WHERE practica_id = %s AND estudiante_id = %s
        """
        self.cursor.execute(query, (estado, practica_id, estudiante_id))
        self.connection.commit()
        print(f"Estado de práctica {practica_id} actualizado a '{estado}' para estudiante {estudiante_id}")
        return True
    except Exception as e:
        self.connection.rollback()
        print(f"Error al actualizar estado de práctica: {str(e)}")
        return False

def obtener_entregas_por_estudiante(self, estudiante_id):
    """Obtiene todas las entregas de un estudiante."""
    try:
        query = """
        SELECT id, practica_id, estudiante_id, fecha_entrega, estado, archivos_url, contenido
        FROM entregas
        WHERE estudiante_id = %s
        ORDER BY fecha_entrega DESC
        """
        self.cursor.execute(query, (estudiante_id,))
        entregas = self.cursor.fetchall()
        return entregas
    except Exception as e:
        print(f"Error al obtener entregas por estudiante: {str(e)}")
        return []

