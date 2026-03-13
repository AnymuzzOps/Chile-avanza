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
    "https://www.df.cl/feed",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    "https://www.ciperchile.cl/feed/",
    "https://interferencia.cl/feed/",
    "https://www.gob.cl/feed/",
    "https://www.hacienda.cl/feed/",
    "https://www.corfo.cl/feed/",
    "https://www.bcn.cl/rss",
    "https://www.uchile.cl/rss.xml",
    "https://www.fayerwayer.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/ciencia-y-tecnologia/feed/",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/chile/portada",
    "https://en.mercopress.com/rss/chile",
]

KEYWORDS = [
    "inversión", "millones", "crecimiento", "exportación",
    "acuerdo", "contrato", "financiamiento", "fondo",
    "inauguración", "construcción", "obra", "proyecto",
    "hospital", "metro", "carretera", "puerto",
    "innovación", "tecnología", "startup", "digital",
    "energía", "solar", "hidrógeno", "litio", "cobre",
    "alianza", "tratado", "cooperación", "embajada",
    "descubrimiento", "investigación", "universidad",
    "récord", "avance", "logro", "histórico", "beneficio",
    "hidrogeno", "innovacion", "tecnologia",
    "inteligencia artificial", "energia", "inversion",
    "infraestructura", "exportaciones", "mineria",
    "ciencia", "desarrollo"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ChileAvanzaBot/1.0; +https://github.com/tuusuario/turepo)"
}


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje
        }, timeout=15)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")


def leer_feed(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except requests.RequestException as e:
        print(f"Error leyendo {url}: {e}")
        return None
    except Exception as e:
        print(f"Error inesperado en {url}: {e}")
        return None


def obtener_noticias():
    noticias = []
    for url in FUENTES:
        feed = leer_feed(url)
        if not feed:
            continue

        for entry in feed.entries[:5]:
            titulo = getattr(entry, "title", "").lower()
            if any(k in titulo for k in KEYWORDS):
                noticias.append({
                    "titulo": getattr(entry, "title", "Sin título"),
                    "link": getattr(entry, "link", url)
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
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return respuesta.choices[0].message.content


def main():
    enviar_telegram("🤖 Bot Chile Avanza iniciado.")

    try:
        noticias = obtener_noticias()
    except Exception as e:
        enviar_telegram(f"❌ Error obteniendo noticias:\n{e}")
        return

    if not noticias:
        enviar_telegram("⚠️ Sin noticias relevantes hoy.")
        return

    for noticia in noticias[:3]:
        try:
            post = generar_post(noticia)
            enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")
        except Exception as e:
            enviar_telegram(f"❌ Error generando post:\n{e}")

if __name__ == "__main__":
    main()
