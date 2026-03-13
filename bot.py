import os
import feedparser
import requests
from groq import Groq

# Configuración
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Fuentes RSS chilenas
FUENTES = [
    # Noticias generales
    "https://feeds.emol.com/emol/nacional",
    "https://feeds.emol.com/emol/economia",
    "https://www.cooperativa.cl/noticias/rss/",
    "https://www.24horas.cl/rss/ultimas-noticias",
    "https://radio.uchile.cl/feed/",
    "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.elmostrador.cl/feed/",
    "https://www.theclinic.cl/feed/",
    "https://www.cnnchile.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/nacional/feed/",
    
    # Economía y negocios
    "https://www.df.cl/feed",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    
    # Investigación y análisis
    "https://www.ciperchile.cl/feed/",
    "https://interferencia.cl/feed/",
    
    # Gobierno y desarrollo
    "https://www.gob.cl/feed/",
    "https://www.hacienda.cl/feed/",
    "https://www.corfo.cl/feed/",
    "https://www.bcn.cl/rss",
    
    # Ciencia y universidades
    "https://www.uchile.cl/rss.xml",
    
    # Tecnología
    "https://www.fayerwayer.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/ciencia-y-tecnologia/feed/",
    
    # Noticias sobre Chile desde afuera
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/chile/portada",
    "https://en.mercopress.com/rss/chile",
]


# Palabras clave de avances
KEYWORDS = [
    # Economía
    "inversión", "millones", "crecimiento", "exportación",
    "acuerdo", "contrato", "financiamiento", "fondo",
    # Infraestructura
    "inauguración", "construcción", "obra", "proyecto",
    "hospital", "metro", "carretera", "puerto",
    # Tecnología e innovación
    "innovación", "tecnología", "startup", "digital",
    "energía", "solar", "hidrógeno", "litio", "cobre",
    # Internacional
    "alianza", "tratado", "cooperación", "embajada",
    # Ciencia
    "descubrimiento", "investigación", "universidad",
    # General positivo
    "récord", "avance", "logro", "histórico", "beneficio" KEYWORDS = [
    "hidrogeno", "litio", "startup", "innovacion", "tecnologia",
    "inteligencia artificial", "energia", "inversion", "infraestructura",
    "exportaciones", "mineria", "ciencia", "desarrollo"

]


def obtener_noticias():
    noticias = []
    for url in FUENTES:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            titulo = entry.title.lower()
            if any(k in titulo for k in KEYWORDS):
                noticias.append({
                    "titulo": entry.title,
                    "link": entry.link
                })
    return noticias

def generar_post(noticia):
    cliente = Groq(api_key=GROQ_API_KEY)
    prompt = f"""
Eres un editor de un perfil de Twitter llamado Chile Avanza.
Tu criterio: solo publicas avances concretos que benefician a Chile, sin tinte político.
Tono: optimista y motivador.

Noticia: {noticia['titulo']}
Fuente: {noticia['link']}

Genera un post para Twitter de máximo 280 caracteres con:
- Emoji relevante al inicio
- El hecho concreto
- Por qué importa para Chile
- El link al final
- Hashtag #ChileAvanza al final

Solo responde con el post, nada más.
"""
    respuesta = cliente.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}]
    )
    return respuesta.choices[0].message.content

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    })

def main():
    enviar_telegram("🤖 Bot iniciado, buscando noticias...")
    noticias_vistas = []
    for url in FUENTES:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            noticias_vistas.append(entry.title)
    
    if noticias_vistas:
        mensaje = "📋 Títulos encontrados:\n\n" + "\n".join(noticias_vistas[:10])
        enviar_telegram(mensaje)
    else:
        enviar_telegram("❌ No se pudo leer ningún RSS feed.")

if __name__ == "__main__":
    main()
