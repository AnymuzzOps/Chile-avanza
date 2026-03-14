import logging
import os
import subprocess
from typing import Dict, List, Set

import feedparser
import requests
from groq import Groq


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("elchilometro-bot")


# Configuración
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_IDS = [
    os.environ["TELEGRAM_CHAT_ID"],
    os.environ.get("TELEGRAM_CHAT_ID_2", "").strip(),
]
TELEGRAM_CHAT_IDS = [chat_id for chat_id in TELEGRAM_CHAT_IDS if chat_id]
MAX_NOTICIAS_POR_FEED = 15
MAX_NOTICIAS_A_PROCESAR = 5


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
    "https://www.cnnchile.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/nacional/feed/",
    # Economía y negocios
    "https://www.df.cl/feed",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    "https://www.estrategia.cl/feed/",
    "https://www.ex-ante.cl/feed/",
    "https://www.pauta.cl/feed/",
    # Gobierno y desarrollo
    "https://www.gob.cl/feed/",
    "https://www.hacienda.cl/feed/",
    "https://www.corfo.cl/feed/",
    "https://www.bcn.cl/rss",
    "https://www.prochile.gob.cl/feed/",
    "https://www.sernac.cl/feed/",
    # Minería y energía
    "https://www.mineria.cl/feed/",
    "https://www.cochilco.cl/feed/",
    "https://www.energiaabierta.cl/feed/",
    "https://www.mch.cl/feed/",
    "https://www.revistaei.cl/feed/",
    # Tecnología y ciencia
    "https://www.fayerwayer.com/feed/",
    "https://www.biobiochile.cl/lista/categoria/ciencia-y-tecnologia/feed/",
    "https://www.startupchile.org/feed/",
    "https://www.uchile.cl/rss.xml",
    "https://www.puc.cl/rss.xml",
    "https://www.usach.cl/rss.xml",
    # Internacional sobre Chile
    "https://en.mercopress.com/rss/chile",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/chile/portada",
    "https://www.reuters.com/rssFeed/businessNews",
    "https://feeds.bloomberg.com/markets/news.rss",
]

NEGATIVOS = {
    "muerto",
    "herido",
    "accidente",
    "crimen",
    "detenido",
    "imputado",
    "violencia",
    "ataque",
    "incendio",
    "robo",
    "homicidio",
    "tragedia",
}

POSITIVOS = {
    "inversión",
    "millones",
    "acuerdo",
    "inauguró",
    "proyecto",
    "innovación",
    "récord",
    "exportación",
    "crecimiento",
    "alianza",
    "avance",
    "descubrimiento",
    "nuevo",
    "histórico",
    "energía",
    "litio",
    "cobre",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElChilometroBot/1.0)"}
GROQ_MODEL = "llama-3.3-70b-versatile"


def enviar_telegram(mensaje: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "text": mensaje},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.exception("Error enviando a chat_id=%s: %s", chat_id, error)


def _es_titulo_positivo(titulo: str) -> bool:
    titulo_normalizado = titulo.lower()
    if any(token in titulo_normalizado for token in NEGATIVOS):
        return False
    return any(token in titulo_normalizado for token in POSITIVOS)


def obtener_noticias() -> List[Dict[str, str]]:
    noticias: List[Dict[str, str]] = []
    vistos: Set[str] = set()

    for url in FUENTES:
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if getattr(feed, "bozo", False):
                logger.warning("Feed con formato irregular: %s", url)

            for entry in feed.entries[:MAX_NOTICIAS_POR_FEED]:
                titulo = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if not titulo or not link or link in vistos:
                    continue
                if _es_titulo_positivo(titulo):
                    noticias.append({"titulo": titulo, "link": link})
                    vistos.add(link)
        except (requests.RequestException, ValueError) as error:
            logger.warning("Error con %s: %s", url, error)
            continue

    return noticias


def es_avance_positivo(cliente: Groq, titulo: str) -> bool:
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

Noticia: \"{titulo}\"

Responde SOLO con SÍ o NO, sin explicación."""
    respuesta = cliente.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    resultado = respuesta.choices[0].message.content.strip().upper()
    return resultado.startswith("SÍ")


def generar_post(cliente: Groq, noticia: Dict[str, str]) -> str:
    prompt = f"""Eres el editor de @ElChilometro, perfil que registra avances concretos de Chile.
Tono: formal, informativo, sin exceso de emojis.

Noticia: {noticia['titulo']}
Link: {noticia['link']}

Genera un post para Twitter de máximo 280 caracteres con:
- Un emoji relevante al inicio
- El hecho concreto en una línea
- Por qué importa para Chile
- Fuente: [nombre del medio] al final
- Sin hashtags
- Incluye el link al final antes de la fuente

Solo responde con el post, nada más."""
    respuesta = cliente.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}],
    )
    return respuesta.choices[0].message.content.strip()


def cargar_procesadas() -> Set[str]:
    try:
        with open("procesadas.txt", "r", encoding="utf-8") as file:
            return {linea.strip() for linea in file if linea.strip()}
    except FileNotFoundError:
        return set()


def guardar_procesadas(procesadas: Set[str]) -> None:
    with open("procesadas.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(sorted(procesadas)))

    subprocess.run(["git", "config", "user.email", "bot@elchilometro.cl"], check=True)
    subprocess.run(["git", "config", "user.name", "ElChilometro Bot"], check=True)
    subprocess.run(["git", "add", "procesadas.txt"], check=True)

    estado = subprocess.run(
        ["git", "status", "--porcelain", "procesadas.txt"],
        check=True,
        capture_output=True,
        text=True,
    )
    if not estado.stdout.strip():
        logger.info("Sin cambios en procesadas.txt; se omite commit.")
        return

    subprocess.run(["git", "commit", "-m", "Update procesadas"], check=True)
    subprocess.run(["git", "push"], check=True)


def main() -> None:
    enviar_telegram("📡 ElChilometro iniciado.")
    cliente = Groq(api_key=GROQ_API_KEY)

    try:
        noticias = obtener_noticias()
    except Exception as error:
        enviar_telegram(f"❌ Error obteniendo noticias:\n{error}")
        return

    if not noticias:
        enviar_telegram("⚠️ Sin noticias relevantes hoy.")
        return

    procesadas = cargar_procesadas()
    noticias_nuevas = [noticia for noticia in noticias if noticia["link"] not in procesadas]

    if not noticias_nuevas:
        enviar_telegram("⚠️ Sin noticias nuevas, todas ya procesadas.")
        return

    links_nuevos: Set[str] = set()
    for noticia in noticias_nuevas[:MAX_NOTICIAS_A_PROCESAR]:
        try:
            decision = es_avance_positivo(cliente, noticia["titulo"])
            if decision:
                post = generar_post(cliente, noticia)
                enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")
            else:
                enviar_telegram(f"❌ DESCARTADO:\n{noticia['titulo']}")
            links_nuevos.add(noticia["link"])
        except Exception as error:
            enviar_telegram(f"❌ Error generando post:\n{error}")
            links_nuevos.add(noticia["link"])

    guardar_procesadas(procesadas | links_nuevos)


if __name__ == "__main__":
    main()
