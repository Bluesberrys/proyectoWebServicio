import numpy as np
import re
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords

import nltk
nltk.download('stopwords')

class TextDataset(Dataset):
    def __init__(self, entradas, salidas, tokenizer):
        self.entradas = entradas
        self.salidas = salidas
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.entradas)

    def __getitem__(self, idx):
        entrada = self.tokenizer.transform([self.entradas[idx]]).toarray()[0]
        
        if len(entrada) < 5000:
            entrada = np.pad(entrada, (0, 5000 - len(entrada)), 'constant')
        elif len(entrada) > 5000:
            entrada = entrada[:5000]

        salida = float(self.salidas[idx])
        return torch.tensor(entrada, dtype=torch.float32), torch.tensor(salida, dtype=torch.float32)

class PracticaEvaluator(nn.Module):
    def __init__(self, input_dim=5000, hidden_dim=256, output_dim=1):
        super(PracticaEvaluator, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.dropout1 = nn.Dropout(0.3)  
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)  
        self.fc3 = nn.Linear(hidden_dim, hidden_dim // 2) 
        self.dropout2 = nn.Dropout(0.3)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()  

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout1(x)
        x = self.fc2(x)
        x = self.relu(x)
        x = self.dropout2(x)
        x = self.fc3(x)
        x = self.sigmoid(x) * 10  
        return x
class GeneradorPracticasML:
    def __init__(self):
        spanish_stopwords = stopwords.words('spanish')

        self.vectorizer = TfidfVectorizer(
            stop_words=spanish_stopwords,  
            max_features=5000,
            ngram_range=(1, 2)  
        )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = PracticaEvaluator(input_dim=5000, hidden_dim=256, output_dim=1).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001, weight_decay=1e-5) 
        self.criterion = nn.MSELoss()

        self.base_conocimiento = [
            "Resolver ecuaciones diferenciales de primer orden utilizando métodos numéricos.",
            "Análisis de datos utilizando técnicas estadísticas descriptivas e inferenciales.",
            "Implementación de algoritmos de ordenamiento y búsqueda para estructuras de datos.",
            "Diseño de experimentos científicos con controles apropiados.",
            "Desarrollo de aplicaciones web con frameworks modernos.",
            "Análisis literario de obras contemporáneas.",
            "Estudio de reacciones químicas orgánicas.",
            "Diseño de circuitos electrónicos analógicos y digitales.",
        ]

        self.tfidf_matrix = self.vectorizer.fit_transform(self.base_conocimiento)
        
        self.feedback_templates = {
            'excellent': [
                "Excelente trabajo. Has demostrado un dominio completo del tema.",
                "Trabajo sobresaliente. Cumple con todos los requisitos y va más allá.",
                "Felicitaciones por un trabajo excepcional. Demuestra comprensión profunda."
            ],
            'good': [
                "Buen trabajo. Cumple con la mayoría de los requisitos.",
                "Trabajo sólido con algunos aspectos destacables.",
                "Has demostrado buena comprensión del tema con algunas áreas para mejorar."
            ],
            'average': [
                "Trabajo aceptable. Cumple con los requisitos básicos.",
                "Has demostrado comprensión básica del tema.",
                "El trabajo cumple con lo mínimo esperado."
            ],
            'needs_improvement': [
                "El trabajo necesita mejoras. Revisa los requisitos de la actividad.",
                "Hay áreas importantes que requieren más atención.",
                "Es necesario profundizar más en el tema."
            ],
            'poor': [
                "El trabajo no cumple con los requisitos mínimos.",
                "Es necesario revisar completamente el trabajo.",
                "Recomiendo volver a estudiar los conceptos básicos del tema."
            ]
        }


    def analizar_contenido(self, contenido_archivo, titulo_actividad="", objetivo_actividad=""):
        """
        Analiza el contenido del archivo y devuelve una calificación y comentarios.
        Incorpora el título y objetivo de la actividad para una evaluación más precisa.
        """
        if not contenido_archivo.strip():
            raise ValueError("El archivo está vacío o no contiene texto válido.")
    
        contenido_archivo = self._preprocess_text(contenido_archivo)
        
        context = contenido_archivo
        if titulo_actividad and objetivo_actividad:
            context = f"{titulo_actividad}. {objetivo_actividad}. {contenido_archivo}"
        
        try:
            contenido_vectorizado = self.vectorizer.transform([context]).toarray()[0]
        except Exception as e:
            raise ValueError(f"Error al vectorizar el contenido: {str(e)}")
    
        if len(contenido_vectorizado) < 5000:
            contenido_vectorizado = np.pad(contenido_vectorizado, (0, 5000 - len(contenido_vectorizado)), 'constant')
        elif len(contenido_vectorizado) > 5000:
            contenido_vectorizado = contenido_vectorizado[:5000]
    
        contenido_tensor = torch.tensor(contenido_vectorizado, dtype=torch.float32).to(self.device)
        print(contenido_vectorizado[:10])  

        self.model.eval()
        with torch.no_grad():
            try:
                pred = self.model(contenido_tensor).cpu().numpy()[0]
                print(f"Predicción inicial del modelo: {pred}")
            except Exception as e:
                raise RuntimeError(f"Error al generar la predicción: {str(e)}")
    
        calificacion = float(round(pred, 1))
        
        relevancia = self._calcular_relevancia(contenido_archivo, titulo_actividad, objetivo_actividad)
        
        calificacion_ajustada = calificacion + (relevancia * 2)  # Aumentar el impacto de la relevancia
        calificacion_final = min(10.0, max(0.0, calificacion_ajustada))
        
        comentarios = self._generar_comentarios_detallados(calificacion_final, contenido_archivo, titulo_actividad, objetivo_actividad)
        
        sugerencias = self._generar_sugerencias_mejora(calificacion_final, contenido_archivo, titulo_actividad, objetivo_actividad)
        print(f"Calificación inicial: {calificacion}")
        print(f"Relevancia: {relevancia}")
        print(f"Calificación ajustada: {calificacion_final}")
        return {
            "calificacion": round(calificacion_final, 1),
            "comentarios": comentarios,
            "sugerencias": sugerencias,
            "relevancia": round(relevancia * 100, 1)
        }

    def _preprocess_text(self, text):
        """Preprocess text for analysis"""
        text = text.lower()
        text = re.sub(r'[^\w\s.,;:¿?¡!]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _calcular_relevancia(self, contenido, titulo, objetivo):
        """Calculate how relevant the submission is to the activity requirements"""
        if not titulo or not objetivo:
            return 1.0  
            
        requisitos = f"{titulo} {objetivo}"
        
        vec_requisitos = self.vectorizer.transform([requisitos])
        vec_contenido = self.vectorizer.transform([contenido])
        
        similarity = cosine_similarity(vec_requisitos, vec_contenido)[0][0]
        
        return 0.5 + (similarity * 0.5)

    def _generar_comentarios_detallados(self, calificacion, contenido, titulo, objetivo):
        """Generate detailed feedback based on score and content analysis"""
        if calificacion >= 9.0:
            template = np.random.choice(self.feedback_templates['excellent'])
        elif calificacion >= 7.0:
            template = np.random.choice(self.feedback_templates['good'])
        elif calificacion >= 5.0:
            template = np.random.choice(self.feedback_templates['average'])
        elif calificacion >= 3.0:
            template = np.random.choice(self.feedback_templates['needs_improvement'])
        else:
            template = np.random.choice(self.feedback_templates['poor'])
            
        word_count = len(contenido.split())
        length_comment = ""
        if word_count < 100:
            length_comment = " El contenido es muy breve, considera desarrollar más tus ideas."
        elif word_count > 1000:
            length_comment = " Has desarrollado un trabajo extenso, lo cual es positivo."
            
        relevance_comment = ""
        if titulo and objetivo:
            relevancia = self._calcular_relevancia(contenido, titulo, objetivo)
            if relevancia < 0.6:
                relevance_comment = " Tu trabajo podría estar más enfocado en el tema solicitado."
            elif relevancia > 0.8:
                relevance_comment = " Has abordado el tema de manera muy pertinente."
                
        return f"{template}{length_comment}{relevance_comment}"

    def _generar_sugerencias_mejora(self, calificacion, contenido, titulo, objetivo):
        """Generate improvement suggestions based on score and content analysis"""
        sugerencias = []
        
        if calificacion < 7.0:
            sugerencias.append("Revisa los conceptos fundamentales del tema.")
            
        if calificacion < 5.0:
            sugerencias.append("Considera rehacer el trabajo siguiendo más de cerca las instrucciones.")
            
        word_count = len(contenido.split())
        if word_count < 200:
            sugerencias.append("Desarrolla más tus ideas y argumentos.")
            
        if titulo and objetivo:
            relevancia = self._calcular_relevancia(contenido, titulo, objetivo)
            if relevancia < 0.7:
                sugerencias.append(f"Enfoca más tu trabajo en el tema: '{titulo}' y el objetivo: '{objetivo}'.")
                
        if not sugerencias and calificacion >= 8.0:
            sugerencias.append("Continúa con este nivel de trabajo en futuras entregas.")
            
        return sugerencias

    def entrenar_modelo(self, entradas, salidas, epochs=10, batch_size=32):
        """Entrena el modelo con datos de entrada (prácticas) y salida (calificaciones)."""
        if not entradas or not salidas or len(entradas) != len(salidas):
            raise ValueError("Datos de entrenamiento inválidos o insuficientes.")
            
        self.vectorizer.fit(entradas)
        
        dataset = TextDataset(entradas, salidas, self.vectorizer)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        self.model.train()
        
        best_loss = float('inf')
        patience = 5
        patience_counter = 0
        
        for epoch in range(epochs):
            total_loss = 0
            for inputs, targets in dataloader:
                inputs = inputs.to(self.device, dtype=torch.float32)
                targets = targets.to(self.device, dtype=torch.float32).view(-1, 1)

                self.optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)

                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()

            avg_loss = total_loss/len(dataloader)
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
            
            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), "modelo_practicas.pth")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

        self.model.load_state_dict(torch.load("modelo_practicas.pth"))
        print("Modelo entrenado y guardado.")
    
    def cargar_modelo(self, ruta="modelo_practicas.pth"):
        """Carga el modelo entrenado desde un archivo."""
        try:
            self.model.load_state_dict(torch.load(ruta, map_location=self.device))
            self.model.eval()
            print("Modelo cargado correctamente.")
        except Exception as e:
            raise RuntimeError(f"Error al cargar el modelo: {str(e)}")

    def generar_comentarios_y_calificacion(self, titulo_practica: str, entrega: str) -> dict:
        """Genera comentarios y calificación para una práctica entregada."""
        try:
            resultado = self.analizar_contenido(entrega, titulo_practica, "")
            return resultado
        except Exception as e:
            raise RuntimeError(f"Error al generar comentarios y calificación: {str(e)}")

    def generar_practica(self, titulo, objetivo):
        """Genera contenido para una práctica basada en el título y objetivo proporcionados."""
        consulta = f"{titulo} {objetivo}"
        consulta = re.sub(r'[^\w\s]', '', consulta.lower())

        consulta_vector = self.vectorizer.transform([consulta])
        similitudes = cosine_similarity(consulta_vector, self.tfidf_matrix)[0]

        idx_mas_similar = np.argmax(similitudes)
        similitud = similitudes[idx_mas_similar]

        if similitud > 0.1:
            base = self.base_conocimiento[idx_mas_similar]
        else:
            base = "Práctica general de aplicación de conocimientos."

        practica_generada = {
            "descripcion": f"Esta práctica se enfoca en: {base}",
            "objetivos_especificos": [
                f"Comprender los conceptos fundamentales relacionados con {titulo}",
                f"Aplicar técnicas para resolver problemas de {objetivo}",
                "Desarrollar habilidades analíticas y de resolución de problemas"
            ],
            "actividades": [
                {"numero": 1, "descripcion": f"Investigación sobre {titulo}", "tiempo_estimado": "2 horas"},
                {"numero": 2, "descripcion": f"Resolución de problemas relacionados con {objetivo}", "tiempo_estimado": "3 horas"},
                {"numero": 3, "descripcion": "Presentación y discusión de resultados", "tiempo_estimado": "1 hora"}
            ],
            "recursos": [
                "Libros de texto relacionados con la materia",
                "Artículos científicos recientes",
                "Herramientas de software específicas"
            ],
            "criterios_evaluacion": [
                "Comprensión de conceptos (30%)",
                "Aplicación práctica (40%)",
                "Presentación y comunicación (30%)"
            ],
            "recomendaciones": f"Se recomienda revisar conceptos básicos de {titulo.split()[0]} antes de comenzar."
        }

        return practica_generada

