import os
import json
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np


import mysql.connector
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader


class TextDataset(Dataset):
    def __init__(self, entradas, salidas, tokenizer):
        self.entradas = entradas
        self.salidas = salidas
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.entradas)

    def __getitem__(self, idx):
        entrada = self.tokenizer.encode(self.entradas[idx], max_length=100)
        salida = self.tokenizer.text_to_matrix(self.salidas[idx])
        return torch.tensor(entrada), torch.tensor(salida, dtype=torch.float)


class SimpleTokenizer:
    def __init__(self, num_words=5000):
        self.num_words = num_words
        self.word_index = {}
        self.index_word = {}
        self.word_counts = {}
        self.max_length = 100

    def fit_on_texts(self, texts):
        word_counts = {}
        for text in texts:
            for word in text.lower().split():
                if word in word_counts:
                    word_counts[word] += 1
                else:
                    word_counts[word] = 1

        sorted_words = sorted(word_counts.items(),
                              key=lambda x: x[1], reverse=True)
        self.word_counts = word_counts

        self.word_index = {"<PAD>": 0}
        self.index_word = {0: "<PAD>"}

        for i, (word, _) in enumerate(sorted_words[:self.num_words - 1], 1):
            self.word_index[word] = i
            self.index_word[i] = word

    def texts_to_sequences(self, texts):
        sequences = []
        for text in texts:
            seq = []
            for word in text.lower().split():
                if word in self.word_index:
                    seq.append(self.word_index[word])
            sequences.append(seq)
        return sequences

    def encode(self, text, max_length=None):
        seq = self.texts_to_sequences([text])[0]
        if max_length:
            # Padding
            if len(seq) < max_length:
                seq = seq + [0] * (max_length - len(seq))
            else:
                seq = seq[:max_length]
        return seq

    def text_to_matrix(self, text, mode='count'):
        matrix = [0] * self.num_words
        for word in text.lower().split():
            if word in self.word_index:
                idx = self.word_index[word]
                if idx < self.num_words:
                    matrix[idx] += 1
        return matrix

    def to_json(self):
        return json.dumps({
            "word_index": self.word_index,
            "index_word": {str(k): v for k, v in self.index_word.items()},
            "word_counts": self.word_counts,
            "num_words": self.num_words
        })

    def from_json(self, json_string):
        data = json.loads(json_string)
        self.word_index = data["word_index"]
        self.index_word = {int(k): v for k, v in data["index_word"].items()}
        self.word_counts = data["word_counts"]
        self.num_words = data["num_words"]


class PracticaGenerator(nn.Module):
    def __init__(self, vocab_size=5000, embed_dim=128, hidden_dim=256, output_dim=500):
        super(PracticaGenerator, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.lstm1 = nn.LSTM(embed_dim, hidden_dim, batch_first=True)
        self.dropout1 = nn.Dropout(0.2)
        self.lstm2 = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
        self.dropout2 = nn.Dropout(0.2)
        self.fc1 = nn.Linear(hidden_dim, 512)
        self.fc2 = nn.Linear(512, 1024)
        self.fc3 = nn.Linear(1024, output_dim)
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax(dim=1)

    def forward(self, x):
        x = self.embedding(x)
        x, _ = self.lstm1(x)
        x = self.dropout1(x)
        x, _ = self.lstm2(x[:, -1, :].unsqueeze(1))
        x = self.dropout2(x)
        x = x.squeeze(1)
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        x = self.softmax(self.fc3(x))
        return x


class GeneradorPracticasML:
    def __init__(self, model_path: str = 'modelo_practicas_pytorch.pt'):
        self.model_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(self.model_dir, model_path)
        self.tokenizer_path = os.path.join(
            self.model_dir, 'tokenizer_pytorch.json')
        self.max_length = 100
        self.vocab_size = 5000
        self.device = torch.device(
            'cuda' if torch.cuda.is_available() else 'cpu')

        if os.path.exists(self.model_path) and os.path.exists(self.tokenizer_path):
            try:
                self.model = PracticaGenerator(vocab_size=self.vocab_size)
                self.model.load_state_dict(torch.load(
                    self.model_path, map_location=self.device))
                self.model.to(self.device)
                self.model.eval()

                # Cargar tokenizer
                with open(self.tokenizer_path, 'r') as f:
                    tokenizer_data = f.read()
                    self.tokenizer = SimpleTokenizer()
                    self.tokenizer.from_json(tokenizer_data)
            except Exception as e:
                print(f"Error al cargar el modelo: {e}")
                self._crear_modelo()
        else:
            # Crear modelo nuevo
            self._crear_modelo()

    def _crear_modelo(self):
        """Crea un modelo simple de red neuronal para generación de texto"""
        self.tokenizer = SimpleTokenizer(num_words=self.vocab_size)

        self.model = PracticaGenerator(vocab_size=self.vocab_size)
        self.model.to(self.device)

        self.guardar_modelo()

    def entrenar_modelo(self, titulos: List[str], objetivos: List[str], contenidos: List[str], epochs: int = 50):
        """Entrena el modelo con datos existentes de prácticas"""
        entradas = [f"{titulo} | {objetivo}" for titulo,
                    objetivo in zip(titulos, objetivos)]

        self.tokenizer.fit_on_texts(entradas + contenidos)

        dataset = TextDataset(entradas, contenidos, self.tokenizer)
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

        optimizer = optim.Adam(self.model.parameters())
        criterion = nn.CrossEntropyLoss()

        self.model.train()

        for epoch in range(epochs):
            total_loss = 0
            for batch_idx, (inputs, targets) in enumerate(dataloader):
                inputs, targets = inputs.to(
                    self.device), targets.to(self.device)

                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, targets)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

            print(
                f'Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}')

        self.guardar_modelo()

    def generar_practica(self, titulo: str, objetivo: str) -> Dict[str, Any]:
        """Genera contenido de práctica basado en título y objetivo"""
        entrada = f"{titulo} | {objetivo}"

        seq = torch.tensor(self.tokenizer.encode(
            entrada, max_length=self.max_length)).unsqueeze(0)
        seq = seq.to(self.device)

        self.model.eval()
        with torch.no_grad():
            pred = self.model(seq).cpu().numpy()[0]

        # Determinar palabras más probables
        indices = np.argsort(pred)[-50:]  # Top 50 palabras más probables

        # Construir contenido simplificado basado en predicciones
        palabras = []
        for idx in reversed(indices):
            if idx > 0 and idx < len(self.tokenizer.index_word):
                palabras.append(self.tokenizer.index_word[idx])

        # Si no tenemos suficientes palabras (por ejemplo, con modelo no entrenado),
        # usamos algunas palabras genéricas relacionadas con educación
        if len(palabras) < 30:
            palabras_genéricas = [
                "aprendizaje", "investigación", "análisis", "proyecto", "desarrollo",
                "evaluación", "competencias", "objetivos", "metodología", "resultados",
                "conocimiento", "habilidades", "comprensión", "aplicación", "práctica",
                "teoría", "concepto", "implementación", "estrategia", "tecnología",
                "innovación", "desafío", "solución", "proceso", "sistema",
                "colaboración", "diseño", "planificación", "herramientas", "recursos"
            ]
            random.shuffle(palabras_genéricas)
            palabras.extend(palabras_genéricas[:30-len(palabras)])

        # Generar una estructura de práctica
        practica_generada = {
            "titulo": titulo,
            "objetivo": objetivo,
            "introduccion": f"Esta práctica se enfoca en {' '.join(palabras[:5])}",
            "descripcion": f"A través de esta actividad, exploraremos {' '.join(palabras[5:15])}",
            "actividades": [
                f"Actividad 1: Investigar sobre {' '.join(palabras[15:20])}",
                f"Actividad 2: Desarrollar un proyecto relacionado con {' '.join(palabras[20:25])}",
                f"Actividad 3: Presentar los resultados enfocándose en {' '.join(palabras[25:30])}"
            ],
            "recursos": [
                "Libros de texto especializados",
                "Recursos en línea",
                "Herramientas de software relevantes"
            ],
            "evaluacion": {
                "criterios": [
                    "Comprensión del tema",
                    "Aplicación práctica de conceptos",
                    "Calidad de la presentación"
                ],
                "ponderacion": {
                    "participacion": 20,
                    "actividades": 50,
                    "proyecto_final": 30
                }
            },
            "tiempo_estimado": "2 semanas"
        }

        return practica_generada

    def guardar_modelo(self):
        """Guarda el modelo y el tokenizer"""
        try:
            torch.save(self.model.state_dict(), self.model_path)

            # Guardar tokenizer
            with open(self.tokenizer_path, 'w') as f:
                f.write(self.tokenizer.to_json())
            print(f"Modelo guardado exitosamente en {self.model_path}")
        except Exception as e:
            print(f"Error al guardar el modelo: {e}")


class GeneradorPracticasDB:
    def __init__(self, host="localhost", user="tu_usuario", password="tu_password", database="generador_practicas"):
        try:
            self.connection = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            self.generador_ml = GeneradorPracticasML()
        except mysql.connector.Error as err:
            print(f"Error al conectar a MySQL: {err}")
            # Inicializar el generador ML aunque la BD no esté disponible
            self.generador_ml = GeneradorPracticasML()
            self.connection = None
            self.cursor = None

    def generar_comentarios_y_calificacion(self, titulo: str, contenido: str) -> Dict[str, Any]:
        """Genera calificación y comentarios para una entrega."""
        entrada = f"{titulo} | {contenido}"
        seq = torch.tensor(self.tokenizer.encode(entrada, max_length=self.max_length)).unsqueeze(0)
        seq = seq.to(self.device)

        self.model.eval()
        with torch.no_grad():
            pred = self.model(seq).cpu().numpy()[0]

        # Calcular calificación como promedio ponderado
        calificacion = np.dot(pred, np.arange(len(pred))) / len(pred)

        # Generar comentarios basados en las palabras más probables
        indices = np.argsort(pred)[-5:]  # Top 5 palabras más probables
        comentarios = " ".join([self.tokenizer.index_word[idx] for idx in reversed(indices) if idx in self.tokenizer.index_word])

        return {
            "calificacion": round(calificacion, 2),
            "comentarios": comentarios
        }

    def generar_comentarios_y_calificacion(self, titulo: str, contenido: str) -> Dict[str, Any]:
        """Genera calificación y comentarios para una entrega."""
        entrada = f"{titulo} | {contenido}"
        seq = torch.tensor(self.tokenizer.encode(entrada, max_length=self.max_length)).unsqueeze(0)
        seq = seq.to(self.device)

        self.model.eval()
        with torch.no_grad():
            pred = self.model(seq).cpu().numpy()[0]

        # Calcular calificación como promedio ponderado
        calificacion = np.dot(pred, np.arange(len(pred))) / len(pred)

        # Generar comentarios basados en las palabras más probables
        indices = np.argsort(pred)[-5:]  # Top 5 palabras más probables
        comentarios = " ".join([self.tokenizer.index_word[idx] for idx in reversed(indices) if idx in self.tokenizer.index_word])

        return {
            "calificacion": round(calificacion, 2),
            "comentarios": comentarios
        }

    def login_usuario(self, email: str, password: str) -> Optional[Dict]:
        """Autenticar usuario"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return None

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        query = "SELECT id, nombre, rol FROM usuarios WHERE email = %s AND password_hash = %s"
        self.cursor.execute(query, (email, password_hash))
        return self.cursor.fetchone()

    def crear_usuario(self, nombre: str, email: str, password: str, rol: str) -> int:
        """Crear nuevo usuario"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return -1

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        query = """
        INSERT INTO usuarios (nombre, email, password_hash, rol)
        VALUES (%s, %s, %s, %s)
        """
        self.cursor.execute(query, (nombre, email, password_hash, rol))
        self.connection.commit()
        return self.cursor.lastrowid

    def obtener_competencias_materia(self, materia_id: int) -> List[Dict]:
        """Obtener competencias asociadas a una materia"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return []

        query = """
        SELECT DISTINCT c.* FROM competencias c
        JOIN practica_competencia pc ON c.id = pc.competencia_id
        JOIN practicas p ON pc.practica_id = p.id
        WHERE p.materia_id = %s
        """
        self.cursor.execute(query, (materia_id,))
        return self.cursor.fetchall()

    def generar_practica_ml(self, titulo: str, objetivo: str, materia_id: int, nivel_id: int,
                            autor_id: int, competencias: List[Dict],
                            tiempo_estimado: int) -> Dict[str, Any]:
        """
        Genera una práctica combinando el modelo ML y almacenándola en la BD
        """
        # 1. Generar el contenido con el modelo de ML
        contenido_ml = self.generador_ml.generar_practica(titulo, objetivo)

        # 2. Almacenar en la BD si está disponible
        practica_id = -1
        if self.connection:
            try:
                # Obtener concepto y herramienta aleatorios
                concepto_id = self._obtener_concepto_aleatorio(materia_id)
                herramienta_id = self._obtener_herramienta_aleatoria()

                # Calcular fecha de entrega
                fecha_entrega = datetime.now() + timedelta(days=14)

                # Insertar práctica
                query = """
                INSERT INTO practicas (titulo, materia_id, nivel_id, autor_id, 
                                    concepto_id, herramienta_id, objetivo, 
                                    fecha_entrega, tiempo_estimado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                self.cursor.execute(query, (
                    titulo, materia_id, nivel_id, autor_id, concepto_id,
                    herramienta_id, objetivo, fecha_entrega, tiempo_estimado
                ))
                practica_id = self.cursor.lastrowid

                # Asociar competencias
                self._asociar_competencias(practica_id, competencias)

                # Generar rúbrica basada en la evaluación del ML
                self._generar_rubrica_ml(
                    practica_id, nivel_id, contenido_ml["evaluacion"]["criterios"])

                # Generar recursos basados en los recursos ML
                self._generar_recursos_ml(
                    practica_id, contenido_ml["recursos"])

                self.connection.commit()
            except Exception as e:
                if self.connection:
                    self.connection.rollback()
                print(f"Error al guardar en BD: {e}")

        # Enriquecer el contenido ML con ID de BD si está disponible
        if practica_id > 0:
            contenido_ml["id_bd"] = practica_id

        return contenido_ml

    def generar_practica(self, titulo: str, materia_id: int, nivel_id: int,
                         autor_id: int, competencias: List[Dict],
                         tiempo_estimado: int, objetivo: str) -> int:
        """Generar una nueva práctica (método original)"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return -1

        try:
            # Obtener concepto y herramienta aleatorios
            concepto_id = self._obtener_concepto_aleatorio(materia_id)
            herramienta_id = self._obtener_herramienta_aleatoria()

            # Calcular fecha de entrega (2 semanas por defecto)
            fecha_entrega = datetime.now() + timedelta(days=14)

            # Insertar práctica
            query = """
            INSERT INTO practicas (titulo, materia_id, nivel_id, autor_id, 
                                 concepto_id, herramienta_id, objetivo, 
                                 fecha_entrega, tiempo_estimado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                titulo, materia_id, nivel_id, autor_id, concepto_id,
                herramienta_id, objetivo, fecha_entrega, tiempo_estimado
            ))
            practica_id = self.cursor.lastrowid

            # Asociar competencias
            self._asociar_competencias(practica_id, competencias)

            # Generar rúbrica
            self._generar_rubrica(practica_id, nivel_id)

            # Generar recursos
            self._generar_recursos(practica_id)

            self.connection.commit()
            return practica_id

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            raise e

    def _obtener_concepto_aleatorio(self, materia_id: int) -> Optional[int]:
        """Obtener un concepto aleatorio para la materia"""
        if not self.connection:
            return None

        query = "SELECT id FROM conceptos WHERE materia_id = %s ORDER BY RAND() LIMIT 1"
        self.cursor.execute(query, (materia_id,))
        result = self.cursor.fetchone()
        return result['id'] if result else None

    def _obtener_herramienta_aleatoria(self) -> Optional[int]:
        """Obtener una herramienta aleatoria"""
        if not self.connection:
            return None

        query = "SELECT id FROM herramientas ORDER BY RAND() LIMIT 1"
        self.cursor.execute(query)
        result = self.cursor.fetchone()
        return result['id'] if result else None

    def _asociar_competencias(self, practica_id: int, competencias: List[Dict]) -> None:
        """Asociar competencias a la práctica"""
        if not self.connection:
            return

        for comp in competencias:
            query = """
            INSERT INTO practica_competencia (practica_id, competencia_id, nivel)
            VALUES (%s, %s, %s)
            """
            self.cursor.execute(
                query, (practica_id, comp['id'], comp.get('nivel', 1)))

    def _generar_rubrica(self, practica_id: int, nivel_id: int) -> None:
        """Generar rúbrica según el nivel"""
        if not self.connection:
            return

        criterios = {
            1: [  # Básico
                ("Comprensión conceptual",
                 "Entendimiento de los conceptos básicos", 30),
                ("Implementación", "Correcta implementación de la solución", 40),
                ("Documentación", "Calidad de la documentación", 30)
            ],
            2: [  # Intermedio
                ("Diseño", "Calidad del diseño de la solución", 25),
                ("Implementación", "Correcta implementación", 35),
                ("Optimización", "Eficiencia de la solución", 20),
                ("Documentación", "Calidad de la documentación", 20)
            ],
            3: [  # Avanzado
                ("Diseño", "Calidad y originalidad del diseño", 20),
                ("Implementación", "Correcta implementación", 30),
                ("Optimización", "Eficiencia y rendimiento", 25),
                ("Innovación", "Aspectos innovadores", 15),
                ("Documentación", "Calidad de la documentación", 10)
            ]
        }

        for criterio, descripcion, puntaje in criterios.get(nivel_id, criterios[1]):
            query = """
            INSERT INTO rubricas (practica_id, criterio, descripcion, puntaje_maximo)
            VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(
                query, (practica_id, criterio, descripcion, puntaje))

    def _generar_rubrica_ml(self, practica_id: int, nivel_id: int, criterios_ml: List[str]) -> None:
        """Generar rúbrica basada en los criterios generados por ML"""
        if not self.connection:
            return

        # Ponderaciones según nivel
        ponderaciones = {
            1: [40, 35, 25],  # Básico
            2: [35, 30, 20, 15],  # Intermedio
            3: [30, 25, 20, 15, 10]  # Avanzado
        }

        # Usar el array de ponderaciones correcta según el nivel
        ponderacion = ponderaciones.get(nivel_id, ponderaciones[1])

        # Asegurar que tenemos suficientes criterios
        if len(criterios_ml) < len(ponderacion):
            # Agregar criterios genéricos si faltan
            criterios_adicionales = [
                "Documentación",
                "Implementación",
                "Innovación",
                "Optimización",
                "Diseño"
            ]
            criterios_ml.extend(
                criterios_adicionales[:len(ponderacion) - len(criterios_ml)])

        # Limitar a la cantidad según nivel
        criterios_ml = criterios_ml[:len(ponderacion)]

        # Insertar en la base de datos
        for idx, criterio in enumerate(criterios_ml):
            descripcion = f"Evaluación de {criterio.lower()}"
            query = """
            INSERT INTO rubricas (practica_id, criterio, descripcion, puntaje_maximo)
            VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(
                query, (practica_id, criterio, descripcion, ponderacion[idx]))

    def _generar_recursos(self, practica_id: int) -> None:
        """Generar recursos para la práctica"""
        if not self.connection:
            return

        recursos = [
            ("Guía de implementación", "documento", "https://ejemplo.com/guia",
             "Guía detallada para la implementación"),
            ("Material de referencia", "documento", "https://ejemplo.com/material",
             "Material de apoyo y referencias"),
            ("Video tutorial", "video", "https://ejemplo.com/video",
             "Tutorial en video de la implementación")
        ]

        for nombre, tipo, url, descripcion in recursos:
            query = """
            INSERT INTO recursos_practica (practica_id, tipo, nombre, url, descripcion)
            VALUES (%s, %s, %s, %s, %s)
            """
            self.cursor.execute(
                query, (practica_id, tipo, nombre, url, descripcion))

    def _generar_recursos_ml(self, practica_id: int, recursos_ml: List[str]) -> None:
        """Generar recursos basados en los generados por ML"""
        if not self.connection:
            return

        tipos = ["documento", "video", "enlace"]
        urls_demo = ["https://ejemplo.com/recurso1",
                     "https://ejemplo.com/recurso2", "https://ejemplo.com/recurso3"]

        for idx, recurso in enumerate(recursos_ml):
            tipo = tipos[idx % len(tipos)]
            url = urls_demo[idx % len(urls_demo)]
            descripcion = f"Recurso para apoyar el aprendizaje: {recurso}"

            query = """
            INSERT INTO recursos_practica (practica_id, tipo, nombre, url, descripcion)
            VALUES (%s, %s, %s, %s, %s)
            """
            self.cursor.execute(
                query, (practica_id, tipo, recurso, url, descripcion))

    def crear_grupo(self, nombre: str, descripcion: str, practica_id: int) -> int:
        """Crear un nuevo grupo para una práctica"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return -1

        query = """
        INSERT INTO grupos (nombre, descripcion, practica_id)
        VALUES (%s, %s, %s)
        """
        self.cursor.execute(query, (nombre, descripcion, practica_id))
        self.connection.commit()
        return self.cursor.lastrowid

    def agregar_miembro_grupo(self, grupo_id: int, usuario_id: int, rol: str) -> None:
        """Agregar un miembro a un grupo"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return

        query = """
        INSERT INTO grupo_miembros (grupo_id, usuario_id, rol)
        VALUES (%s, %s, %s)
        """
        self.cursor.execute(query, (grupo_id, usuario_id, rol))
        self.connection.commit()

    def registrar_entrega(self, practica_id: int, estudiante_id: int,
                          archivos_url: str) -> int:
        """Registrar una entrega de práctica"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return -1

        query = """
        INSERT INTO entregas (practica_id, estudiante_id, fecha_entrega, 
                            estado, archivos_url)
        VALUES (%s, %s, %s, %s, %s)
        """
        self.cursor.execute(query, (
            practica_id, estudiante_id, datetime.now(),
            'pendiente', archivos_url
        ))
        self.connection.commit()
        return self.cursor.lastrowid

    def evaluar_entrega(self, entrega_id: int, profesor_id: int,
                        calificacion: float, comentarios: str) -> None:
        """Evaluar una entrega"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return

        # Actualizar entrega
        query = """
        UPDATE entregas 
        SET estado = 'revisada', calificacion = %s
        WHERE id = %s
        """
        self.cursor.execute(query, (calificacion, entrega_id))

        # Registrar retroalimentación
        query = """
        INSERT INTO retroalimentacion (entrega_id, profesor_id, comentario, aspecto)
        VALUES (%s, %s, %s, %s)
        """
        self.cursor.execute(query, (
            entrega_id, profesor_id, comentarios, 'evaluación general'
        ))
        self.connection.commit()

    def obtener_practica_completa(self, practica_id: int) -> Optional[Dict]:
        """Obtener todos los detalles de una práctica"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return None

        # Obtener información básica
        query = """
        SELECT p.*, m.nombre as materia, n.nombre as nivel, 
               c.nombre as concepto, h.nombre as herramienta,
               u.nombre as autor
        FROM practicas p
        JOIN materias m ON p.materia_id = m.id
        JOIN niveles n ON p.nivel_id = n.id
        JOIN conceptos c ON p.concepto_id = c.id
        JOIN herramientas h ON p.herramienta_id = h.id
        JOIN usuarios u ON p.autor_id = u.id
        WHERE p.id = %s
        """
        self.cursor.execute(query, (practica_id,))
        practica = self.cursor.fetchone()

        if not practica:
            return None

        # Obtener competencias
        self.cursor.execute("""
            SELECT c.*, pc.nivel
            FROM competencias c
            JOIN practica_competencia pc ON c.id = pc.competencia_id
            WHERE pc.practica_id = %s
        """, (practica_id,))
        practica['competencias'] = self.cursor.fetchall()

        # Obtener rúbrica
        self.cursor.execute(
            "SELECT * FROM rubricas WHERE practica_id = %s",
            (practica_id,))
        practica['rubrica'] = self.cursor.fetchall()

        # Obtener recursos
        self.cursor.execute("""
            SELECT * FROM recursos_practica 
            WHERE practica_id = %s
        """, (practica_id,))
        practica['recursos'] = self.cursor.fetchall()

        # Obtener entregas si existen
        self.cursor.execute("""
            SELECT e.*, u.nombre as estudiante_nombre
            FROM entregas e
            JOIN usuarios u ON e.estudiante_id = u.id
            WHERE e.practica_id = %s
        """, (practica_id,))
        practica['entregas'] = self.cursor.fetchall()

        # Obtener grupos si existen
        self.cursor.execute("""
            SELECT * FROM grupos
            WHERE practica_id = %s
        """, (practica_id,))
        grupos = self.cursor.fetchall()

        if grupos:
            practica['grupos'] = grupos
            # Para cada grupo, obtener sus miembros
            for grupo in practica['grupos']:
                self.cursor.execute("""
                    SELECT gm.*, u.nombre as usuario_nombre
                    FROM grupo_miembros gm
                    JOIN usuarios u ON gm.usuario_id = u.id
                    WHERE gm.grupo_id = %s
                """, (grupo['id'],))
                grupo['miembros'] = self.cursor.fetchall()

        return practica

    def obtener_practicas_por_materia(self, materia_id: int) -> List[Dict]:
        """Obtener todas las prácticas de una materia"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return []

        query = """
        SELECT p.id, p.titulo, p.objetivo, p.fecha_entrega, 
               u.nombre as autor, n.nombre as nivel
        FROM practicas p
        JOIN usuarios u ON p.autor_id = u.id
        JOIN niveles n ON p.nivel_id = n.id
        WHERE p.materia_id = %s
        ORDER BY p.fecha_entrega DESC
        """
        self.cursor.execute(query, (materia_id,))
        return self.cursor.fetchall()

    def obtener_practicas_por_profesor(self, profesor_id: int) -> List[Dict]:
        """Obtener todas las prácticas creadas por un profesor"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return []

        query = """
        SELECT p.id, p.titulo, p.objetivo, p.fecha_entrega, 
               m.nombre as materia, n.nombre as nivel
        FROM practicas p
        JOIN materias m ON p.materia_id = m.id
        JOIN niveles n ON p.nivel_id = n.id
        WHERE p.autor_id = %s
        ORDER BY p.fecha_entrega DESC
        """
        self.cursor.execute(query, (profesor_id,))
        return self.cursor.fetchall()

    def obtener_entregas_por_estudiante(self, estudiante_id: int) -> List[Dict]:
        """Obtener todas las entregas realizadas por un estudiante"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return []

        query = """
        SELECT e.*, p.titulo as practica_titulo, 
               m.nombre as materia, p.fecha_entrega as fecha_limite
        FROM entregas e
        JOIN practicas p ON e.practica_id = p.id
        JOIN materias m ON p.materia_id = m.id
        WHERE e.estudiante_id = %s
        ORDER BY e.fecha_entrega DESC
        """
        self.cursor.execute(query, (estudiante_id,))
        return self.cursor.fetchall()

    def obtener_entregas_pendientes_profesor(self, profesor_id: int) -> List[Dict]:
        """Obtener todas las entregas pendientes de revisión para las prácticas de un profesor"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return []

        query = """
        SELECT e.*, p.titulo as practica_titulo, 
               u.nombre as estudiante_nombre
        FROM entregas e
        JOIN practicas p ON e.practica_id = p.id
        JOIN usuarios u ON e.estudiante_id = u.id
        WHERE p.autor_id = %s AND e.estado = 'pendiente'
        ORDER BY e.fecha_entrega ASC
        """
        self.cursor.execute(query, (profesor_id,))
        return self.cursor.fetchall()

    def actualizar_modelo_ml(self, titulos: List[str], objetivos: List[str], contenidos: List[str]) -> bool:
        """Actualizar el modelo de ML con nuevos datos"""
        try:
            # Entrenar el modelo con nuevos datos
            self.generador_ml.entrenar_modelo(titulos, objetivos, contenidos)
            return True
        except Exception as e:
            print(f"Error al actualizar el modelo ML: {e}")
            return False

    def recopilar_datos_entrenamiento(self) -> Tuple[List[str], List[str], List[str]]:
        """Recopilar datos de prácticas existentes para entrenar el modelo"""
        if not self.connection:
            print("Error: No hay conexión a la base de datos")
            return [], [], []

        # Obtener datos básicos de prácticas
        query = """
        SELECT titulo, objetivo, introduccion, descripcion
        FROM practicas p
        WHERE introduccion IS NOT NULL AND descripcion IS NOT NULL
        """
        self.cursor.execute(query)
        practicas = self.cursor.fetchall()

        titulos = []
        objetivos = []
        contenidos = []

        for p in practicas:
            titulos.append(p['titulo'])
            objetivos.append(p['objetivo'])
            # Combinar introducción y descripción como contenido
            contenido = f"{p['introduccion']} {p['descripcion']}"
            contenidos.append(contenido)

        return titulos, objetivos, contenidos

    def cerrar_conexion(self):
        """Cerrar conexión a la base de datos"""
        if self.connection:
            self.cursor.close()
            self.connection.close()

    def __del__(self):
        """Destructor para asegurar que se cierre la conexión"""
        self.cerrar_conexion()


class APIGeneradorPracticas:
    """Clase para manejo de API REST del generador de prácticas"""

    def __init__(self, db_host="localhost", db_user="usuario", db_password="password", db_name="generador_practicas"):
        self.db = GeneradorPracticasDB(
            host=db_host, user=db_user, password=db_password, database=db_name)

    def autenticar_usuario(self, email: str, password: str) -> Dict[str, Any]:
        """Autenticar usuario y devolver token si es válido"""
        usuario = self.db.login_usuario(email, password)
        if not usuario:
            return {"error": "Credenciales inválidas", "success": False}

        # Generar token simple (en producción usar JWT u OAuth)
        token = hashlib.sha256(
            f"{email}:{datetime.now().isoformat()}".encode()).hexdigest()

        return {
            "success": True,
            "usuario": usuario,
            "token": token,
            "expira": (datetime.now() + timedelta(hours=24)).isoformat()
        }

    def crear_usuario_api(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Crear un nuevo usuario desde la API"""
        try:
            usuario_id = self.db.crear_usuario(
                nombre=datos.get('nombre', ''),
                email=datos.get('email', ''),
                password=datos.get('password', ''),
                rol=datos.get('rol', 'estudiante')
            )

            if usuario_id > 0:
                return {"success": True, "usuario_id": usuario_id}
            else:
                return {"success": False, "error": "Error al crear usuario"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generar_practica_api(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Generar una nueva práctica desde la API"""
        try:
            # Verificar campos requeridos
            campos_requeridos = ['titulo', 'materia_id',
                                 'nivel_id', 'autor_id', 'objetivo']
            for campo in campos_requeridos:
                if campo not in datos:
                    return {"success": False, "error": f"Campo requerido: {campo}"}

            # Procesar competencias
            competencias = datos.get('competencias', [])
            tiempo_estimado = datos.get('tiempo_estimado', 14)

            # Usar el generador ML para crear la práctica
            if datos.get('usar_ml', True):
                practica = self.db.generar_practica_ml(
                    titulo=datos['titulo'],
                    objetivo=datos['objetivo'],
                    materia_id=datos['materia_id'],
                    nivel_id=datos['nivel_id'],
                    autor_id=datos['autor_id'],
                    competencias=competencias,
                    tiempo_estimado=tiempo_estimado
                )

                return {"success": True, "practica": practica}
            else:
                # Usar el método tradicional
                practica_id = self.db.generar_practica(
                    titulo=datos['titulo'],
                    materia_id=datos['materia_id'],
                    nivel_id=datos['nivel_id'],
                    autor_id=datos['autor_id'],
                    competencias=competencias,
                    tiempo_estimado=tiempo_estimado,
                    objetivo=datos['objetivo']
                )

                if practica_id > 0:
                    # Obtener la práctica completa
                    practica = self.db.obtener_practica_completa(practica_id)
                    return {"success": True, "practica": practica}
                else:
                    return {"success": False, "error": "Error al generar práctica"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def obtener_practica_api(self, practica_id: int) -> Dict[str, Any]:
        """Obtener detalles de una práctica desde la API"""
        try:
            practica = self.db.obtener_practica_completa(practica_id)
            if practica:
                return {"success": True, "practica": practica}
            else:
                return {"success": False, "error": "Práctica no encontrada"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def entrenar_modelo_api(self) -> Dict[str, Any]:
        """Entrenar modelo con datos existentes desde la API"""
        try:
            # Recopilar datos de entrenamiento
            titulos, objetivos, contenidos = self.db.recopilar_datos_entrenamiento()

            if not titulos:
                return {"success": False, "error": "No hay datos suficientes para entrenar"}

            # Entrenar modelo
            resultado = self.db.actualizar_modelo_ml(
                titulos, objetivos, contenidos)

            if resultado:
                return {
                    "success": True,
                    "mensaje": f"Modelo entrenado con {len(titulos)} prácticas"
                }
            else:
                return {"success": False, "error": "Error al entrenar el modelo"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def crear_entrega_api(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Crear una nueva entrega desde la API"""
        try:
            # Verificar campos requeridos
            campos_requeridos = ['practica_id',
                                 'estudiante_id', 'archivos_url']
            for campo in campos_requeridos:
                if campo not in datos:
                    return {"success": False, "error": f"Campo requerido: {campo}"}

            # Registrar entrega
            entrega_id = self.db.registrar_entrega(
                practica_id=datos['practica_id'],
                estudiante_id=datos['estudiante_id'],
                archivos_url=datos['archivos_url']
            )

            if entrega_id > 0:
                return {"success": True, "entrega_id": entrega_id}
            else:
                return {"success": False, "error": "Error al registrar entrega"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def evaluar_entrega_api(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluar una entrega desde la API"""
        try:
            # Verificar campos requeridos
            campos_requeridos = ['entrega_id',
                                 'profesor_id', 'calificacion', 'comentarios']
            for campo in campos_requeridos:
                if campo not in datos:
                    return {"success": False, "error": f"Campo requerido: {campo}"}

            # Evaluar entrega
            self.db.evaluar_entrega(
                entrega_id=datos['entrega_id'],
                profesor_id=datos['profesor_id'],
                calificacion=datos['calificacion'],
                comentarios=datos['comentarios']
            )

            return {"success": True, "mensaje": "Entrega evaluada correctamente"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cerrar(self):
        """Cerrar conexiones"""
        self.db.cerrar_conexion()
