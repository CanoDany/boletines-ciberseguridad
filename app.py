# Importaciones

import os
import sys
import json
import shutil
import requests
from flask import Flask, render_template, send_file, request
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image as RLImage
from xml.sax.saxutils import escape


def app_dir() -> str:
    """Carpeta real donde vive el .exe o el código fuente."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path: str) -> str:
    """Ubica archivos incluidos por PyInstaller: templates, static, assets, XML, modelos."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = app_dir()
    return os.path.join(base_path, relative_path)


BASE_DIR = app_dir()
BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

# Cargar variables de entorno desde la misma carpeta del .exe/código
load_dotenv(os.path.join(BASE_DIR, ".env"))

from pipeline import main, OUTPUT_JSON, generar_boletin, update_history_for_boletin, HISTORY_JSON


def asegurar_archivo_editable(nombre_archivo: str):
    """Copia JSON iniciales del bundle hacia la carpeta del .exe si todavía no existen."""
    destino = os.path.join(BASE_DIR, nombre_archivo)
    origen = resource_path(nombre_archivo)
    if not os.path.exists(destino) and os.path.exists(origen):
        shutil.copyfile(origen, destino)


asegurar_archivo_editable("boletin_diario.json")
asegurar_archivo_editable("history.json")

# Rutas para salida de PDFs
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Inicialización de la app Flask
app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.config['TEMPLATES_AUTO_RELOAD'] = True



# lee los boletines generados desde el JSON del pipeline

def leer_boletines():
    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []



# Exportar boletines a PDF con ReportLab

def exportar_pdf(boletines, filename="boletin.pdf"):
    # Ruta completa del PDF dentro de la carpeta "output"
    pdf_path = os.path.join(OUTPUT_DIR, filename)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleStyle', fontSize=15, leading=20,
                              textColor=colors.HexColor("#003366"), spaceAfter=10))
    styles.add(ParagraphStyle(name='Header', fontSize=11, leading=14,
                              textColor=colors.white, backColor=colors.HexColor("#003366"),
                              alignment=1, spaceAfter=6))
    styles.add(ParagraphStyle(name='Body', fontSize=10.5, leading=15, alignment=4))
    styles.add(ParagraphStyle(name='SectionTitle', fontSize=11.5, leading=14,
                              textColor=colors.HexColor("#0b5394"), spaceAfter=6, spaceBefore=8))

    cell_style = ParagraphStyle(
        "cell",
        fontSize=9,
        leading=12,
        textColor=colors.black,
        wordWrap="CJK",
        allowWidows=1,
        allowOrphans=1,
        linkUnderline=True
    )

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=0.8 * cm,
        bottomMargin=2 * cm,
    )
    story = []
    def safe_para(texto: str) -> str:
        """
        Escapa caracteres que rompen el parser de ReportLab
        (<, >, &, comillas).
        """
        return escape(texto or "", {
            "'": "&apos;",
            '"': "&quot;",
        })

    # Rutas de logos compatibles con ejecución normal y con .exe PyInstaller
    logo_ipn_path = resource_path(os.path.join("assets", "logo_ipn.png"))
    logo_esime_path = resource_path(os.path.join("assets", "esime.jpg"))

    def header_logos(texto):
        # Anchuras
        left_w = 3 * cm
        right_w = 3 * cm
        center_w = doc.width - left_w - right_w

        # Logos
        try:
            logo_ipn = RLImage(logo_ipn_path, width=2.6*cm, height=2.6*cm)
        except Exception:
            logo_ipn = Spacer(1, 2.6*cm)

        try:
            logo_esime = RLImage(logo_esime_path, width=2.6*cm, height=2.6*cm)
        except Exception:
            logo_esime = Spacer(1, 2.6*cm)

        # Texto blanco dentro de la barra
        header_style = ParagraphStyle(
            "HeaderInsideBar",
            parent=styles["Body"],
            alignment=1,
            fontSize=15,
            leading=9,
            textColor=colors.white,
        )
        txt = Paragraph(texto, header_style)

        # Barra delgada
        barra_delgada = Table([[txt]], colWidths=[center_w], rowHeights=[25])
        barra_delgada.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#003366")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Tabla final
        t = Table([[logo_ipn, barra_delgada, logo_esime]], colWidths=[left_w, center_w, right_w])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),  
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),  
        ]))

        return t


    for idx, b in enumerate(boletines, 1):
        
        story.append(header_logos(f"Boletín de Ciberseguridad #{idx}"))
        story.append(Spacer(1, 10))

    
        story.append(Paragraph(b.get("Titulo", "Sin título"), styles["TitleStyle"]))
        story.append(Spacer(1, 12))



        # Tabla de detalles clave 
        nivel_pdf = (b.get("NivelUrgencia") or "").replace("*", "").strip()
        data = [
            ["CVE", Paragraph(
                f'<a href="{b.get("CVELink","")}" color="blue"><u>{b.get("CVE","N/A")}</u></a>',
                cell_style
            )],
            ["Fecha", Paragraph(b.get("Fecha", "N/A"), cell_style)],
            ["Vendor", Paragraph(b.get("Vendor", "N/A"), cell_style)],
            ["Producto", Paragraph(b.get("Producto", "N/A"), cell_style)],
            ["Puntaje CVSS", Paragraph(b.get("PuntajeCVSS", "N/A"), cell_style)],
            #["Nivel de Urgencia", Paragraph(b.get("NivelUrgencia", "N/A"), cell_style)],
           
            ["Nivel de Urgencia", Paragraph(safe_para(nivel_pdf or "N/A"), cell_style)],

            ["Sector", Paragraph(b.get("Sector", "N/A"), cell_style)],
            ["Tácticas MITRE", Paragraph("<br/>".join(b.get("TacticasMITRE", [])) or "N/A", cell_style)],
            ["CWE Asociados", Paragraph(
                "<br/>".join(
                    [
                        f'<a href="{link}" color="blue"><u>{name}</u></a>'
                        for name, link in zip(b.get("CWEAsociados", []), b.get("CWELinks", []))
                    ]
                ) or "N/A",
                cell_style
            )],
        ]

        table = Table(data, colWidths=[4 * cm, 12 * cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))

        # Descripción CWE / resumen / mitigaciones 
        if b.get("CWEExplicacion"):
            story.append(Paragraph("Descripción de CWE", styles["SectionTitle"]))
            for exp in b["CWEExplicacion"]:
                story.append(Paragraph(f"• {exp}", styles["Body"]))
            story.append(Spacer(1, 10))

        if b.get("ResumenEjecutivo"):
            story.append(Paragraph("Descripción", styles["SectionTitle"]))
            story.append(Paragraph(b["ResumenEjecutivo"], styles["Body"]))
            story.append(Spacer(1, 10))

        if b.get("MedidasMitigacion"):
            story.append(Paragraph("Medidas de Mitigación", styles["SectionTitle"]))
            for m in b["MedidasMitigacion"]:
                story.append(Paragraph("• " + safe_para(str(m)), styles["Body"]))
            story.append(Spacer(1, 10))

        if idx < len(boletines):
            story.append(PageBreak())

    doc.build(story)
    return pdf_path  # devolvemos la ruta completa



# Rutas Flask

@app.route("/", methods=["GET"])
def index():
    return render_template("boletines.html", boletines=leer_boletines(), mensaje=None)


@app.route("/generar_mes", methods=["POST"])
def generar_boletin_mes():
    from pipeline import generar_boletin, update_history_for_boletin

    cantidad = int(request.form.get("cantidad", 2))

    # Descarga el JSON completo de CISA
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    resp = requests.get(url, timeout=20)
    kev = resp.json()

    # Toma solo la cantidad solicitada
    vulns = kev.get("vulnerabilities", [])[:cantidad]

    if not vulns:
        return render_template("boletines.html", boletines=[], mensaje="No se encontraron boletines.")

    # Genera boletines y actualizar timeline automáticamente
    resultados = []
    for v in vulns:
        boletin = generar_boletin(v)
        resultados.append(boletin)

        try:
            update_history_for_boletin(boletin)
        except Exception as e:
            print(f"⚠️ No se pudo actualizar el historial: {e}")

    # Guarda boletines generados
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

    return render_template(
        "boletines.html",
        boletines=resultados,
        mensaje=f"Se generaron {len(resultados)} boletines correctamente.",
    )


@app.route("/pdf")
def pdf_boletin():
    boletines = leer_boletines()
    if not boletines:
        return render_template("boletines.html", boletines=[], mensaje="No hay boletines para exportar.")
    pdf_path = exportar_pdf(boletines, "boletin.pdf")
    return send_file(pdf_path, as_attachment=True)


@app.route("/filtrar_y_exportar", methods=["POST"])
def filtrar_y_exportar():
    def norm_nivel(s: str) -> str:
        return (s or "").replace("*", "").strip().lower()

    boletines = leer_boletines()
    if not boletines:
        return render_template("boletines.html", boletines=[], mensaje="No hay boletines disponibles.")

    nivel = request.form.get("nivel", "").lower()
    accion = request.form.get("accion")

    #Filtra boletines solo por nivel de urgencia
    filtrados = [
        b for b in boletines
        if norm_nivel(b.get("NivelUrgencia")) == nivel
]


    if not filtrados:
        return render_template(
            "boletines.html",
            boletines=[],
            mensaje=f"No hay boletines con nivel {nivel.capitalize()}.",
        )

    # Si el usuario quiere exportar PDF
    if accion == "pdf":
        filename = f"boletines_{nivel}.pdf"
        pdf_path = exportar_pdf(filtrados, filename)
        return send_file(pdf_path, as_attachment=True)

    # Si solo quiere verlos en pantalla
    mensaje = f"Mostrando {len(filtrados)} boletines con nivel {nivel.capitalize()}."
    return render_template("boletines.html", boletines=filtrados, mensaje=mensaje)


@app.route("/api")
def api():
    return leer_boletines()



# Timeline

def leer_historial():
    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@app.route("/timeline")
def timeline_index():
    boletines = leer_boletines()
    hist = leer_historial()

    items = []
    for b in boletines:
        cve = b.get("CVE")
        if not cve:
            continue
        eventos = hist.get(cve, {}).get("events", [])
        ultima_fecha = eventos[-1]["fecha"] if eventos else b.get("Fecha")
        items.append({
            "CVE": cve,
            "Titulo": b.get("Titulo"),
            "Fecha": ultima_fecha,
            "Sector": b.get("Sector"),
        })

    items = sorted(items, key=lambda x: x["Fecha"] or "", reverse=True)
    return render_template("timeline_index.html", items=items)


@app.route("/timeline/<cve>")
def timeline_view(cve):
    hist = leer_historial()
    entry = hist.get(cve)
    if not entry:
        return render_template("timeline.html", cve=cve, events=[], mensaje=f"No hay historial para {cve}")
    eventos = sorted(entry.get("events", []), key=lambda x: x["fecha"])
    return render_template("timeline.html", cve=cve, events=eventos, mensaje=None)



# Punto de entrada

if __name__ == "__main__":
    import webbrowser
    from threading import Timer

    HOST = "0.0.0.0"   
    PORT = 8000        

    url = f"http://127.0.0.1:{PORT}/"

    # abre el navegador
    Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"Servidor iniciado en {url}")
    app.run(host=HOST, port=PORT, debug=False)

