import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

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
MAX_EVALUACIONES_IA = 20
MAX_MUESTRAS_DIAGNOSTICO = 5
MAX_CARACTERES_POST = 260


# Fuentes RSS verificadas y funcionando + adicionales
FUENTES = [
    # Chile: economía, inversión, minería, energía, tecnología e innovación
    "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.ex-ante.cl/feed/",
    "https://www.theclinic.cl/feed/",
    "https://www.cambio21.cl/rss",
    "https://www.lanacion.cl/feed/",
    "https://www.fayerwayer.com/feed/",
    "https://www.startupchile.org/feed/",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    "https://www.corfo.cl/feed/",
    # Internacional en español con cobertura frecuente de Chile y su economía
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/chile/portada",
    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
    "https://www.minsal.cl/feed/",
    "https://www.mineduc.cl/feed/",
    "https://www.conicyt.cl/feed/",
    "https://www.anid.cl/feed/",
    "https://www.bcn.cl/rss",
]

FUENTES_CHILE = {
    "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://www.ex-ante.cl/feed/",
    "https://www.theclinic.cl/feed/",
    "https://www.cambio21.cl/rss",
    "https://www.lanacion.cl/feed/",
    "https://www.fayerwayer.com/feed/",
    "https://www.startupchile.org/feed/",
    "https://www.pulso.cl/feed/",
    "https://www.americaeconomia.com/rss.xml",
    "https://www.corfo.cl/feed/",
    "https://www.minsal.cl/feed/",
    "https://www.mineduc.cl/feed/",
    "https://www.conicyt.cl/feed/",
    "https://www.anid.cl/feed/",
    "https://www.bcn.cl/rss",
}

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
    "sopaipilla",
    "receta",
    "turistico",
    "turismo",
    "restaurante",
    "cocina",
    "gastronomia",
    "centolla",
    "merluza",
    "copa chile",
    "futbol",
    "gol",
    "partido",
    "clasificacion",
    "dormir",
    "dieta",
    "lugares para",
    "temblor",
    "sismo",
    "epicentro",
    "magnitud",
    "oscar",
    "ceremonia",
    "alfombra roja",
    "kast",
    "boric",
    "inauguracion",
    "asume",
    "sworn",
    "presidente electo",
    "migrantes",
    "venezolanos",
    "inmigracion",
    "nueva era",
    "giro conservador",
    "100 dias",
    "90 dias",
    "plan de gobierno",
    "lollapalooza",
    "concierto",
    "festival",
    "escenario",
    "fanaticada",
    "album",
    "debut musical",
    "zelensky",
    "rusia",
    "iran",
    "medio oriente",
    "ucrania",
    "india",
    "california",
    "indonesia",
    "malaysia",
    "greece",
    "greek",
    "strait of hormuz",
    "black sea",
    "narco",
    "extradicion",
    "extradited",
    "capturan",
    "fugado",
    "rosalia",
    "picasso",
    "chef",
    "renuncia",
    "obituario",
    "muere",
    "dies",
    "fallecio",
    "entrada",
    "entradas",
    "venta de entradas",
    "charlas",
    "arte",
    "cultura",
    "concierto",
    "felicidad",
    "infeliz",
    "estudio ipsos",
    "quiebra",
    "reorganización",
    "reorganizacion",
    "luminarias",
    "soda stereo",
    "chuck norris",
    "kevin spacey",
    "gago",
    "técnico",
    "tecnico",
    "entrenador",
    "copa libertadores",
    "sorteo",
    "curanto",
    "tunas",
    "aceite de oliva",
    "campesina",
    "trenzas",
    "chorizo",
    "horizon worlds",
    "metaverso",
    "hospitalizado",
    "acuerdo extrajudicial",
    "agresión",
    "agresion",
    "youtube millones",
    "industria musical",
    "cancelación",
    "cancelacion",
    "universidad la república",
    "universidad la republica",
    "personalidad jurídica",
    "personalidad juridica",
    "tren valparaíso",
    "tren valparaiso",
    "anhelo ciudadano",
    "parlamentarios",
    "cuba",
    "convoy",
    "humanitaria",
    "publirreportaje",
    "publi",
    "lugares turísticos",
    "lugares turisticos",
    "gastronomía chilota",
    "gastronomia chilota",
    "tradición campesina",
    "tradicion campesina",
    "papa nativa",
    "dalcahue",
    "til til",
    "investigadores chilenos reciben",
    "mepco",
    "senadora",
    "ministra duco",
    "jj.oo",
    "juegos olimpicos juventud",
    "migraciones penalizar",
    "extranjeros irregulares",
    "copa de la liga",
    "nuevo torneo",
    "lluvia hoy",
    "milimetros de agua",
    "comenzó el otoño",
    "comenzo el otono",
    "mujeres que transforman",
    "rating del jueves",
    "rating del lunes",
    "rating del martes",
    "rating del miercoles",
    "rating del miércoles",
    "rating del viernes",
    "como le fue a chv",
    "senapred",
    "perimetro de seguridad",
    "alerta temprana",
    "jeff bezos",
    "bezos",
    "fabricacion con ia",
    "fondo dedicado",
    "muertes en chile",
    "mortalidad",
    "comunas del sur lideran",
    "una de cada cuatro",
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
    "hospital",
    "clinica",
    "beca",
    "gratuito",
    "gratuita",
    "ley aprobada",
    "promulgada",
    "beneficio",
    "subsidio",
    "bonificacion",
    "pension",
    "jubilacion",
    "medicamento",
    "vacuna",
    "programa social",
    "vivienda social",
    "area protegida",
    "parque nacional",
    "ciclovía",
    "metro",
    "tren",
    "conservación",
    "conservacion",
    "biodiversidad",
    "reforestación",
    "reforestacion",
    "restauración ecológica",
    "restauracion ecologica",
    "área protegida",
    "area protegida",
    "humedal",
    "especie protegida",
    "nidificación",
    "nidificacion",
    "reserva nacional",
    "fauna",
    "flora",
    "reconocimiento internacional",
    "reconocimiento",
    "premio",
    "investigadores chilenos",
    "científicos chilenos",
    "cientificos chilenos",
    "avance en inteligencia artificial",
    "avance científico",
    "avance cientifico",
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
    "investigadores",
    "científicos",
    "cientificos",
    "reconocimiento",
    "avance",
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
    "conaf",
    "sernapesca",
    "parque nacional",
    "área protegida",
    "area protegida",
    "lauca",
    "torres del paine",
    "chiloé",
    "chiloe",
}

PALABRAS_CHILE_ESTRICTAS = {
    "chile",
    "chileno",
    "chilena",
    "codelco",
    "enap",
    "corfo",
    "sernageomin",
    "cochilco",
    "hacienda",
    "prochile",
    "conaf",
    "sernapesca",
    "santiago",
    "antofagasta",
    "atacama",
    "valparaíso",
    "valparaiso",
    "biobío",
    "biobio",
    "lauca",
    "torres del paine",
    "chiloé",
    "chiloe",
    "sky airline",
    "latam",
}

PALABRAS_INVERSION_BENEFICIO = {
    "inversión",
    "inversion",
    "invertirá",
    "invertira",
    "millones",
    "acuerdo",
    "acuerdo comercial",
    "proyecto",
    "inauguró",
    "inauguro",
    "aprobó",
    "aprobo",
    "exportación",
    "exportacion",
    "empleo",
    "crecimiento",
    "expansión",
    "expansion",
    "beneficio",
    "subsidio",
    "programa",
    "presupuesto",
    "licitación",
    "licitacion",
    "hospital",
    "clinica",
    "medicamento",
    "vacuna",
    "beca",
    "gratuito",
    "gratuita",
    "metro",
    "tren",
    "ley aprobada",
    "promulgada",
    "vivienda social",
    "parque nacional",
    "area protegida",
    "conservación",
    "conservacion",
    "biodiversidad",
    "humedal",
    "reforestación",
    "reforestacion",
    "restauración",
    "restauracion",
    "fauna",
    "flora",
    "especie protegida",
    "nidificación",
    "nidificacion",
    "reserva nacional",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ElChilometroBot/1.0)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}
GROQ_MODEL = "llama-3.3-70b-versatile"

FALLBACK_FUENTES = {
    "https://www.pulso.cl/feed/": [
        "https://www.latercera.com/canal/pulso/feed/",
    ],
    "https://www.corfo.cl/feed/": [
        "https://www.corfo.cl/sites/cpp/feed",
    ],
}


def _cargar_prompt_editorial() -> str:
    rutas = [
        os.path.join(os.path.dirname(__file__), "Esto es el alma de elchilometro.txt"),
        "Esto es el alma de elchilometro.txt",
    ]
    for ruta in rutas:
        try:
            with open(ruta, "r", encoding="utf-8") as archivo:
                contenido = archivo.read().strip()
                if contenido:
                    return contenido
        except FileNotFoundError:
            continue
    return (
        "Actúa como redactor de El Chilómetro. "
        "Escribe en tono neutral, breve y basado en hechos. "
        "Prioriza un solo post. "
        "Si no cabe, usa hilo de 2 posts. "
        "Máximo 260 caracteres por post."
    )


PROMPT_EDITORIAL = _cargar_prompt_editorial()


def _extraer_fuente(link: str) -> str:
    netloc = urlparse(link).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if not netloc:
        return "Medio"

    nombre = netloc.split(".")[0].replace("-", " ").strip()
    return nombre.title() or "Medio"


def _recortar_texto(texto: str, max_len: int) -> str:
    texto = " ".join(texto.split())
    if len(texto) <= max_len:
        return texto
    if max_len <= 1:
        return texto[:max_len]
    return texto[: max_len - 1].rstrip(" ,;:-") + "…"


def _split_posts(post: str) -> List[str]:
    bloques = [bloque.strip() for bloque in re.split(r"\n\s*\n", post.strip()) if bloque.strip()]
    return bloques[:2] if bloques else []


def _limpiar_linea(linea: str) -> str:
    linea = re.sub(r"\s+", " ", (linea or "").strip())
    linea = re.sub(r"\s+([,.;:])", r"\1", linea)
    return linea.strip()


def _contar_post(post: str) -> int:
    return len(post)


def _formatear_post_final(post: str) -> str:
    post = "\n".join(_limpiar_linea(linea) for linea in post.splitlines())
    post = re.sub(r"\n{3,}", "\n\n", post).strip()
    return f"{post} ({_contar_post(post)} caracteres)"


def _ajustar_post_individual(post: str, noticia: Dict[str, str]) -> str:
    fuente = _extraer_fuente(noticia["link"].strip())
    titulo = _limpiar_linea(noticia["titulo"])
    lineas = [_limpiar_linea(linea) for linea in post.splitlines() if _limpiar_linea(linea)]

    if not lineas:
        lineas = [titulo, fuente]

    texto_actual = "\n".join(lineas).lower()
    if fuente.lower() not in texto_actual:
        lineas.append(fuente)

    candidato = "\n".join(lineas)
    if len(candidato) <= MAX_CARACTERES_POST:
        return candidato

    while len(candidato) > MAX_CARACTERES_POST:
        idx = None
        largo = 0
        for i, linea in enumerate(lineas):
            if len(linea) > largo:
                idx = i
                largo = len(linea)
        if idx is None or largo < 18:
            break
        exceso = len(candidato) - MAX_CARACTERES_POST
        lineas[idx] = _recortar_texto(lineas[idx], max(18, len(lineas[idx]) - exceso - 2))
        candidato = "\n".join(lineas)

    if len(candidato) <= MAX_CARACTERES_POST:
        return candidato

    base = f"{_recortar_texto(titulo, max(20, MAX_CARACTERES_POST - len(fuente) - 1))}\n{fuente}"
    return base[:MAX_CARACTERES_POST]


def _ajustar_post_a_limite(post: str, noticia: Dict[str, str]) -> str:
    posts = _split_posts(post)
    if not posts:
        posts = [noticia["titulo"]]
    ajustados = [_formatear_post_final(_ajustar_post_individual(p, noticia)) for p in posts[:2]]
    return "\n\n".join(ajustados)


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
    return _score_titulo(titulo) >= 2


def _es_relevante_para_chile(titulo: str, fuente_base: str) -> bool:
    titulo_normalizado = titulo.lower()
    score = _score_titulo(titulo)
    tiene_chile = any(token in titulo_normalizado for token in PALABRAS_CHILE_ESTRICTAS)
    tiene_beneficio = any(token in titulo_normalizado for token in PALABRAS_INVERSION_BENEFICIO)
    tiene_contexto_chile = any(token in titulo_normalizado for token in PALABRAS_CHILE_RELEVANTE)

    # Caso ideal: señal directa de Chile + beneficio concreto.
    if tiene_chile and tiene_beneficio:
        return True

    # Si hay contexto Chile y score sólido, permitimos pasar el titular.
    if (tiene_chile or tiene_contexto_chile) and score >= 3:
        return True

    # Si viene de una fuente chilena, permitimos titulares de beneficio concreto
    # o titulares con score claramente alto para que Groq haga el filtro final.
    if fuente_base in FUENTES_CHILE and (tiene_beneficio or tiene_chile or tiene_contexto_chile or score >= 2):
        return True

    return False



def _razones_titulo(titulo: str, fuente_base: str) -> Tuple[int, List[str]]:
    titulo_normalizado = titulo.lower()
    score = _score_titulo(titulo)
    razones: List[str] = []

    if score < 0:
        razones.append("negativo")
    if score < 3:
        razones.append("score_bajo")

    tiene_chile = any(token in titulo_normalizado for token in PALABRAS_CHILE_ESTRICTAS)
    tiene_beneficio = any(token in titulo_normalizado for token in PALABRAS_INVERSION_BENEFICIO)
    tiene_contexto_chile = any(token in titulo_normalizado for token in PALABRAS_CHILE_RELEVANTE)

    if not _es_relevante_para_chile(titulo, fuente_base):
        if not (tiene_chile or tiene_contexto_chile):
            razones.append("sin_contexto_chile")
        if not tiene_beneficio and fuente_base not in FUENTES_CHILE:
            razones.append("sin_beneficio")
        if fuente_base in FUENTES_CHILE and not tiene_beneficio and score < 5:
            razones.append("fuente_chilena_insuficiente")

    return score, razones


def _resumen_diagnostico(stats: Dict[str, int], muestras: List[str]) -> str:
    partes = [
        f"entradas={stats['entradas_total']}",
        f"candidatas={stats['candidatas']}",
        f"duplicadas={stats['duplicadas']}",
        f"desc_negativo={stats['desc_negativo']}",
        f"desc_score={stats['desc_score']}",
        f"desc_chile={stats['desc_chile']}",
        f"fuentes_ok={stats['fuentes_total'] - stats['fuentes_error']}/{stats['fuentes_total']}",
    ]
    mensaje = "🔎 Diagnóstico filtro: " + ", ".join(partes) + "."
    if muestras:
        mensaje += "\nMuestras descartadas: " + " | ".join(muestras[:MAX_MUESTRAS_DIAGNOSTICO])
    return mensaje

def _normalizar_feed_content(content: bytes) -> bytes:
    # Algunos feeds llegan con bytes basura/BOM antes del XML y feedparser marca bozo.
    recortado = content.lstrip()
    for marca in (b"<?xml", b"<rss", b"<feed"):
        idx = recortado.find(marca)
        if idx > 0:
            recortado = recortado[idx:]
            break
    return recortado


def _parse_feed_desde_url(fuente: str) -> feedparser.FeedParserDict:
    # Fallback para servidores que rechazan ciertos headers (ej. HTTP 415).
    return feedparser.parse(fuente)


def _normalizar_titulo_duplicado(titulo: str) -> str:
    return re.sub(r"[^\w\s]", "", titulo.lower()).strip()


def _marca_titulo_procesado(titulo: str) -> str:
    return f"titulo::{_normalizar_titulo_duplicado(titulo)}"


def _extraer_resumen_entry(entry) -> str:
    resumen = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    resumen = re.sub(r"<[^>]+>", " ", resumen)
    return " ".join(resumen.split())


def _texto_contexto(titulo: str, resumen: str = "") -> str:
    return " ".join(part for part in [titulo or "", resumen or ""] if part).strip()


def obtener_noticias() -> tuple[List[Dict[str, str]], Dict[str, int], List[str]]:
    noticias: List[Dict[str, str]] = []
    vistos: Set[str] = set()
    titulos_vistos: Set[str] = set()

    errores_por_fuente = 0
    stats: Dict[str, int] = {
        "candidatas": 0,
        "fuentes_error": 0,
        "fuentes_total": len(FUENTES),
        "entradas_total": 0,
        "duplicadas": 0,
        "desc_negativo": 0,
        "desc_score": 0,
        "desc_chile": 0,
    }
    muestras_descartadas: List[str] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for url in FUENTES:
        urls_intento = [url, *FALLBACK_FUENTES.get(url, [])]
        feed_cargado = False
        ultimo_error = None

        for fuente in urls_intento:
            try:
                response = session.get(fuente, timeout=12)
                response.raise_for_status()
                feed = feedparser.parse(_normalizar_feed_content(response.content))

                if getattr(feed, "bozo", False):
                    if getattr(feed, "entries", []):
                        logger.info("Feed irregular pero usable: %s", fuente)
                    else:
                        logger.warning("Feed con formato irregular: %s", fuente)

                for entry in feed.entries[:MAX_NOTICIAS_POR_FEED]:
                    stats["entradas_total"] += 1
                    titulo = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    if not titulo or not link:
                        continue
                    titulo_normalizado = _normalizar_titulo_duplicado(titulo)
                    if link in vistos or titulo_normalizado in titulos_vistos:
                        stats["duplicadas"] += 1
                        continue

                    resumen = _extraer_resumen_entry(entry)
                    contexto = _texto_contexto(titulo, resumen)
                    score, razones = _razones_titulo(contexto, url)
                    if score < 0:
                        stats["desc_negativo"] += 1
                    elif score < 3:
                        stats["desc_score"] += 1
                    elif razones:
                        stats["desc_chile"] += 1

                    if score >= 2 and not razones:
                        noticias.append({"titulo": titulo, "link": link, "resumen": resumen})
                        vistos.add(link)
                        titulos_vistos.add(titulo_normalizado)
                    elif len(muestras_descartadas) < MAX_MUESTRAS_DIAGNOSTICO:
                        muestras_descartadas.append(f"{titulo} [{','.join(razones) or 'descartado'}]")

                if fuente != url:
                    logger.info("Fuente recuperada con fallback: %s -> %s", url, fuente)
                feed_cargado = True
                break
            except requests.HTTPError as error:
                # Algunos medios devuelven 415 por headers; intentamos parseo directo por URL.
                status_code = getattr(error.response, "status_code", None)
                if status_code == 415:
                    try:
                        feed = _parse_feed_desde_url(fuente)
                        if getattr(feed, "entries", []):
                            logger.info("Fuente recuperada sin headers (415): %s", fuente)
                            for entry in feed.entries[:MAX_NOTICIAS_POR_FEED]:
                                stats["entradas_total"] += 1
                                titulo = getattr(entry, "title", "").strip()
                                link = getattr(entry, "link", "").strip()
                                if not titulo or not link:
                                    continue
                                titulo_normalizado = _normalizar_titulo_duplicado(titulo)
                                if link in vistos or titulo_normalizado in titulos_vistos:
                                    stats["duplicadas"] += 1
                                    continue

                                resumen = _extraer_resumen_entry(entry)
                                contexto = _texto_contexto(titulo, resumen)
                                score, razones = _razones_titulo(contexto, url)
                                if score < 0:
                                    stats["desc_negativo"] += 1
                                elif score < 3:
                                    stats["desc_score"] += 1
                                elif razones:
                                    stats["desc_chile"] += 1

                                if score >= 2 and not razones:
                                    noticias.append({"titulo": titulo, "link": link, "resumen": resumen})
                                    vistos.add(link)
                                    titulos_vistos.add(titulo_normalizado)
                                elif len(muestras_descartadas) < MAX_MUESTRAS_DIAGNOSTICO:
                                    muestras_descartadas.append(f"{titulo} [{','.join(razones) or 'descartado'}]")
                            feed_cargado = True
                            break
                    except Exception as inner_error:  # noqa: BLE001
                        ultimo_error = inner_error
                        continue
                ultimo_error = error
            except (requests.RequestException, ValueError) as error:
                ultimo_error = error

        if not feed_cargado:
            errores_por_fuente += 1
            logger.warning(
                "Fuente sin respuesta útil (%s intentos): %s | último error: %s",
                len(urls_intento),
                url,
                ultimo_error,
            )

    noticias.sort(key=lambda item: _score_titulo(item["titulo"]), reverse=True)
    stats["candidatas"] = len(noticias)
    stats["fuentes_error"] = errores_por_fuente
    logger.info("Total de noticias candidatas: %s", stats["candidatas"])
    logger.info("Fuentes sin respuesta útil: %s/%s", stats["fuentes_error"], stats["fuentes_total"])
    return noticias, stats, muestras_descartadas


def _tiene_ingles_consecutivo(titulo: str) -> bool:
    palabras = [
        ''.join(ch for ch in token.lower() if ch.isalpha())
        for token in titulo.split()
    ]
    palabras = [p for p in palabras if p]
    ingles = {
        "the", "and", "with", "from", "for", "new", "launch", "startup", "service", "market",
        "agreement", "deal", "growth", "record", "wins", "award", "global", "tech", "business",
        "economy", "energy", "mining", "copper", "lithium", "in", "on", "to", "of", "by",
        "is", "are", "was", "were", "at", "or", "as", "after", "before", "first", "announces",
    }
    consecutivas = 0
    for palabra in palabras:
        if palabra in ingles:
            consecutivas += 1
            if consecutivas > 3:
                return True
        else:
            consecutivas = 0
    return False


def _groq_chat(cliente: Groq, prompt: str, temperature: float = 0, max_retries: int = 2) -> str:
    ultimo_error: Optional[Exception] = None
    for intento in range(max_retries + 1):
        try:
            respuesta = cliente.chat.completions.create(
                model=GROQ_MODEL,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return (respuesta.choices[0].message.content or "").strip()
        except Exception as error:
            ultimo_error = error
            logger.warning("Groq fallo intento %s/%s: %s", intento + 1, max_retries + 1, error)
            time.sleep(1.2 * (intento + 1))
    raise ultimo_error or RuntimeError("Groq sin respuesta")


def es_avance_positivo(cliente: Groq, titulo: str) -> bool:
    prompt = (
        "Eres un filtro editorial estricto del perfil @ElChilometro en Twitter.\n"
        "REGLA ABSOLUTA: Si la noticia no tiene un beneficio DIRECTO y CONCRETO para Chile o los chilenos con datos verificables, responde NO inmediatamente. No aprobar noticias de otros países sin relación directa con Chile, no aprobar noticias de entretenimiento, farándula, deportes locales, turismo, gastronomía o política sin proyecto concreto.\n"
        "Criterio único: ¿Esta noticia anuncia algo concreto y positivo que beneficia directamente a Chile o a los chilenos?\n\n"
        "Aprueba SOLO si el titular menciona explícitamente a Chile/chilenos o una institución/empresa chilena y además contiene un hecho económico concreto, por ejemplo:\n"
        "- inversión en Chile con cifras\n"
        "- proyecto inaugurado o aprobado en Chile\n"
        "- acuerdo comercial firmado que involucre a Chile\n"
        "- logro medible de un chileno o institución chilena\n"
        "- nuevo servicio o tecnología disponible en Chile\n"
        "- récord económico chileno medible\n"
        "- nuevos hospitales, centros de salud o medicamentos disponibles en Chile\n"
        "- leyes o decretos aprobados que beneficien directamente a ciudadanos chilenos\n"
        "- programas de becas o educación gratuita nuevos o ampliados\n"
        "- proyectos de infraestructura social inaugurados o aprobados con presupuesto\n"
        "- avances en medio ambiente o áreas protegidas en Chile\n"
        "- conservación de biodiversidad, fauna, flora o humedales en Chile\n"
        "- recuperación de especies, nidificación, reforestación o restauración ecológica en Chile\n"
        "- avances liderados por CONAF, Sernapesca u otras instituciones chilenas de protección ambiental\n"
        "- noticias con ubicación específica en Chile (por ejemplo Lauca, Torres del Paine, Chiloé) cuando describen un beneficio concreto\n"
        "- investigadores o instituciones chilenas que publican estudios en revistas científicas internacionales de alto impacto como Nature, Science o similares\n"
        "- premios, reconocimientos o galardones internacionales de alto prestigio obtenidos por chilenos o instituciones chilenas cuando el titular identifica claramente a la persona o institución\n"
        "- registros nacionales, plataformas o programas lanzados por organizaciones chilenas cuando entregan un beneficio social directo y concreto a los ciudadanos\n\n"
        "Rechaza todo lo demás, incluyendo:\n"
        "- noticias económicas de otros países sin impacto directo y explícito en Chile\n"
        "- política interna sin proyecto económico concreto\n"
        "- conflictos internacionales\n"
        "- deportes\n"
        "- farándula\n"
        "- gastronomía\n"
        "- turismo\n"
        "- clima\n"
        "- policiales\n"
        "- noticias de publirreportaje o contenido patrocinado\n"
        "- reconocimientos mencionados sin cifras ni impacto concreto\n"
        "- reconocimientos o premios genéricos sin institución, cifra o proyecto específico\n"
        "- noticias que mencionan 'reconocimiento', 'distinción' o 'galardón' sin especificar qué, quién y cuánto\n"
        "- noticias de universidades canceladas o instituciones cerradas\n"
        "- noticias de fracasos empresariales aunque sean de empresas tech\n"
        "- cualquier noticia donde Chile aparezca como receptor pasivo sin acción concreta\n"
        "- noticias en inglés\n\n"
        f'Noticia: "{titulo}"\n\n'
        "Responde SOLO con SÍ o NO, sin explicación."
    )
    resultado = _groq_chat(cliente, prompt, temperature=0).upper()
    return resultado.startswith("SÍ")


def generar_post(cliente: Groq, noticia: Dict[str, str]) -> str:
    contexto = noticia.get("resumen", "")
    prompt = (
        f"{PROMPT_EDITORIAL}\n\n"
        f"Título: {noticia['titulo']}\n"
        f"Resumen adicional: {contexto or 'No disponible'}\n"
        f"Link: {noticia['link']}\n\n"
        "Reglas extra para esta ejecución:\n"
        "1. No uses frases genéricas como 'beneficia a Chile', 'avance concreto' o 'impacto local' salvo que el título lo diga.\n"
        "2. No inventes datos ni contexto.\n"
        "3. Prioriza 1 solo post.\n"
        "4. Si haces hilo, usa solo 2 posts.\n"
        "5. Cada post debe quedar bajo 260 caracteres reales antes del conteo final.\n"
        "6. Usa como fuente el nombre breve del medio o entidad, no la URL completa salvo que sea imprescindible.\n"
        "7. Responde solo con la versión final lista para publicar."
    )
    respuesta = _groq_chat(cliente, prompt, temperature=0.2)
    return _ajustar_post_a_limite(respuesta, noticia)


def _ruta_procesadas() -> str:
    if os.path.isdir("/data"):
        return "/data/procesadas.txt"
    return "procesadas.txt"


def cargar_procesadas() -> Set[str]:
    try:
        with open(_ruta_procesadas(), "r", encoding="utf-8") as file:
            return {linea.strip() for linea in file if linea.strip()}
    except FileNotFoundError:
        return set()


def guardar_procesadas(procesadas: Set[str]) -> None:
    with open(_ruta_procesadas(), "w", encoding="utf-8") as file:
        file.write("\n".join(sorted(procesadas)))

    if not shutil.which("git"):
        logger.info("git no disponible; %s guardado solo localmente.", _ruta_procesadas())
        return

    try:
        subprocess.run(["git", "config", "user.email", "bot@elchilometro.cl"], check=True)
        subprocess.run(["git", "config", "user.name", "ElChilometro Bot"], check=True)
        subprocess.run(["git", "add", _ruta_procesadas()], check=True)

        estado = subprocess.run(
            ["git", "status", "--porcelain", _ruta_procesadas()],
            check=True, capture_output=True, text=True,
        )
        if not estado.stdout.strip():
            logger.info("Sin cambios en %s; se omite commit.", _ruta_procesadas())
            return

        subprocess.run(["git", "commit", "-m", "Update procesadas"], check=True)
        subprocess.run(["git", "push"], check=True)
        logger.info("%s pusheado a GitHub.", _ruta_procesadas())
    except Exception as error:
        logger.warning("No se pudo pushear %s: %s", _ruta_procesadas(), error)


def main() -> None:
    enviar_telegram("📡 ElChilometro iniciado.")

    try:
        cliente = Groq(api_key=GROQ_API_KEY)
        noticias, stats, muestras_descartadas = obtener_noticias()
    except Exception as error:
        enviar_telegram(f"❌ Error inicializando u obteniendo noticias:\n{error}")
        return

    if not noticias:
        enviar_telegram("⚠️ Sin noticias relevantes hoy.")
        enviar_telegram(_resumen_diagnostico(stats, []))
        return

    procesadas = cargar_procesadas()
    noticias_nuevas = [
        noticia
        for noticia in noticias
        if noticia["link"] not in procesadas
        and _marca_titulo_procesado(noticia["titulo"]) not in procesadas
    ]

    modo_rescate = False

    modo_rescate = False
    if not noticias_nuevas:
        enviar_telegram("ℹ️ Sin noticias nuevas en este ciclo.")
        enviar_telegram(_resumen_diagnostico(stats, muestras_descartadas))
        return

    links_nuevos: Set[str] = set()
    noticias_seleccionadas = noticias_nuevas[:MAX_EVALUACIONES_IA]
    enviadas = 0
    descartadas_idioma = 0
    descartadas_ia = 0
    titulos_descartados: List[str] = []

    logger.info(
        "Resumen inicial de ejecución: candidatas=%s nuevas=%s a_procesar=%s fuentes_ok=%s/%s",
        stats["candidatas"],
        len(noticias_nuevas),
        len(noticias_seleccionadas),
        stats["fuentes_total"] - stats["fuentes_error"],
        stats["fuentes_total"],
    )
    logger.info(_resumen_diagnostico(stats, muestras_descartadas))

    for indice, noticia in enumerate(noticias_seleccionadas, start=1):
        if enviadas >= MAX_NOTICIAS_A_PROCESAR:
            logger.info("Se alcanzó el máximo de noticias a enviar: %s", MAX_NOTICIAS_A_PROCESAR)
            break

        try:
            logger.info(
                "Evaluando candidata %s/%s: %s",
                indice,
                len(noticias_seleccionadas),
                noticia["titulo"],
            )
            if _tiene_ingles_consecutivo(noticia["titulo"]):
                descartadas_idioma += 1
                logger.info("Descartada por idioma: %s", noticia["titulo"])
                links_nuevos.update({noticia["link"], _marca_titulo_procesado(noticia["titulo"])})
                continue

            decision = es_avance_positivo(cliente, noticia["titulo"])
            if decision:
                post = generar_post(cliente, noticia)
                logger.info("Aprobada por IA: %s", noticia["titulo"])
                enviar_telegram(f"📢 POST SUGERIDO:\n\n{post}")
                enviadas += 1
                links_nuevos.update({noticia["link"], _marca_titulo_procesado(noticia["titulo"])})
            else:
                descartadas_ia += 1
                logger.info("Descartada por IA: %s", noticia["titulo"])
                titulos_descartados.append(noticia["titulo"])
        except Exception as error:
            logger.exception("Error procesando noticia: %s", noticia["titulo"])
            enviar_telegram(f"❌ Error generando post:\n{error}")

    logger.info(
        "Resumen final de ejecución: enviadas=%s descartadas_ia=%s descartadas_idioma=%s evaluadas=%s",
        enviadas,
        descartadas_ia,
        descartadas_idioma,
        min(len(noticias_seleccionadas), MAX_EVALUACIONES_IA),
    )

    if titulos_descartados:
        enviar_telegram("❌ DESCARTADOS:\n" + "\n".join(f"- {titulo}" for titulo in titulos_descartados))

    try:
        guardar_procesadas(procesadas | links_nuevos)
    except Exception as error:
        logger.exception("Error guardando procesadas: %s", error)
        enviar_telegram(f"❌ Error guardando procesadas:\n{error}")


def run_listener() -> None:
    offset = 0
    chat_autorizado = TELEGRAM_CHAT_IDS[0] if TELEGRAM_CHAT_IDS else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    while True:
        try:
            response = requests.get(
                url,
                params={"timeout": 30, "offset": offset},
                timeout=35,
            )
            response.raise_for_status()
            payload = response.json()

            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                mensaje = update.get("message", {})
                chat_id = str(mensaje.get("chat", {}).get("id", ""))
                texto = (mensaje.get("text") or "").strip()

                if not chat_autorizado or chat_id != chat_autorizado:
                    continue

                if texto == "/buscar":
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        data={"chat_id": chat_id, "text": "⚙️ Buscando noticias..."},
                        timeout=10,
                    ).raise_for_status()
                    main()
                elif texto == "/status":
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        data={
                            "chat_id": chat_id,
                            "text": f"✅ Bot activo. {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
                        },
                        timeout=10,
                    ).raise_for_status()
        except requests.RequestException as error:
            logger.warning("Error de red en listener: %s", error)
            time.sleep(5)
        except Exception as error:
            logger.exception("Error en listener: %s", error)
            time.sleep(5)


if __name__ == "__main__":
    modo = os.environ.get("BOT_MODE", "once")
    if modo == "listener":
        run_listener()
    else:
        main()
