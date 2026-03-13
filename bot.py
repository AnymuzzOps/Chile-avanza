import os
import feedparser
import requests
import subprocess
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
    "https://www.cnnchile.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/nacional/feed/",
    "https://www.df.cl/feed",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    "https://www.gob.cl/feed/",
    "https://www.hacienda.cl/feed/",
    "https://www.corfo.cl/feed/",
    "https://www.bcn.cl/rss",
    "https://www.mineria.cl/feed/",
    "https://www.cochilco.cl/feed/",
    "https://www.energiaabierta.cl/feed/",
    "https://www.fayerwayer.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/ciencia-y-tecnologia/feed/",
    "https://www.startupchile.org/feed/",
    "https://www.uchile.cl/rss.xml",
    "https://en.mercopress.com/rss/chile",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/chile/portada",
]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje
        }, timeout=15)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def obtener_noticias():
    noticias = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ElChilometroBot/1.0)"}
    for url in FUENTES:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:15]:
                titulo = entry.title.lower()
                negativos = [
                    "muerto", "herido", "accidente", "crimen",
                    "detenido", "imputado", "violencia", "ataque",
                    "incendio", "robo", "homicidio", "tragedia"
                ]
                if any(n in titulo for n in negativos):
                    continue
                positivos = [
                    "inversión", "millones", "acuerdo", "inauguró",
                    "proyecto", "innovación", "récord", "exportación",
                    "crecimiento", "alianza", "avance", "descubrimiento",
                    "nuevo", "histórico", "energía", "litio", "cobre"
                ]
                if any(p in titulo for p in positivos):
                    noticias.append({
                        "titulo": entry.title,
                        "link": entry.link
                    })
        except Exception as e:
            print(f"Error con {url}: {e}")
            continue
    return noticias

def es_avance_positivo(titulo):
    cliente = Groq(api_key=GROQ_API_KEY)
    prompt = f"""Eres un filtro editorial estricto del perfil @ElChilometro en Twitter.
Tu única tarea es evaluar si una noticia representa un avance concreto y positivo para Chile.

Criterios para decir SÍ:
- Inversiones, acuerdos comerciales, proyectos nuevos
- Infraestructura, tecnología, energía, innovación
- Logros científicos, récords económicos
- Acuerdos internacionales beneficiosos

Criterios para decir NO:
- Noticias políticas sin impacto concreto
- Declaraciones, opiniones o discursos
- Conflictos, violencia, escándalos
- Noticias negativas o neutras

Noticia: "{titulo}"

Responde SOLO con SÍ o NO, sin explicación."""
    respuesta = cliente.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    resultado = respuesta.choices[0].message.content.strip().upper()
    return "SÍ" in resultado

def generar_post(noticia):
    cliente = Groq(api_key=GROQ_API_KEY)
    prompt = f"""Eres el editor de @ElChilometro, perfil que registra avances concretos de Chile.
Tono: formal, informativo, sin exceso de emojis.

Noticia: {noticia['titulo']}

Genera un post para Twitter de máximo 280 caracteres con:
- Un emoji relevante al inicio
- El hecho concreto en una línea
- Por qué importa para Chile
- Fuente: [nombre del medio] al final
- Sin hashtags

Solo responde con el post, nada más."""
    respuesta = cliente.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return respuesta.choices[0].message.content

def cargar_procesadas():
    try:
        with open("procesadas.txt", "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def guardar_procesadas(procesadas):
    with open("procesadas.txt", "w") as f:
        f.write("\n".join(procesadas))
    subprocess.run(["git", "config", "user.email", "bot@elchilometro.cl"])
    subprocess.run(["git", "config", "user.name", "ElChilometro Bot"])
    subprocess.run(["git", "add", "procesadas.txt"])
    subprocess.run(["git", "commit", "-m", "Update procesadas"])
    subprocess.run(["git", "push"])

def main():
    enviar_telegram("📡 ElChilometro iniciado.")
    try:
        noticias = obtener_noticias()
    except Exception as e:
        enviar_telegram(f"❌ Error obteniendo noticias:\n{e}")
        return

    if not noticias:
        enviar_telegram("⚠️ Sin noticias relevantes hoy.")
        return

    procesadas = cargar_procesadas()
    noticias_nuevas = [n for n in noticias if n["link"] not in procesadas]

    if not noticias_nuevas:
        enviar_telegram("⚠️ Sin noticias nuevas, todas ya procesadas.")
        return

    links_nuevos = set()
    for noticia in noticias_nuevas[:5]:
        try:
            if es_avance_positivo(noticia["titulo"]):
                post = generar_post(noticia)
                enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")
            links_nuevos.add(noticia["link"])
        except Exception as e:
            enviar_telegram(f"❌ Error generando post:\n{e}")

    guardar_procesadas(procesadas | links_nuevos)

if __name__ == "__main__":
    main()
