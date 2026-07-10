from pathlib import Path
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
DESTINO = Path("models") / MODEL_NAME

print(f"Descargando/preparando modelo {MODEL_NAME}...")
DESTINO.parent.mkdir(parents=True, exist_ok=True)
modelo = SentenceTransformer(MODEL_NAME)
modelo.save(str(DESTINO))
print(f"Modelo guardado en: {DESTINO}")
