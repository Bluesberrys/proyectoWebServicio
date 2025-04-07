from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
import mysql.connector
from mysql.connector import Error
from dataclasses import dataclass
import hashlib
import secrets
from enum import Enum
from collections import defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from cachetools import TTLCache
import hashlib
from modelo_ml_scikit import GeneradorPracticasML
from db_utils import get_db_connection
from typing import Dict, Any, Optional
import mysql.connector
class EstadoPractica(Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"

@dataclass
class Practica:
    id: Optional[int] = None
    titulo: str = ""
    materia_id: int = 0
    nombre_materia: str = ""
    nivel_id: int = 0
    autor_id: int = 0
    objetivo: str = ""
    fecha_entrega: datetime = datetime.now()
    estado: str = "pendiente"
    concepto_id: int = 0
    herramienta_id: int = 0
    tiempo_estimado: int = 0
    uso_ia: bool = False
    grupo_id: Optional[int] = None
    practica_id: int = 0


@dataclass
class Materia:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Nivel:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Notificacion:
    usuario_id: int
    tipo: str
    mensaje: str
    fecha_creacion: datetime

@dataclass
class Plantilla:
    nombre: str
    descripcion: str
    contenido: dict
    autor_id: int
    fecha_creacion: datetime
    categoria: str

@dataclass
class Version:
    id: int
    practica_id: int
    contenido: dict
    autor_id: int
    fecha_creacion: datetime
    numero_version: int
    cambios: str

@dataclass
class Grupo:
    id: Optional[int]
    nombre: str
    practica_id: int
    fecha_creacion: datetime
    activo: bool

@dataclass
class Entrega:
    id: Optional[int]
    practica_id: int
    estudiante_id: int
    grupo_id: Optional[int]
    contenido: str
    fecha_entrega: datetime
    estado: str
    calificacion: Optional[float]
    comentarios: Optional[str]
    evaluacion_id: Optional[int]  

@dataclass
class Usuario:
    id: Optional[int]
    nombre: str
    email: str
    rol: str

@dataclass
class Concepto:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Herramienta:
    id: int
    nombre: str
    descripcion: Optional[str]
    url: Optional[str]

class GeneradorPracticasExtendido:
    def __init__(self, config: Dict[str, str]):
        self.connection = mysql.connector.connect(**config)
        self.cursor = self.connection.cursor(dictionary=True)
        self.cache = TTLCache(maxsize=100, ttl=300)  
        self.executor = ThreadPoolExecutor()
        self.config = config
        self.modelo_ml = GeneradorPracticasML() 
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='generador_practicas.log'
        )
        self.logger = logging.getLogger('GeneradorPracticas')
    
    def crear_evaluacion_para_practica(self, practica_id: int, estudiante_id: int) -> Optional[int]:
        """Crea una evaluación solo para el estudiante seleccionado y devuelve el ID de la evaluación."""
        try:
            query_autor = "SELECT autor_id FROM practicas WHERE id = %s"
            self.cursor.execute(query_autor, (practica_id,))
            practica = self.cursor.fetchone()
    
            if not practica:
                raise ValueError("La práctica no existe.")
    
            autor_id = practica['autor_id']
    
            query_evaluacion = """
                INSERT INTO evaluaciones (practica_id, estudiante_id, evaluador_id, fecha_evaluacion, estado, calificacion, comentarios)
                VALUES (%s, %s, %s, NOW(), 'pendiente', NULL, NULL)
            """
            self.cursor.execute(query_evaluacion, (practica_id, estudiante_id, autor_id))
            self.connection.commit()
    
            evaluacion_id = self.cursor.lastrowid
            return evaluacion_id  
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear evaluación: {str(e)}")
            raise

    def obtener_semestres(self):
        """Obtiene todos los semestres de la base de datos."""
        try:
            query = "SELECT * FROM semestres"
            self.cursor.execute(query)
            return self.cursor.fetchall()  
        except Error as e:
            self.logger.error(f"Error al obtener semestres: {str(e)}")
            return []

    def obtener_estudiantes(self):
        """Obtiene todos los estudiantes de la base de datos."""
        try:
            query = "SELECT * FROM usuarios WHERE rol = 'estudiante'"  
            self.cursor.execute(query)
            return self.cursor.fetchall()  
        except Error as e:
            self.logger.error(f"Error al obtener estudiantes: {str(e)}")
            return []

    def obtener_grupo_por_id(self, grupo_id):
        """Obtiene un grupo por su ID."""
        try:
            query = "SELECT * FROM grupos WHERE id = %s"
            self.cursor.execute(query, (grupo_id,))
            return self.cursor.fetchone()  
        except Error as e:
            self.logger.error(f"Error al obtener grupo por ID: {str(e)}")
            return None

    def obtener_estudiantes_por_practica(self, practica_id):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT 
                u.id AS estudiante_id,
                u.nombre AS estudiante_nombre,
                ev.estado,
                ev.calificacion,
                ev.comentarios,
                ev.uso_ia,  -- Obtener uso_ia de la tabla evaluaciones
                e.archivos_url AS archivo_url
            FROM 
                evaluaciones ev
            JOIN 
                usuarios u ON ev.estudiante_id = u.id
            LEFT JOIN 
                entregas e ON ev.practica_id = e.practica_id AND ev.estudiante_id = e.estudiante_id
            WHERE 
                ev.practica_id = %s
        """
        cursor.execute(query, (practica_id,))
        estudiantes = cursor.fetchall()
        connection.close()
        return estudiantes

    def obtener_estudiantes_por_grupo(self, grupo_id):
        """Obtiene todos los estudiantes inscritos en un grupo."""
        try:
            query = """
            SELECT u.id, u.nombre
            FROM grupo_miembros gm
            JOIN usuarios u ON gm.usuario_id = u.id
            WHERE gm.grupo_id = %s
            """
            self.cursor.execute(query, (grupo_id,))
            return self.cursor.fetchall()  
        except Error as e:
            self.logger.error(f"Error al obtener estudiantes por grupo: {str(e)}")
            return []

    def obtener_grupo_actual(self, usuario_id):
        """Obtiene el grupo actual del usuario."""
        try:
            query = """
            SELECT g.*
            FROM grupos g
            JOIN grupo_miembros gm ON g.id = gm.grupo_id
            WHERE gm.usuario_id = %s
            LIMIT 1
            """
            self.cursor.execute(query, (usuario_id,))
            return self.cursor.fetchone() 
        except Error as e:
            self.logger.error(f"Error al obtener el grupo actual: {str(e)}")
            return None

    def obtener_grupos_con_estudiantes(self):
        """Obtiene todos los grupos y los estudiantes inscritos en cada grupo."""
        try:
            query = """
            SELECT g.id AS grupo_id, g.nombre AS grupo_nombre, g.descripcion, 
                   gm.usuario_id, u.nombre AS estudiante_nombre
            FROM grupos g
            LEFT JOIN grupo_miembros gm ON g.id = gm.grupo_id
            LEFT JOIN usuarios u ON gm.usuario_id = u.id
            """
            self.cursor.execute(query)
            resultados = self.cursor.fetchall()

            grupos = defaultdict(lambda: {"nombre": "", "descripcion": "", "estudiantes": []})
            for row in resultados:
                grupo_id = row['grupo_id']
                grupos[grupo_id]['nombre'] = row['grupo_nombre']
                grupos[grupo_id]['descripcion'] = row['descripcion']
                if row['estudiante_nombre']:
                    grupos[grupo_id]['estudiantes'].append(row['estudiante_nombre'])

            return grupos
        except Error as e:
            self.logger.error(f"Error al obtener grupos con estudiantes: {str(e)}")
            return {}

    def obtener_grupos_por_semestre(self, semestre_id):
        """Obtiene todos los grupos de la base de datos por semestre."""
        try:
            query = "SELECT * FROM grupos WHERE semestre_id = %s"
            self.cursor.execute(query, (semestre_id,))
            return self.cursor.fetchall()  
        except Error as e:
            self.logger.error(f"Error al obtener grupos por semestre: {str(e)}")
            return []

    def obtener_grupos(self):
        """Obtiene todos los grupos de la base de datos y devuelve una lista de diccionarios."""
        try:
            query = "SELECT id, nombre FROM grupos"
            self.cursor.execute(query)
            resultados = self.cursor.fetchall()

            grupos = [{"id": grupo["id"], "nombre": grupo["nombre"]} for grupo in resultados]


            return grupos
        except Error as e:
            self.logger.error(f"Error al obtener grupos: {str(e)}")
            return []


    def obtener_usuarios_por_rol(self, rol):
        """
        Obtiene los usuarios filtrados por rol.
        :param rol: Rol de los usuarios a obtener (por ejemplo, 'estudiante')
        :return: Lista de usuarios con el rol especificado
        """
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor(dictionary=True)
            query = "SELECT id, nombre, email FROM usuarios WHERE rol = %s"
            cursor.execute(query, (rol,))
            usuarios = cursor.fetchall()
            connection.close()
            return usuarios
        except Exception as e:
            print(f"Error al obtener usuarios por rol: {e}")
            return []

    def recopilar_datos_entrenamiento(self) -> Tuple[List[str], List[str], List[str]]:
        """Recopilar datos de prácticas existentes para entrenar el modelo"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return [], [], []

        query = """
        SELECT titulo, objetivo
        FROM practicas
        WHERE titulo IS NOT NULL AND objetivo IS NOT NULL
        """
        self.cursor.execute(query)
        practicas = self.cursor.fetchall()

        titulos = []
        objetivos = []
        contenidos = []

        for p in practicas:
            titulo = p['titulo'].strip().lower()
            objetivo = p['objetivo'].strip().lower()
            contenido = f"{titulo} {objetivo}".strip().lower()  
        
            titulos.append(titulo)
            objetivos.append(objetivo)
            contenidos.append(contenido)

            return titulos, objetivos, contenidos

    def registrar_usuario(self, nombre: str, email: str, password: str, rol: str = 'estudiante') -> None:
        """Registrar un nuevo usuario"""
        try:
            query = "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)"
            password_hash = hashlib.sha256(password.encode()).hexdigest()  
            self.cursor.execute(query, (nombre, email, password_hash, rol))
            self.connection.commit()
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al registrar usuario: {str(e)}")
            raise

    # def registrar_tiempo(self, usuario_id: int, tiempo: float) -> None:
    #     """Registra el tiempo que un usuario pasa en la página web."""
    #     if tiempo < 0:
    #         print("El tiempo no puede ser negativo.")
    #         return  # Evitar registrar tiempos negativos

    #     try:
    #         query = """
    #             INSERT INTO tiempo_registrado (usuario_id, tiempo, fecha)
    #             VALUES (%s, %s, NOW())
    #         """
    #         self.cursor.execute(query, (usuario_id, tiempo))
    #         self.connection.commit()
    #     except Error as e:
    #         self.connection.rollback()
    #         print(f"Error al registrar tiempo: {str(e)}")  # Agrega un print para depuración

    def autenticar_usuario(self, email: str, password: str) -> Optional[Dict]:
        """Autenticar usuario"""
        try:
            query = "SELECT id, nombre, rol, password_hash FROM usuarios WHERE email = %s"
            self.cursor.execute(query, (email,))
            usuario = self.cursor.fetchone()

            if usuario:
                password_hash = hashlib.sha256(password.encode()).hexdigest()

                print(f"Hash de la contraseña ingresada: {password_hash}")
                print(f"Hash de la contraseña almacenada: {usuario['password_hash']}")

                if password_hash == usuario['password_hash']:
                    return {
                        'id': usuario['id'],
                        'nombre': usuario['nombre'],
                        'rol': usuario['rol']
                    }

            print("Credenciales inválidas")
            return None
        except Error as e:
            self.logger.error(f"Error al autenticar usuario: {str(e)}")
            return None

    def actualizar_rol_usuario(self, usuario_id, nuevo_rol):
        """Actualiza el rol de un usuario en la base de datos."""
        try:
            query = """
            UPDATE usuarios
            SET rol = %s
            WHERE id = %s
            """
            self.cursor.execute(query, (nuevo_rol, usuario_id))
            self.connection.commit()  
            return nuevo_rol  
        except Exception as e:
            self.connection.rollback() 
            print(f"Error al actualizar rol: {str(e)}")  
            return None


    def _calcular_similitud(self, texto1: str, texto2: str) -> float:
        """Calcula la similitud entre dos textos usando SequenceMatcher"""
        return SequenceMatcher(None, texto1, texto2).ratio()

    def crear_notificacion(self, notificacion: Notificacion) -> int:
        """Crea una nueva notificación en la base de datos"""
        try:
            query = """
                INSERT INTO notificaciones (usuario_id, tipo, mensaje, fecha_creacion)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                notificacion.usuario_id,
                notificacion.tipo,
                notificacion.mensaje,
                notificacion.fecha_creacion
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear notificación: {str(e)}")
            raise

    def obtener_conceptos(self) -> List[Concepto]:
        """Obtiene todos los conceptos"""
        try:
            query = "SELECT * FROM conceptos ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            conceptos = []
            for result in results:
                concepto = Concepto(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                conceptos.append(concepto)
            return conceptos
        except Error as e:
            self.logger.error(f"Error al obtener conceptos: {str(e)}")
            return []

    def eliminar_practica(self, practica_id: int) -> bool:
        """Elimina una práctica y sus entregas y evaluaciones asociadas."""
        try:
            query_entregas = "DELETE FROM entregas WHERE practica_id = %s"
            self.cursor.execute(query_entregas, (practica_id,))

            query_evaluaciones = "DELETE FROM evaluaciones WHERE practica_id = %s"
            self.cursor.execute(query_evaluaciones, (practica_id,))

            query_practica = "DELETE FROM practicas WHERE id = %s"
            self.cursor.execute(query_practica, (practica_id,))

            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al eliminar práctica: {str(e)}")
            return False



    def obtener_herramientas(self) -> List[Herramienta]:
        """Obtiene todas las herramientas"""
        try:
            query = "SELECT * FROM herramientas ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()

            herramientas = []
            for result in results:
                herramienta = Herramienta(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result.get('descripcion'),
                    url=result.get('url')
                )
                herramientas.append(herramienta)
            return herramientas
        except Error as e:
            self.logger.error(f"Error al obtener herramientas: {str(e)}")
            return []

    def guardar_contenido_generado(self, practica_id: int, contenido: dict) -> bool:
        """Guarda el contenido generado por IA para una práctica"""
        try:
            query = """
                INSERT INTO contenido_generado (practica_id, contenido, fecha_creacion)
                VALUES (%s, %s, %s)
            """
            self.cursor.execute(query, (
                practica_id,
                json.dumps(contenido),
                datetime.now()
            ))
            self.connection.commit()
            return True
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al guardar contenido generado: {str(e)}")
            return False
    
    def obtener_contenido_generado(self, practica_id: int) -> Optional[dict]:
        """Obtiene el contenido generado por IA para una práctica"""
        try:
            query = "SELECT contenido FROM contenido_generado WHERE practica_id = %s"
            self.cursor.execute(query, (practica_id,))
            result = self.cursor.fetchone()
            if result:
                return json.loads(result['contenido'])
            return None
        except Error as e:
            self.logger.error(f"Error al obtener contenido generado: {str(e)}")
            return None 
    
    def obtener_niveles(self) -> List[Nivel]:
        """Obtiene todos los niveles"""
        try:
            query = "SELECT * FROM niveles ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            niveles = []
            for result in results:
                nivel = Nivel(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                niveles.append(nivel)
            return niveles
        except Error as e:
            self.logger.error(f"Error al obtener niveles: {str(e)}")
            return []
        
    def obtener_usuarios(self) -> List[Usuario]:
        """Obtiene todos los usuarios"""
        try:
            query = "SELECT * FROM usuarios ORDER BY rol DESC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            usuarios = []
            for result in results:
                usuario = Usuario(
                    id=result['id'],
                    nombre=result['nombre'],
                    email=result['email'],
                    rol=result['rol']
                )
                usuarios.append(usuario)
            return usuarios
        except Error as e:
            self.logger.error(f"Error al obtener usuarios: {str(e)}")
            return []
        
    def obtetener_usuarios_autorizados(self) -> List[Usuario]:
        """Obtiene todos los usuarios autorizados"""
        try:
            query = "SELECT * FROM usuarios WHERE NOT rol = 'estudiante' ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            usuarios_autorizados = []
            for result in results:
                usuario = Usuario(
                    id=result['id'],
                    nombre=result['nombre'],
                    email=result['email'],
                    rol=result['rol']
                )
                usuarios_autorizados.append(usuario)
            return usuarios_autorizados
        except Error as e:
            self.logger.error(f"Error al obtener usuarios autorizados: {str(e)}")
            return []

    def obtener_evaluaciones(self):
       """Obtiene todas las evaluaciones."""
       try:
           query = """
           SELECT e.id, e.practica_id, e.estudiante_id, e.calificacion, e.comentarios, 
                  e.estado, e.fecha_evaluacion, p.titulo as practica_titulo, u.nombre as estudiante, p.grupo_id
           FROM evaluaciones e
           JOIN practicas p ON e.practica_id = p.id
           JOIN usuarios u ON e.estudiante_id = u.id
           ORDER BY e.fecha_evaluacion DESC
           """
           self.cursor.execute(query)
           evaluaciones = self.cursor.fetchall()
           print("Evaluaciones obtenidas:", evaluaciones) 
           return evaluaciones
       except Exception as e:
           print(f"Error al obtener evaluaciones: {str(e)}")
           return []

    def obtener_actividades_recientes(self) -> List[Dict]:
        """Obtiene las actividades recientes de la base de datos."""
        try:
            query = """
                SELECT descripcion, fecha
                FROM actividades
                ORDER BY fecha DESC
                LIMIT 10
            """
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Error as e:
            self.logger.error(f"Error al obtener actividades recientes: {str(e)}")
            return []

    def evaluar_entrega(self, evaluacion_id: int, contenido: str, titulo: str, objetivo: str):
        """Genera una calificación y comentarios para una entrega y actualiza la evaluación"""
        try:
            resultado = self.modelo_ml.analizar_contenido(contenido, titulo, objetivo)
            calificacion = resultado['calificacion']
            comentarios = resultado['comentarios']

            self.actualizar_evaluacion(evaluacion_id, comentarios, calificacion)
            print(f"Evaluación {evaluacion_id} actualizada con calificación {calificacion} y comentarios.")
        except Exception as e:
            print(f"Error al evaluar entrega: {str(e)}")

    def actualizar_evaluacion(self, evaluacion_id, comentarios, calificacion):
        """
        Actualiza la evaluación con los comentarios y la calificación.
        """
        try:
            query = """
                UPDATE evaluaciones 
                SET calificacion = %s, comentarios = %s, estado = 'calificado' 
                WHERE id = %s
            """
            self.cursor.execute(query, (calificacion, comentarios, evaluacion_id))

            query_update_entrega = """
                UPDATE entregas 
                SET estado = 'calificado' 
                WHERE id = %s
            """
            self.cursor.execute(query_update_entrega, (evaluacion_id,))
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"Error al actualizar la evaluación: {str(e)}")
            raise e


    def obtener_materias(self) -> List[Materia]:
        """Obtiene todas las materias"""
        try:
            query = "SELECT * FROM materias ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            materias = []
            for result in results:
                materia = Materia(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                materias.append(materia)
            return materias
        except Error as e:
            self.logger.error(f"Error al obtener materias: {str(e)}")
            return []

    def obtener_practicas(self) -> List[Practica]:
        """Obtiene todas las prácticas con el nombre del autor."""
        try:
            query = """
                SELECT p.*, m.nombre AS nombre_materia, u.nombre AS autor_nombre, u.rol AS autor_rol
                FROM practicas p
                JOIN materias m ON p.materia_id = m.id
                JOIN usuarios u ON p.autor_id = u.id
                WHERE u.rol IN ('administrador', 'profesor')
                ORDER BY p.fecha_entrega DESC
            """
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            practicas = []
            for result in results:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nombre_materia=result['nombre_materia'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                practicas.append(practica)
            return practicas
        except Error as e:
            self.logger.error(f"Error al obtener prácticas: {str(e)}")
            return []
        
    def obtener_grupos_por_profesor(self, profesor_id):
        """Obtiene todos los grupos creados por un profesor específico."""
        try:
            query = """
            SELECT g.id, g.nombre, g.descripcion, g.materia_id, g.profesor_id, g.fecha_creacion, g.semestre_id, g.activo
            FROM grupos g
            WHERE g.profesor_id = %s
            """
            self.cursor.execute(query, (profesor_id,))
            resultados = self.cursor.fetchall() 
    
            grupos = [{"id": grupo["id"],
                       "nombre": grupo["nombre"],
                       "descripcion": grupo["descripcion"],
                       "materia_id": grupo["materia_id"],
                       "profesor_id": grupo["profesor_id"],
                       "fecha_creacion": grupo["fecha_creacion"],
                       "semestre_id": grupo["semestre_id"],
                       "activo": grupo["activo"]} for grupo in resultados]
    
            return grupos
        except Error as e:
            self.logger.error(f"Error al obtener grupos por profesor: {str(e)}")
            return []
        
    def obtener_practicas_activas(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM practicas WHERE estado = 'pendiente'")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener prácticas activas: {str(e)}")
            return 0

    def obtener_entregas_pendientes(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM entregas WHERE estado = 'pendiente'")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener entregas pendientes: {str(e)}")
            return 0
        
    def obtener_practicas_estudiante(self, estudiante_id: int) -> List[Dict]:
        """Obtiene las prácticas activas asignadas a un estudiante."""
        try:
            query = """
                SELECT p.id, p.titulo, p.fecha_entrega, p.estado, p.objetivo
                FROM practicas p
                JOIN evaluaciones e ON p.id = e.practica_id
                WHERE e.estudiante_id = %s AND p.estado = 'pendiente'
                ORDER BY p.fecha_entrega ASC
            """
            self.cursor.execute(query, (estudiante_id,))
            return self.cursor.fetchall()
        except Error as e:
            self.logger.error(f"Error al obtener prácticas del estudiante: {str(e)}")
            return []


    def obtener_usuarios_registrados(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM usuarios")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener usuarios registrados: {str(e)}")
            return 0

    def obtener_estadisticas_dashboard(self) -> Dict[str, Any]:
        """Obtiene todas las estadísticas necesarias para el dashboard"""
        try:
            cache_key = 'dashboard_stats'
            if cache_key in self.cache:
                return self.cache[cache_key]
                
            stats = {
                'practicas_activas': self.obtener_practicas_activas(),
                'entregas_pendientes': self.obtener_entregas_pendientes(),
                'usuarios_registrados': self.obtener_usuarios_registrados(),
                'materias_populares': self.obtener_materias_populares(),
                'entrega_por_estado': self.obtener_distribucion_entregas_por_estado()
            }
            
            self.cache[cache_key] = stats
            return stats
        except Error as e:
            self.logger.error(f"Error al obtener estadísticas del dashboard: {str(e)}")
            return {}
    
    def obtener_materias_populares(self, limite: int = 5) -> List[Dict[str, Any]]:
        """Obtiene las materias con más prácticas creadas"""
        try:
            query = """
                SELECT m.id, m.nombre, COUNT(p.id) AS total_practicas
                FROM materias m
                JOIN practicas p ON m.id = p.materia_id
                GROUP BY m.id, m.nombre
                ORDER BY total_practicas DESC
                LIMIT %s
            """
            self.cursor.execute(query, (limite,))
            return self.cursor.fetchall()
        except Error as e:
            self.logger.error(f"Error al obtener materias populares: {str(e)}")
            return []
    
    def obtener_entrega_desde_evaluacion(self, evaluacion_id: int) -> Optional[int]:
        """Obtiene el ID de la entrega asociada a una evaluación."""
        try:
            query = """
            SELECT e.id AS entrega_id
            FROM evaluaciones ev
            JOIN entregas e ON ev.practica_id = e.practica_id AND ev.estudiante_id = e.estudiante_id
            WHERE ev.id = %s
            """
            self.cursor.execute(query, (evaluacion_id,))
            result = self.cursor.fetchone()
            return result['entrega_id'] if result else None
        except mysql.connector.Error as e:
            self.logger.error(f"Error al obtener entrega desde evaluación: {str(e)}")
            return None

    def obtener_distribucion_entregas_por_estado(self) -> Dict[str, int]:
        """Obtiene la distribución de entregas por estado"""
        try:
            query = """
                SELECT estado, COUNT(*) as cantidad
                FROM entregas
                GROUP BY estado
            """
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            return {row['estado']: row['cantidad'] for row in result}
        except Error as e:
            self.logger.error(f"Error al obtener distribución de entregas: {str(e)}")
            return {}
    
    async def crear_practica_async(self, practica: Practica) -> Optional[int]:
        """Crea una nueva práctica de forma asíncrona"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.crear_practica, practica)

    def obtener_entrega_por_id(self, entrega_id: int, es_evaluacion: bool = False) -> Optional[Dict]:
        try:
            if es_evaluacion:
                entrega_id = self.obtener_entrega_desde_evaluacion(entrega_id)
                if not entrega_id:
                    print(f"No se encontró una entrega asociada a la evaluación con ID: {entrega_id}")
                    return None

            print(f"Buscando entrega con ID: {entrega_id}")  
            query = """
            SELECT e.id AS entrega_id, 
                   e.practica_id, 
                   e.estudiante_id, 
                   e.fecha_entrega, 
                   e.estado, 
                   e.archivos_url, 
                   e.contenido, 
                   e.calificacion,
                   p.titulo AS practica_titulo, 
                   p.objetivo AS practica_objetivo
            FROM entregas e
            JOIN practicas p ON e.practica_id = p.id
            WHERE e.id = %s
            """
            self.cursor.execute(query, (entrega_id,))
            entrega = self.cursor.fetchone()
            print(f"Resultado de la consulta de entrega: {entrega}")  
            return entrega
        except mysql.connector.Error as e:
            print(f"Error al obtener entrega: {str(e)}")
            return None
    
    def obtener_entrega_desde_evaluacion(self, evaluacion_id: int) -> Optional[int]:
        """Obtiene el ID de la entrega asociada a una evaluación."""
        try:
            print(f"Buscando entrega asociada a la evaluación con ID: {evaluacion_id}") 
            query = """
            SELECT ev.id AS entrega_id
            FROM evaluaciones ev
            JOIN entregas e ON ev.practica_id = e.practica_id AND ev.estudiante_id = e.estudiante_id
            WHERE ev.id = %s
            """
            self.cursor.execute(query, (evaluacion_id,))
            result = self.cursor.fetchone()
            print(f"Resultado de obtener_entrega_desde_evaluacion: {result}")  
            return result['entrega_id'] if result else None
        except mysql.connector.Error as e:
            print(f"Error al obtener entrega desde evaluación: {str(e)}")
            return None

    def crear_practica(self, practica: Practica):
        try:
            query = """
            INSERT INTO practicas (titulo, materia_id, nivel_id, autor_id, objetivo, fecha_entrega, tiempo_estimado, concepto_id, herramienta_id, uso_ia, grupo_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                practica.titulo,
                practica.materia_id,
                practica.nivel_id,
                practica.autor_id,
                practica.objetivo,
                practica.fecha_entrega,
                practica.tiempo_estimado,
                practica.concepto_id,
                practica.herramienta_id,
                practica.uso_ia,
                practica.grupo_id
            )
            self.cursor.execute(query, values)
            self.connection.commit()
    
            practica_id = self.cursor.lastrowid
            print(f"Práctica creada con ID: {practica_id}")  
    
            self.crear_evaluaciones_para_practica(practica_id, practica.autor_id, practica.uso_ia)
    
            return practica_id
        except Exception as e:
            self.connection.rollback()
            print(f"Error al crear práctica: {str(e)}")
            raise e

    def crear_evaluaciones_para_practica(self, practica_id: int, autor_id: int, uso_ia: bool = False) -> None:
        """Crea evaluaciones automáticamente para todos los estudiantes."""
        try:
            query_estudiantes = "SELECT id FROM usuarios WHERE rol = 'estudiante'"
            self.cursor.execute(query_estudiantes)
            estudiantes = self.cursor.fetchall()

            if not estudiantes:
                print("No se encontraron estudiantes para crear evaluaciones.")
                return

            for estudiante in estudiantes:
                estudiante_id = estudiante['id']
                query_insert = """
                INSERT INTO evaluaciones (practica_id, estudiante_id, evaluador_id, fecha_evaluacion, estado, calificacion, comentarios, uso_ia)
                VALUES (%s, %s, %s, NOW(), 'pendiente', NULL, NULL, %s)
                """
                self.cursor.execute(query_insert, (practica_id, estudiante_id, autor_id, 1 if uso_ia else 0))
                print(f"Evaluación creada para estudiante ID: {estudiante_id}") 

            self.connection.commit()
            print("Evaluaciones creadas exitosamente.")
        except Exception as e:
            self.connection.rollback()
            print(f"Error al crear evaluaciones: {str(e)}")
            raise e
    
    def actualizar_calificacion_entrega(self, evaluacion_id: int, estudiante_id: int) -> bool:
        """
        Actualiza la calificación de la entrega correspondiente a una evaluación.
    
        Args:
            evaluacion_id: ID de la evaluación de la que se obtendrá la calificación.
            estudiante_id: ID del estudiante cuya entrega se actualizará.
    
        Returns:
            True si la actualización fue exitosa, False en caso contrario.
        """
        try:
            query_calificacion = "SELECT calificacion FROM evaluaciones WHERE id = %s"
            self.cursor.execute(query_calificacion, (evaluacion_id,))
            resultado_calificacion = self.cursor.fetchone()
    
            if resultado_calificacion:
                calificacion = resultado_calificacion['calificacion']
    
                query_actualizar = """
                    UPDATE entregas
                    SET calificacion = %s
                    WHERE estudiante_id = %s AND evaluacion_id = %s
                """
                self.cursor.execute(query_actualizar, (calificacion, estudiante_id, evaluacion_id))
                self.connection.commit()
    
                print(f"Calificación actualizada a {calificacion} para el estudiante ID: {estudiante_id}.")
                return True
            else:
                print(f"No se encontró la calificación para la evaluación ID: {evaluacion_id}.")
                return False
    
        except Exception as e:
            self.connection.rollback()
            print(f"Error al actualizar la calificación de la entrega: {str(e)}")
            return False
        
    def actualizar_practica(self, practica: Practica) -> bool:
        """Actualiza una práctica existente"""
        try:
            query = """
                UPDATE practicas 
                SET titulo = %s, materia_id = %s, nivel_id = %s, objetivo = %s,
                fecha_entrega = %s, estado = %s, concepto_id = %s, 
                herramienta_id = %s, tiempo_estimado = %s
                WHERE id = %s
            """
            self.cursor.execute(query, (
                practica.titulo,
                practica.materia_id,
                practica.nivel_id,
                practica.objetivo,
                practica.fecha_entrega,
                practica.estado,
                practica.concepto_id,
                practica.herramienta_id,
                practica.tiempo_estimado,
                practica.id
            ))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al actualizar práctica: {str(e)}")
            return False
    
    def obtener_practica_por_id(self, practica_id: int) -> Optional[Practica]:
        """Obtiene una práctica por su ID"""
        try:
            cache_key = f'practica_{practica_id}'
            if cache_key in self.cache:
                return self.cache[cache_key]

            query = """
                SELECT practicas.*, materias.nombre 
                FROM practicas 
                JOIN materias ON practicas.materia_id = materias.id 
                WHERE practicas.id = %s
            """
            self.cursor.execute(query, (practica_id,))
            result = self.cursor.fetchone()

            if result:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nombre_materia=result['nombre'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                self.cache[cache_key] = practica
                return practica
            return None
        except Error as e:
            self.logger.error(f"Error al obtener práctica: {str(e)}")
            return None
    
    def obtener_practicas_por_grupo(self, grupo_id: int) -> int:
        """Obtiene el número total de prácticas para un grupo específico."""
        try:
            query = "SELECT COUNT(*) AS total FROM practicas WHERE grupo_id = %s"
            self.cursor.execute(query, (grupo_id,))
            result = self.cursor.fetchone()
            return result['total'] if result else 0
        except Error as e:
            self.logger.error(f"Error al obtener prácticas por grupo: {str(e)}")
            return 0

    def obtener_practicas_por_autor(self, autor_id: int) -> List[Practica]:
        """Obtiene todas las prácticas creadas por un autor"""
        try:
            query = "SELECT * FROM practicas WHERE autor_id = %s ORDER BY fecha_entrega DESC"
            self.cursor.execute(query, (autor_id,))
            results = self.cursor.fetchall()
            
            practicas = []
            for result in results:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                practicas.append(practica)
            return practicas
        except Error as e:
            self.logger.error(f"Error al obtener prácticas por autor: {str(e)}")
            return []
    
    def crear_grupo(self, grupo: Grupo) -> Optional[int]:
        """Crea un nuevo grupo para una práctica"""
        try:
            query = """
                INSERT INTO grupos (nombre, practica_id, fecha_creacion, activo)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                grupo.nombre,
                grupo.practica_id,
                grupo.fecha_creacion,
                grupo.activo
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear grupo: {str(e)}")
            return None
    
    def obtener_materia_por_id(self, materia_id):
        """Obtiene una materia de la base de datos por su ID."""
        try:
            query = "SELECT * FROM materias WHERE id = %s"
            self.cursor.execute(query, (materia_id,))
            return self.cursor.fetchone()  
        except Error as e:
            self.logger.error(f"Error al obtener materia por ID: {str(e)}")
            return None
    
    def calificar_entrega(self, entrega_id: int, calificacion: float, comentarios: str) -> bool:
        """Califica una entrega de práctica"""
        try:
            query = """
                UPDATE entregas 
                SET calificacion = %s, comentarios = %s, estado = 'calificado'
                WHERE id = %s
            """
            self.cursor.execute(query, (calificacion, comentarios, entrega_id))
            self.connection.commit()
            
            self.cursor.execute("SELECT estudiante_id, practica_id FROM entregas WHERE id = %s", (entrega_id,))
            entrega_info = self.cursor.fetchone()
            
            if entrega_info:
                practica = self.obtener_practica_por_id(entrega_info['practica_id'])
                if practica:
                    notificacion = Notificacion(
                        usuario_id=entrega_info['estudiante_id'],
                        tipo="entrega_calificada",
                        mensaje=f"Tu entrega para '{practica.titulo}' ha sido calificada",
                        fecha_creacion=datetime.now()
                    )
                    self.crear_notificacion(notificacion)
            
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al calificar entrega: {str(e)}")
            return False
    
    def guardar_plantilla(self, plantilla: Plantilla) -> Optional[int]:
        """Guarda una nueva plantilla de práctica"""
        try:
            query = """
                INSERT INTO plantillas 
                (nombre, descripcion, contenido, autor_id, fecha_creacion, categoria)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                plantilla.nombre,
                plantilla.descripcion,
                json.dumps(plantilla.contenido),
                plantilla.autor_id,
                plantilla.fecha_creacion,
                plantilla.categoria
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al guardar plantilla: {str(e)}")
            return None
    
    def crear_version(self, version: Version) -> Optional[int]:
        """Crea una nueva versión de una práctica"""
        try:
            query = """
                INSERT INTO versiones 
                (practica_id, contenido, autor_id, fecha_creacion, numero_version, cambios)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                version.practica_id,
                json.dumps(version.contenido),
                version.autor_id,
                version.fecha_creacion,
                version.numero_version,
                version.cambios
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear versión: {str(e)}")
            return None
    
    def obtener_versiones_practica(self, practica_id: int) -> List[Version]:
        """Obtiene todas las versiones de una práctica"""
        try:
            query = """
                SELECT * FROM versiones 
                WHERE practica_id = %s
                ORDER BY numero_version DESC
            """
            self.cursor.execute(query, (practica_id,))
            results = self.cursor.fetchall()
            
            versiones = []
            for result in results:
                version = Version(
                    id=result['id'],
                    practica_id=result['practica_id'],
                    contenido=json.loads(result['contenido']),
                    autor_id=result['autor_id'],
                    fecha_creacion=result['fecha_creacion'],
                    numero_version=result['numero_version'],
                    cambios=result['cambios']
                )
                versiones.append(version)
            return versiones
        except Error as e:
            self.logger.error(f"Error al obtener versiones: {str(e)}")
            return []

    def obtener_estudiante_por_id(self, estudiante_id: int) -> Dict:
        """Obtiene los datos de un estudiante por su ID."""
        try:
            query = """
            SELECT id, nombre, email, rol
            FROM usuarios
            WHERE id = %s
            """
            self.cursor.execute(query, (estudiante_id,))
            estudiante = self.cursor.fetchone()
            if estudiante:
                return estudiante
            else:
                raise ValueError(f"No se encontró un estudiante con ID {estudiante_id}")
        except Exception as e:
            print(f"Error al obtener estudiante por ID: {str(e)}")
            return {}

    def obtener_evaluaciones_pendientes(self, estudiante_id: int) -> List[Dict]:
        """Obtiene las evaluaciones pendientes de un estudiante."""
        try:
            query = """
            SELECT e.id, e.practica_id, e.estudiante_id, e.estado, e.fecha_evaluacion, 
                   p.titulo AS practica_titulo
            FROM evaluaciones e
            JOIN practicas p ON e.practica_id = p.id
            WHERE e.estudiante_id = %s AND e.estado = 'pendiente'
            ORDER BY e.fecha_evaluacion ASC
            """
            self.cursor.execute(query, (estudiante_id,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener evaluaciones pendientes: {str(e)}")
            return []
        
    def actualizar_estado_entrega(self, entrega_id: int, nuevo_estado: str) -> bool:
        """
        Actualiza el estado de una entrega en la base de datos.
        
        Args:
            entrega_id (int): ID de la entrega a actualizar.
            nuevo_estado (str): Nuevo estado para la entrega (e.g., 'pendiente', 'calificado').
        
        Returns:
            bool: True si la actualización fue exitosa, False en caso contrario.
        """
        try:
            query = "UPDATE entregas SET estado = %s WHERE id = %s"
            self.cursor.execute(query, (nuevo_estado, entrega_id))
            self.connection.commit()
            if self.cursor.rowcount > 0:
                print(f"Estado de la entrega {entrega_id} actualizado a '{nuevo_estado}'.")
                return True
            else:
                print(f"No se encontró la entrega con ID {entrega_id} para actualizar.")
                return False
        except Exception as e:
            self.connection.rollback()
            print(f"Error al actualizar estado de entrega {entrega_id}: {str(e)}")
            return False

    def obtener_evaluacion_por_id(self, evaluacion_id):
        """Obtiene una evaluación específica por su ID."""
        try:
            query = """
            SELECT e.id, e.practica_id, e.estudiante_id, e.calificacion, e.comentarios, 
                   e.estado, e.fecha_evaluacion, p.titulo as practica_titulo
            FROM evaluaciones e
            JOIN practicas p ON e.practica_id = p.id
            WHERE e.id = %s
            """
            self.cursor.execute(query, (evaluacion_id,))
            evaluacion = self.cursor.fetchone()
            return evaluacion
        except Exception as e:
            print(f"Error al obtener evaluación por ID: {str(e)}")
            return None

    def obtener_entrega_desde_evaluacion(self, evaluacion_id: int) -> Optional[int]:
        """Obtiene el ID de la entrega asociada a una evaluación."""
        try:
            print(f"Buscando entrega asociada a la evaluación con ID: {evaluacion_id}") 
            query = """
            SELECT e.id AS entrega_id
            FROM entregas e
            JOIN evaluaciones ev ON ev.practica_id = e.practica_id AND ev.estudiante_id = e.estudiante_id
            WHERE ev.id = %s
            """
            self.cursor.execute(query, (evaluacion_id,))
            result = self.cursor.fetchone()
            print(f"Resultado de obtener_entrega_desde_evaluacion: {result}")  
            return result['entrega_id'] if result else None
        except mysql.connector.Error as e:
            print(f"Error al obtener entrega desde evaluación: {str(e)}")
            return None

    def obtener_entrega_por_evaluacion(self, evaluacion_id):
        """Obtiene la entrega relacionada con una evaluación."""
        try:
            print(f"Buscando entrega para evaluación ID: {evaluacion_id}")

            entrega_id = self.obtener_entrega_desde_evaluacion(evaluacion_id)

            if entrega_id:
                query = """
                SELECT id, practica_id, estudiante_id, fecha_entrega, estado, 
                       archivos_url, contenido, evaluacion_id
                FROM entregas
                WHERE id = %s
                """
                self.cursor.execute(query, (entrega_id,))
                entrega = self.cursor.fetchone()
                print(f"Entrega encontrada con ID: {entrega_id}")
                return entrega

            query_eval = """
            SELECT practica_id, estudiante_id FROM evaluaciones WHERE id = %s
            """
            self.cursor.execute(query_eval, (evaluacion_id,))
            eval_data = self.cursor.fetchone()

            if not eval_data:
                print(f"No se encontró evaluación con ID: {evaluacion_id}")
                return None

            print(f"Datos de evaluación encontrados: practica_id={eval_data['practica_id']}, estudiante_id={eval_data['estudiante_id']}")

            query = """
            SELECT id, practica_id, estudiante_id, fecha_entrega, estado, 
                   archivos_url, contenido, evaluacion_id
            FROM entregas
            WHERE practica_id = %s AND estudiante_id = %s
            ORDER BY fecha_entrega DESC
            LIMIT 1
            """
            self.cursor.execute(query, (eval_data['practica_id'], eval_data['estudiante_id']))
            entrega = self.cursor.fetchone()

            if entrega:
                print(f"Entrega encontrada con ID: {entrega['id']}")

                if not entrega.get('evaluacion_id'):
                    update_query = """
                    UPDATE entregas SET evaluacion_id = %s WHERE id = %s
                    """
                    self.cursor.execute(update_query, (evaluacion_id, entrega['id']))
                    self.connection.commit()
                    print(f"Actualizada entrega {entrega['id']} con evaluacion_id {evaluacion_id}")
            else:
                print(f"No se encontró entrega para practica_id={eval_data['practica_id']}, estudiante_id={eval_data['estudiante_id']}")

            return entrega
        except Exception as e:
            print(f"Error al obtener entrega por evaluación: {str(e)}")
            return None

    def registrar_entrega(self, entrega: Dict[str, Any]) -> Optional[int]:
        """
        Registra una nueva entrega en la base de datos.

        Args:
            entrega: Diccionario con los datos de la entrega

        Returns:
            ID de la entrega registrada
        """
        try:
            query_check = """
            SELECT id FROM entregas 
            WHERE practica_id = %s AND estudiante_id = %s
            """
            self.cursor.execute(query_check, (entrega['practica_id'], entrega['estudiante_id']))
            existing_entrega = self.cursor.fetchone()

            query_eval = """
            SELECT id FROM evaluaciones
            WHERE practica_id = %s AND estudiante_id = %s
            """
            self.cursor.execute(query_eval, (entrega['practica_id'], entrega['estudiante_id']))
            eval_result = self.cursor.fetchone()
            evaluacion_id = eval_result['id'] if eval_result else None

            if existing_entrega:
                query = """
                UPDATE entregas 
                SET fecha_entrega = %s, estado = %s, archivos_url = %s, contenido = %s, evaluacion_id = %s
                WHERE id = %s
                """
                self.cursor.execute(query, (
                    entrega['fecha_entrega'],
                    entrega['estado'],
                    entrega['archivos_url'],
                    entrega['contenido'],
                    evaluacion_id,
                    existing_entrega['id']
                ))
                self.connection.commit()
                print(f"Entrega actualizada con ID: {existing_entrega['id']}, evaluacion_id: {evaluacion_id}")
                return existing_entrega['id']
            else:
                query = """
                INSERT INTO entregas (practica_id, estudiante_id, fecha_entrega, estado, archivos_url, contenido, evaluacion_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(query, (
                    entrega['practica_id'],
                    entrega['estudiante_id'],
                    entrega['fecha_entrega'],
                    entrega['estado'],
                    entrega['archivos_url'],
                    entrega['contenido'],
                    evaluacion_id
                ))
                self.connection.commit()
                entrega_id = self.cursor.lastrowid
                print(f"Nueva entrega registrada con ID: {entrega_id}, evaluacion_id: {evaluacion_id}")
                return entrega_id
        except Exception as e:
            self.connection.rollback()
            print(f"Error al registrar entrega: {str(e)}")
            raise e

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

    def obtener_nombre_clase_por_practica(self, practica_id: int) -> Optional[str]:
        """Obtiene el nombre de la clase asociado a una práctica dada su ID."""
        try:
            query = """
            SELECT g.nombre AS nombre_clase
            FROM practicas p
            JOIN grupos g ON p.grupo_id = g.id
            WHERE p.id = %s
            """
            self.cursor.execute(query, (practica_id))
            result = self.cursor.fetchone()
            return result['nombre_clase'] if result else None
        except Error as e:
            self.logger.error(f"Error al obtener el nombre de la clase por práctica: {str(e)}")
            return None

    def limpiar_cache(self):
        """Limpia la caché de objetos"""
        self.cache.clear()
    
    def cerrar_conexion(self):
        if self.cursor:
            try:
                self.cursor.close()
            except ReferenceError:
                pass
        if self.connection:  # Cambiado de self.conn a self.connection
            try:
                self.connection.close()
            except ReferenceError:
                pass

    def __del__(self):
        self.cerrar_conexion()