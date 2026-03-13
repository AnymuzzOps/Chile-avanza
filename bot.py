import os
import feedparser
import requests
from groq import Groq

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

cliente = Groq(api_key=GROQ_API_KEY)

FUENTES = [
    "https://www.biobiochile.cl/feed/",
    "https://www.emol.com/rss/",
    "https://www.latercera.com/feed/",
    "https://www.elmostrador.cl/feed/",
]

KEYWORDS = [
    "inversión","acuerdo","inauguración","récord",
    "exportación","innovación","infraestructura",
    "descubrimiento","crecimiento","alianza"
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
    prompt = f"""
Eres editor de Twitter de Chile Avanza.
Publicas avances concretos que benefician al país.

Noticia: {noticia['titulo']}
Fuente: {noticia['link']}

Genera un tweet de máximo 280 caracteres.
Emoji al inicio.
Explica por qué es positivo para Chile.
Incluye el link.
Termina con #ChileAvanza
"""

    respuesta = cliente.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role":"user","content":prompt}]
    )

    return respuesta.choices[0].message.content

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje[:4000]
    })

def main():
    noticias = obtener_noticias()

    if not noticias:
        print("No hay noticias relevantes.")
        return

    for noticia in noticias[:3]:
        post = generar_post(noticia)
        enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")

if __name__ == "__main__":
    main()
