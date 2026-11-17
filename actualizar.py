import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai

# Fuentes: Internacional, España, Inteligencia Artificial y Redes (Reddit/X)
FUENTES = [
    # Internacional
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
    "https://rss.dw.com/xml/rss-sp-all",
    "https://www.france24.com/es/rss",
    # España
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada",
    "https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es",
    # Inteligencia Artificial a nivel mundial
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://news.google.com/rss/search?q=artificial+intelligence+OR+OpenAI+OR+Google+Gemini+OR+Anthropic+when:7d&hl=en-US&gl=US&ceid=US:en",
    # Comunidad global en Reddit y X
    "https://news.google.com/rss/search?q=site:reddit.com/r/worldnews+OR+site:reddit.com/r/singularity&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=site:x.com+breaking+world+news+OR+AI+breakthrough&hl=en-US&gl=US&ceid=US:en"
]

def obtener_titulares():
    recopilacion = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    for url in FUENTES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                items = root.findall('.//item')[:6] or root.findall('.//{http://www.w3.org/2005/Atom}entry')[:6]
                for item in items:
                    titulo = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title')
                    link = item.findtext('link')
                    if link is None:
                        link_el = item.find('{http://www.w3.org/2005/Atom}link')
                        link = link_el.attrib.get('href', '') if link_el is not None else ''
                    if titulo:
                        recopilacion.append(f"- {titulo.strip()} ({link})")
        except Exception as e:
            print(f"Saltando fuente {url}: {e}")
            
    return "\n".join(recopilacion)

def obtener_candidatos_modelo(client):
    candidatos = []
    excluidos = ("embedding", "imagen", "veo", "tts", "audio", "image", "aqa", "robotics", "computer-use")
    try:
        for m in client.models.list():
            nombre = m.name.replace("models/", "")
            if "gemini" in nombre.lower() and not any(x in nombre.lower() for x in excluidos):
                candidatos.append(nombre)
    except Exception as e:
        print(f"Error listando modelos: {e}")

    def prioridad(nombre):
        if nombre == "gemini-2.5-flash":
            return 99
        if "3" in nombre and "flash" in nombre:
            return 1
        if "flash-lite" in nombre:
            return 2
        if "flash" in nombre:
            return 3
        if "3" in nombre:
            return 4
        return 5

    candidatos.sort(key=prioridad)
    return candidatos or ["gemini-2.5-flash-lite", "gemini-2.0-flash"]

def generar_resumen(texto_bruto):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = f"""
    Eres un editor jefe de actualidad internacional, española y tecnológica. Analiza estos titulares, reportes y debates de esta semana y redacta un resumen ejecutivo en español de España, objetivo, directo y sin sensacionalismo.
    
    Reglas:
    - Agrupa noticias repetidas sobre el mismo suceso y prioriza los hechos de mayor impacto.
    - Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta (sin bloques markdown ```json):
    {{
      "fecha_actualizacion": "{datetime.now().strftime('%d/%m/%Y %H:%M')}",
      "titular_semana": "Frase breve y directa con el acontecimiento más relevante de la semana",
      "bloques": [
        {{
          "categoria": "Actualidad en España",
          "resumen": "Párrafo claro con las noticias políticas, económicas y sociales más importantes de España esta semana.",
          "puntos_clave": ["Hecho 1", "Hecho 2"]
        }},
        {{
          "categoria": "Inteligencia Artificial",
          "resumen": "Resumen de los principales lanzamientos, nuevos modelos, avances y regulación de la IA a nivel mundial.",
          "puntos_clave": ["Hecho 1", "Hecho 2"]
        }},
        {{
          "categoria": "Geopolítica y Diplomacia",
          "resumen": "Párrafo claro con los principales movimientos políticos, conflictos y acuerdos internacionales.",
          "puntos_clave": ["Hecho 1", "Hecho 2"]
        }},
        {{
          "categoria": "Economía y Mercados Globales",
          "resumen": "Resumen de decisiones económicas, comercio, energía o mercados con impacto global.",
          "puntos_clave": ["Hecho 1", "Hecho 2"]
        }},
        {{
          "categoria": "Ciencia, Clima y Sociedad",
          "resumen": "Avances científicos, medio ambiente y sucesos sociales destacados de la semana.",
          "puntos_clave": ["Hecho 1", "Hecho 2"]
        }},
        {{
          "categoria": "Pulso Global en Redes",
          "resumen": "Temas internacionales y tecnológicos que más debate están generando en Reddit y X.",
          "puntos_clave": ["Tema 1", "Tema 2"]
        }}
      ]
    }}

    Datos recopilados:
    {texto_bruto}
    """
    
    ultimo_error = None
    for modelo in obtener_candidatos_modelo(client):
        try:
            print(f"Probando modelo: {modelo}")
            response = client.models.generate_content(
                model=modelo,
                contents=prompt
            )
            limpio = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(limpio)
        except Exception as e:
            print(f"No disponible {modelo}: {e}")
            ultimo_error = e

    raise RuntimeError(f"Ningún modelo pudo generar el resumen. Último error: {ultimo_error}")

if __name__ == "__main__":
    noticias = obtener_titulares()
    if noticias:
        resultado = generar_resumen(noticias)
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print("Resumen mundial, español y de IA generado con éxito.")
