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
    "https://www.biobiochile.cl/lista/categorias/noticias/feed",
    "https://www.latercera.com/feed/",
    "https://www.df.cl/feed/",
    "https://www.emol.com/rss/Economia.xml",
    "https://www.elmostrador.cl/feed/",
]

# Palabras clave de avances
KEYWORDS = [
    "inversión", "acuerdo", "inauguración", "récord",
    "exportación", "innovación", "infraestructura",
    "descubrimiento", "crecimiento", "alianza",
    "millones", "proyecto", "desarrollo", "avance"
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
    enviar_telegram("🤖 Bot Chile Avanza iniciado correctamente.")
    noticias = obtener_noticias()
    if not noticias:
        enviar_telegram("⚠️ Bot activo pero sin noticias relevantes hoy.")
        return
    for noticia in noticias[:3]:
        post = generar_post(noticia)
        enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")

if _name_ == "_main_":
    main()
