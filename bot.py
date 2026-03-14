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
MAX_NOTICIAS_POR_FEED = 20
MAX_NOTICIAS_A_PROCESAR = 8


# Fuentes RSS verificadas y funcionando + adicionales
FUENTES = [
    # Chile - medios verificados 2026
    "https://www.theclinic.cl/feed/",
    "https://www.cambio21.cl/rss",
    "https://www.lanacion.cl/feed/",
    "https://www.santiagotimes.cl/feed/",
    "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.ex-ante.cl/feed/",
    "https://www.fayerwayer.com/feed/",
    "https://cooperativa.cl/noticias/economia/rss/noticias.xml",
    "https://cooperativa.cl/noticias/negocios/rss/noticias.xml",
    "https://en.mercopress.com/rss/chile",
    "https://en.mercopress.com/rss/economy",
    # Internacional sobre Chile y Latinoamerica
    "https://feeds.bbci.co.uk/mundo/rss.xml",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada",
    "https://www.americaeconomia.com/rss.xml",
    # Economia y negocios global
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.bloomberg.com/technology/news.rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # Tecnologia e innovacion
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    # Ciencia
    "https://phys.org/rss-feed/",
    "https://futurism.com/feed",
    # Mineria y energia (internacional)
    "https://www.mining.com/feed/",
    "https://oilprice.com/rss/main",
    # Extras para mejorar cobertura en Chile
    "https://www.df.cl/feed",
    "https://www.pulso.cl/feed/",
    "https://www.biobiochile.cl/lista/categoria/economia-y-negocios/feed/",
    "https://www.mch.cl/feed/",
    "https://www.startupchile.org/feed/",
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
    "guerra",
    "fraude",
    "escándalo",
    "escandalo",
    "sopaipillas",
    "panoramas",
    "que hacer",
    "fin de semana",
    "terremoto",
    "historia",
    "tradicion",
    "sandwich",
    "pronostico",
    "forecast",
    "indulto",
    "subsidio vivienda",
    "ketamina",
    "marihuana",
    "incautacion",
    "carabineros",
}

POSITIVOS_FUERTES = {
    "inversión",
    "inversion",
    "millones",
    "acuerdo",
    "proyecto",
    "innovación",
    "innovacion",
    "récord",
    "record",
    "exportación",
    "exportacion",
    "crecimiento",
    "alianza",
    "avance",
    "descubrimiento",
    "histórico",
    "historico",
    "energía",
    "energia",
    "litio",
    "cobre",
    "startup",
    "ia",
    "inteligencia artificial",
    "hidrógeno",
    "hidrogeno",
    "lanzó",
    "firmó",
    "anunció",
    "aprobó",
    "inauguró",
    "alcanzó",
    "superó",
    "logró",
    "obtuvo",
    "construirá",
    "invertirá",
    "lanzo",
    "firmo",
    "aprobo",
    "inauguro",
    "alcanzo",
    "supero",
    "logro",
    "invertira",
    "construira",
    "acuerdo comercial",
    "millones de dolares",
    "exportaciones chilenas",
    "salmon",
    "celulosa",
    "puerto",
    "corredor",
}

POSITIVOS_MODERADOS = {
    "nuevo",
    "nueva",
    "expansión",
    "expansion",
    "apertura",
    "anuncia",
    "lanzan",
    "implementa",
    "desarrollo",
    "tecnología",
    "tecnologia",
    "investigación",
    "investigacion",
    "infraestructura",
    "planta",
    "producción",
    "produccion",
}

PALABRAS_CHILE_RELEVANTE = {
    "chile",
    "chileno",
    "chilena",
    "litio",
    "cobre",
    "codelco",
    "enap",
    "corfo",
    "banco central",
    "minsal",
    "atacama",
    "patagonia",
    "exportaciones",
    "peso chileno",
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


def _score_titulo(titulo: str) -> int:
    titulo_normalizado = titulo.lower()
    if any(token in titulo_normalizado for token in NEGATIVOS):
        return -10

    score = 0
    score += sum(2 for token in POSITIVOS_FUERTES if token in titulo_normalizado)
    score += sum(1 for token in POSITIVOS_MODERADOS if token in titulo_normalizado)

    if any(token in titulo_normalizado for token in PALABRAS_CHILE_RELEVANTE):
        score += 3

    return score


def _es_titulo_candidato(titulo: str) -> bool:
    # Umbral reforzado para priorizar relevancia y reducir llamadas a IA.
    return _score_titulo(titulo) >= 3


def obtener_noticias() -> List[Dict[str, str]]:
    noticias: List[Dict[str, str]] = []
    vistos: Set[str] = set()

    for url in FUENTES:
        try:
            response = requests.get(url, headers=HEADERS, timeout=12)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if getattr(feed, "bozo", False):
                logger.warning("Feed con formato irregular: %s", url)

            for entry in feed.entries[:MAX_NOTICIAS_POR_FEED]:
                titulo = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if not titulo or not link or link in vistos:
                    continue
                if _es_titulo_candidato(titulo):
                    noticias.append({"titulo": titulo, "link": link})
                    vistos.add(link)
        except (requests.RequestException, ValueError) as error:
            logger.warning("Error con %s: %s", url, error)
            continue

    noticias.sort(key=lambda item: _score_titulo(item["titulo"]), reverse=True)
    logger.info("Total de noticias candidatas: %s", len(noticias))
    return noticias


def es_avance_positivo(cliente: Groq, titulo: str) -> bool:
    prompt = f"""Eres un filtro editorial estricto del perfil @ElChilometro en Twitter.
Pregunta central obligatoria: ¿Esta noticia representa un beneficio directo o indirecto concreto para Chile o los chilenos?

Aprueba SOLO si el titular muestra un hecho real y verificable, como:
- inversión en Chile o en un sector chileno clave
- acuerdo comercial firmado
- proyecto con cifras reales
- tecnología o innovación adoptada en Chile
- logro económico medible
- avance global con impacto directo en Chile (minería, litio, cobre, energía, exportaciones)

Rechaza explícitamente si el titular trata de:
- política interna sin impacto económico concreto
- turismo, gastronomía, historia, clima o policiales
- noticias de otros países sin relación con Chile
- potencial, posibilidades o escenarios hipotéticos sin anuncio concreto
- cualquier caso donde el beneficio para Chile sea especulativo

Noticia: "{titulo}"

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
Tono: directo, afirmativo e informativo.

Noticia: {noticia['titulo']}
Link: {noticia['link']}

Genera un post para Twitter de máximo 280 caracteres con:
- Un emoji relevante al inicio
- El hecho concreto en una línea
- Una línea explicando por qué beneficia a Chile o a los chilenos
- Usa solo hechos concretos que aparezcan en el título
- Si el título contiene cifras, nombres, fechas o montos, inclúyelos
- Prohibido usar frases especulativas: "puede", "podría", "es posible", "potencial"
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
    noticias_seleccionadas = noticias_nuevas[:MAX_NOTICIAS_A_PROCESAR]
    enviar_telegram(f"🧮 Candidatas nuevas detectadas: {len(noticias_nuevas)}. Procesando {len(noticias_seleccionadas)}.")

    for noticia in noticias_seleccionadas:
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
