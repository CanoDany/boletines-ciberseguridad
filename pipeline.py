#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, json, re, traceback
import requests
import numpy as np
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import os
import sys

# configuracion


def app_dir() -> str:
    """Carpeta real donde vive el .exe o el código fuente."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path: str) -> str:
    """Ubica archivos incluidos por PyInstaller: XML, modelos, assets, etc."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = app_dir()
    return os.path.join(base_path, relative_path)


BASE_DIR = app_dir()
load_dotenv(os.path.join(BASE_DIR, ".env"))

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "").strip()  # se carga desde .env
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")  # modelo

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_MODEL_LOCAL = resource_path(os.path.join("models", "all-MiniLM-L6-v2"))
EMBED_MODEL = EMBED_MODEL_LOCAL if os.path.exists(EMBED_MODEL_LOCAL) else EMBED_MODEL_NAME

CISA_URL     = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
MITRE_URL    = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

CWE_XML = resource_path(os.path.join("mnt", "data", "cwec_v4.18.xml"))

OUTPUT_JSON  = os.path.join(BASE_DIR, "boletin_diario.json")
N_EVENTS     = 1

print("⚡ Cargando modelos...")
embed_model = SentenceTransformer(EMBED_MODEL)
print("✅ Modelos listos.")


# carga MITRE ATT&CK

def load_mitre():
    r = requests.get(MITRE_URL, timeout=30)
    if r.status_code == 200:
        return r.json()
    return {}

MITRE_DATA = load_mitre()

def build_mitre_index(mitre_json):
    docs = []
    for obj in mitre_json.get("objects", []):
        if obj.get("type") == "attack-pattern":
            name = obj.get("name", "")
            desc = obj.get("description", "")
            tactics = [p.get("phase_name") for p in obj.get("kill_chain_phases", [])]
            text = f"{name}. {desc} {' '.join(tactics)}"
            docs.append({"name": name, "tactics": tactics, "text": text})
    texts = [d["text"] for d in docs]
    embs = embed_model.encode(texts, normalize_embeddings=True) if texts else np.array([])
    return docs, embs

MITRE_DOCS, MITRE_EMBS = build_mitre_index(MITRE_DATA)

def map_to_mitre(description, topk=3):
    if len(MITRE_EMBS) == 0:
        return []
    q = embed_model.encode([description], normalize_embeddings=True)[0]
    sims = np.dot(MITRE_EMBS, q)
    idxs = np.argsort(sims)[::-1][:topk]
    tactics = []
    for i in idxs:
        tactics.extend(MITRE_DOCS[i]["tactics"])
    return list(set(tactics))


# cargar el catalogo de CWE

def load_cwe_dict(xml_path):
    with open(CWE_XML, "rb") as f:
        tree = ET.parse(f)

    root = tree.getroot()
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0].strip("{")
    nsmap = {"cwe": ns} if ns else {}

    cwe_dict = {}
    elems = root.findall(".//cwe:Weakness", nsmap) if ns else root.findall(".//Weakness")
    for weakness in elems:
        wid = weakness.get("ID")
        name = weakness.get("Name")
        desc_el = weakness.find("cwe:Description", nsmap) if ns else weakness.find("Description")
        desc = desc_el.text.strip() if (desc_el is not None and desc_el.text) else ""
        if wid and name:
            cwe_dict[f"CWE-{wid}"] = {"Name": name, "Description": desc}

    return cwe_dict


CWE_MAP = load_cwe_dict(CWE_XML)
print(f"✅ CWE cargados: {len(CWE_MAP)}")

if CWE_MAP:
    CWE_TEXTS = [f"{cid} {data['Name']} {data['Description']}" for cid, data in CWE_MAP.items()]
    CWE_IDS   = list(CWE_MAP.keys())
    CWE_EMBS  = embed_model.encode(CWE_TEXTS, normalize_embeddings=True)
else:
    CWE_TEXTS, CWE_IDS, CWE_EMBS = [], [], np.array([])

def map_to_cwe(description, topk=3):
    if len(CWE_EMBS) == 0:
        return []
    q = embed_model.encode([description], normalize_embeddings=True)[0]
    sims = np.dot(CWE_EMBS, q)
    idxs = np.argsort(sims)[::-1][:topk]
    results = []
    for i in idxs:
        cid = CWE_IDS[i]
        results.append(f"{cid}: {CWE_MAP[cid]['Name']}")
    return results

def explicar_cwe(cwe_id):
    """
    Explica brevemente qué significa un CWE específico.
    Usa la descripción del XML si existe, y genera un resumen claro en español con Perplexity.
    """
    if cwe_id not in CWE_MAP:
        return ""

    name = CWE_MAP[cwe_id]["Name"]
    desc = CWE_MAP[cwe_id]["Description"]

    prompt = f"""
Resume en UNA sola frase técnica qué representa la debilidad {cwe_id}.
REQUISITOS:
- Máximo 20 palabras.
- Lenguaje técnico.
- Sin ejemplos.
- Sin listas.
- Sin referencias numéricasque este algo asi: [1], [2], ni notas.
- Sin introducciones.

ESTRUCTURA OBLIGATORIA:
Debilidad que permite <impacto principal> debido a <causa raíz>.

DESCRIPCIÓN OFICIAL:
{desc}

Devuelve SOLO la frase final.

        """

    respuesta = ask_llm(prompt, 150)
    respuesta = limpiar_brackets(respuesta)
    return respuesta




# 3. CVSS por NVD 2.0

def get_cvss_from_nvd(cve_id):
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return None
        metrics = vulns[0]["cve"].get("metrics", {})
        if "cvssMetricV31" in metrics:
            return metrics["cvssMetricV31"][0]["cvssData"]["baseScore"]
        elif "cvssMetricV30" in metrics:
            return metrics["cvssMetricV30"][0]["cvssData"]["baseScore"]
        elif "cvssMetricV2" in metrics:
            return metrics["cvssMetricV2"][0]["cvssData"]["baseScore"]
    except Exception as e:
        print("⚠️ Error CVSS lookup:", e)
    return None


# 4. LLM de Perplexity

def ask_llm(prompt, max_tokens=256):
    if not PERPLEXITY_API_KEY:
        return "Error: falta configurar PERPLEXITY_API_KEY en el archivo .env."

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️ Error al usar Perplexity: {e}")
        return "Error al generar respuesta."

def ensure_spanish(text: str) -> str:
    english_markers = ["the", "this", "note", "based", "information", "may", "could"]
    eng_count = sum(1 for w in english_markers if w.lower() in text.lower())
    if eng_count >= 2:
        prompt = f"""Traduce el siguiente texto al español formal.
Mantén nombres propios y términos técnicos (CVE, CVSS, CWE, MITRE, etc.) en inglés.
No añadas comentarios extra.

Texto:
{text}
"""
        return ask_llm(prompt, max_tokens=200)
    return text

def limpiar_brackets(text: str) -> str:
    """
    Elimina referencias tipo [1], [2], etc. y dobles espacios.
    """
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)  
    return text.strip()


# generar titulo

def generar_titulo(cve, producto, vendor, descripcion):
    prompt = f"""
Genera un TÍTULO técnico y conciso en español para un boletín de ciberseguridad
sobre la vulnerabilidad {cve} que afecta a {producto} de {vendor}.

REQUISITOS OBLIGATORIOS:
- Máximo 12 palabras.
- UNA sola línea.
- Sin punto final.
- Sin comillas.
- Sin markdown.
- Sin listas ni viñetas.
- Sin referencias numéricas ni notas entre corchetes.
- No incluyas palabras como: “nota”, “informe”, “boletín”, “actualización”.

ESTILO:
- Lenguaje técnico y neutral.
- Enfocado en el impacto principal.
- Sin adjetivos innecesarios.

USA EXACTAMENTE UNA de estas estructuras:
- Vulnerabilidad <impacto principal> en <producto>
- <Impacto principal> en <producto> por vulnerabilidad <CVE>

DESCRIPCIÓN DE CONTEXTO:
{descripcion}

EJEMPLO CORRECTO:
Vulnerabilidad de divulgación de información en Windows

Devuelve SOLO el título final.

"""
    txt = ask_llm(prompt, 40)

    # Limpieza básica
    txt = limpiar_brackets(txt)    
    txt = re.sub(r"[\r\n]", " ", txt).strip()  
    txt = re.sub(r"^[-*#•\s]+", "", txt)  
    txt = ensure_spanish(txt)

    # Quitar punto final si lo pone
    if txt.endswith("."):
        txt = txt[:-1]

    return txt.strip()


def generar_resumen(cve, producto, vendor, descripcion):
    prompt = f"""
        Redacta un RESUMEN EJECUTIVO técnico en español sobre la vulnerabilidad {cve}.

REQUISITOS OBLIGATORIOS:
- UNA sola oración bien detallada.
- Entre 90 y 180 caracteres.
- Sin saltos de línea.
- Sin paréntesis.
- Sin referencias numéricas ni notas entre corchetes es decir sin cosas como [1][2].
- Sin lenguaje narrativo o periodístico.

CONTENIDO:
- Describe el impacto de seguridad.
- Indica el vector o condición principal.
- Enfocado en riesgo para la organización.

REGLAS DE NOMBRES:
- Respeta EXACTAMENTE los nombres propios, marcas y productos.
- No traduzcas nombres técnicos.
- Mantén CVE, CVSS, CWE, MITRE en inglés.

DATOS:
CVE: {cve}
Producto: {producto}
Vendor: {vendor}
Descripción: {descripcion}

EJEMPLO CORRECTO:
La vulnerabilidad permite a un atacante local divulgar información sensible en sistemas Windows afectados.

Devuelve SOLO la oración final.

        """
    txt = ask_llm(prompt, max_tokens=300)
    txt = re.sub(r"(?i)(note:.*|this executive.*)", "", txt)
    txt = txt.replace("\n", " ").strip()
    txt = ensure_spanish(txt)
    if len(txt) > 200:
        txt = txt[:200].rsplit(" ", 1)[0] + "."
    return txt

def generar_urgencia(cve, descripcion):
    prompt = f"""
Clasifica la urgencia del CVE {cve} según la siguiente descripción:
{descripcion}

Devuelve solo una palabra (Alto, Medio o Bajo), considerando que si es de 0 a 3.99 ponle la palabra (Bajo), 
si es de 4 a 6.9 ponle la palabra (Medio) y si es de 7 a 10 ponle la palabra (Alto).
No incluyas referencias numéricas ni notas entre corchetes (como [1], [2], etc.).
"""
    txt = ask_llm(prompt, 10)
    # Limpieza por si el modelo insiste en poner referencias
    txt = re.sub(r"\[\d+\]", "", txt).strip()
    return txt


def generar_mitigaciones(cve, producto, descripcion):
    prompt = f"""
Propón EXACTAMENTE TRES medidas de mitigación técnicas y prácticas en español
para reducir el riesgo de la vulnerabilidad {cve} en {producto}.

FORMATO OBLIGATORIO (SI NO SE CUMPLE, LA RESPUESTA ES INCORRECTA):
- UNA sola línea.
- Exactamente 3 medidas.
- Separadas únicamente por punto y coma (;).
- Cada medida inicia con mayúscula.
- Cada medida termina con punto final.
- No uses símbolos especiales.
- No uses listas, viñetas, numeración ni markdown.
- No incluyas < >, -, *, •, #, números ni saltos de línea.
- No incluyas referencias ni notas.

REGLAS DE CONTENIDO:
- Medidas accionables y realistas.
- Respeta EXACTAMENTE nombres propios y productos.
- No traduzcas marcas o tecnologías.

DESCRIPCIÓN:
{descripcion}

EJEMPLO CORRECTO (SÍGUELO EXACTAMENTE):
Aplicar el parche oficial del fabricante.; Restringir el acceso a servicios expuestos.; Monitorear intentos de explotación mediante registros.

Responde SOLO con la línea final.

"""
    txt = ask_llm(prompt, 200)

    # quitar saltos de línea y markdown básico
    import re
    txt = re.sub(r"[\r\n]+", " ", txt)
    txt = re.sub(r"[#*•]", "", txt)

    medidas = [m.strip(" -•") for m in txt.split(";") if m.strip()]
    medidas = [ensure_spanish(m) for m in medidas]
    return [m if not m.endswith(("…", "reg", "etc")) else m + "." for m in medidas]




# Clasificar boletines por sector (básico)

# Clasificar boletines por sector con IA (Perplexity)

def clasificar_sector_ia(titulo):
    prompt = f"""
    Basándote únicamente en el siguiente TÍTULO de un boletín de ciberseguridad,
    propón el sector o industria al que pertenece la empresa, producto o sistema afectado.

    Elige el sector más probable entre estas opciones:
    Gobierno, Salud, Finanzas, Energía, Educación, Transporte, Tecnología, Industrial, Comunicaciones, General.

    Si el título menciona software, sistemas informáticos, plataformas web, hardware, o empresas tecnológicas
    (como Adobe, Microsoft, Google, Cisco, Oracle, IBM, etc.), clasifícalo en el sector "Tecnología".

    Devuelve solo el nombre del sector (una sola palabra), sin explicación ni puntuación.

    Título: {titulo}
    """
    sector = ask_llm(prompt, 40).strip()
    # Limpieza y validación
    sector = re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúÑñ ]", "", sector).strip()
    if not sector or len(sector.split()) > 2:
        sector = "General"
    return sector





# 6. Generar boletin

def generar_boletin(item):
    cve         = item.get("cveID") or ""
    descripcion = item.get("shortDescription") or ""
    producto    = item.get("product") or ""
    vendor      = item.get("vendorProject") or ""

    titulo   = generar_titulo(cve, producto, vendor, descripcion)
    resumen  = generar_resumen(cve, producto, vendor, descripcion)
    cvss = get_cvss_from_nvd(cve)
   # urgencia = generar_urgencia(cve, descripcion)
    #if urgencia not in ["Alto", "Medio", "Bajo"]:
    try:
        cvss_float = float(cvss)
        if cvss_float >= 7:
            urgencia = "Alto"
        elif cvss_float >= 4:
            urgencia = "Medio"
        else:
            urgencia = "Bajo"
    except Exception:
        urgencia = generar_urgencia(cve, descripcion)
    
    mitig    = generar_mitigaciones(cve, producto, descripcion)

    tacticas = map_to_mitre(descripcion)
    cwes     = map_to_cwe(descripcion)
    #cvss     = get_cvss_from_nvd(cve)

    # Clasificación automática por sector usando Perplexity
    sector = clasificar_sector_ia(titulo)

    # enlaces a CVE y CWE
    cve_link = f"https://nvd.nist.gov/vuln/detail/{cve}" if cve else None
    cwe_links = []
    for c in cwes:
        match = re.search(r"CWE-(\d+)", c)
        if match:
            cwe_id = match.group(1)
            cwe_links.append(f"https://cwe.mitre.org/data/definitions/{cwe_id}.html")

    #  Explicaciones de los CWE
    explicaciones_cwe = []
    for c in cwes:
        cid = c.split(":")[0].strip()  # Extrae el ID
        explicacion = explicar_cwe(cid)
        if explicacion:
            explicaciones_cwe.append(f"{cid}: {explicacion}")

    boletin = {
        "Titulo": titulo,
        "CVE": cve,
        "CVELink": cve_link,          
        "Fecha": item.get("dateAdded"),
        "Vendor": vendor,
        "Producto": producto,
        "ResumenEjecutivo": resumen,
        "PuntajeCVSS": str(cvss) if cvss else None,
        "NivelUrgencia": urgencia,
        "TacticasMITRE": tacticas,
        "ProcedimientosPosibles": [],
        "CWEAsociados": cwes,
        "CWELinks": cwe_links,        
        "CWEExplicacion": explicaciones_cwe,
        "MedidasMitigacion": mitig,
        "Sector": sector          
    }

    print(f"🗂️ Sector detectado para {cve}: {sector}")
    return boletin



# 7. Menu principal

def main(n=1):  
    print(f"⚡ Descargando CISA KEV... (solicitados {n} boletines)")
    resp = requests.get(CISA_URL, timeout=20)
    resp.raise_for_status()
    kev = resp.json()

    vulns = kev.get("vulnerabilities", [])[:n] 
    resultados = []

    for idx, item in enumerate(vulns, 1):
        print(f"[{idx}/{len(vulns)}] Procesando {item.get('cveID')}")
        boletin = generar_boletin(item)
        resultados.append(boletin)
        time.sleep(0.2)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Boletines generados: {len(resultados)} -> guardados en {OUTPUT_JSON}\n")
    return resultados 




# timeline

HISTORY_JSON = os.path.join(BASE_DIR, "history.json")

def update_history_for_boletin(boletin):
    """
    Guarda o actualiza el historial de un boletín según su CVE.
    Crea una línea temporal básica con la fecha y los datos principales.
    """
    try:
        if not boletin.get("CVE"):
            return

        # Cargar historial previo
        if os.path.exists(HISTORY_JSON):
            with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = {}

        cve = boletin["CVE"].strip()  
        entry = history.get(cve, {"cve": cve, "events": []})

        # Nuevo evento
        evento = {
            "fecha": boletin.get("Fecha"),
            "titulo": boletin.get("Titulo"),
            "nivel": boletin.get("NivelUrgencia"),
            "cvss": boletin.get("PuntajeCVSS"),
            "sector": boletin.get("Sector"),
        }

        # Evita duplicados
        if evento not in entry["events"]:
            entry["events"].append(evento)

        history[cve] = entry

        # Guardar historial actualizado
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        print(f"🕓 Historial actualizado para {cve}")

    except Exception as e:
        print(f"⚠️ Error al actualizar historial: {e}")



        
if __name__ == "__main__":
    main()