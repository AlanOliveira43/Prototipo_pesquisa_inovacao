from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import json
from math import log
from pathlib import Path
import re
import unicodedata


BASE = Path(__file__).with_name("fontes.json")
PALAVRAS_COMUNS = set((
    "a as o os e da das do dos de em um uma para por no na nas nos que qual quais como posso pode se"
    " sobre com ou ao aos segundo diz quando quanto existe deve sao lei artigo artigos art arts"
    " preciso verificar brasileira posso buscar"
).split())
LISTA_ARTIGOS = r"\d{1,4}(?:-[a-z])?(?:\s*(?:,|e)\s*\d{1,4}(?:-[a-z])?)*"
LEIS_FORA_DA_BASE = r"\b(?:clt|cpp|codigo penal|codigo de processo penal|constituicao federal|cf/88)\b"


@dataclass(frozen=True)
class Fonte:
    lei: str
    sigla: str
    artigo: str
    tema: str
    resumo: str
    termos: str
    url: str

    @property
    def identificador(self) -> str:
        return f"{self.sigla}-{self.artigo}"


def _normalizar(texto: str) -> str:
    return "".join(letra for letra in unicodedata.normalize("NFKD", texto.casefold())
                   if not unicodedata.combining(letra))


def _termos(texto: str) -> set[str]:
    return {palavra.removesuffix("s") if len(palavra) > 4 else palavra
            for palavra in re.findall(r"[a-z]{2,}", _normalizar(texto)) if palavra not in PALAVRAS_COMUNS}


@lru_cache(maxsize=1)
def _carregar_base() -> tuple[tuple[Fonte, ...], dict[str, str]]:
    leis = json.loads(BASE.read_text(encoding="utf-8"))
    fontes = tuple(Fonte(lei["nome"], lei["sigla"], artigo["artigo"], artigo["tema"],
                         artigo["resumo"], artigo["termos"], lei["url"])
                   for lei in leis for artigo in lei["artigos"])
    aliases = {_normalizar(alias): lei["sigla"] for lei in leis for alias in lei["aliases"]}
    return fontes, aliases


def buscar_fontes(consulta: str, limite: int = 5) -> list[Fonte]:
    if not consulta.strip():
        raise ValueError("Digite uma pergunta, assunto ou referência legal.")
    fontes, aliases = _carregar_base()
    texto = _normalizar(re.sub(r"(?<=\d)\.?\s*[º°]", "", consulta))
    leis = {sigla for alias, sigla in aliases.items()
            if re.search(rf"\b{re.escape(alias)}\b", texto)}
    if not leis and re.search(rf"\blei\s*(?:n[.o]*\s*)?\d|{LEIS_FORA_DA_BASE}", texto):
        return []

    grupos = re.findall(rf"\b(?:artigos?|arts?)\.?\s*({LISTA_ARTIGOS})", texto)
    if not grupos and leis:
        siglas = "|".join({f.sigla.lower() for f in fontes})
        grupos = re.findall(rf"\b(?:{siglas})\s+({LISTA_ARTIGOS})", texto)
    artigos = {numero for grupo in grupos for numero in re.findall(r"\d+(?:-[a-z])?", grupo)}
    candidatas = [fonte for fonte in fontes if not leis or fonte.sigla in leis]
    if artigos:
        return [fonte for fonte in candidatas if fonte.artigo.lower() in artigos][:limite]

    for alias in sorted(aliases, key=len, reverse=True):
        texto = re.sub(rf"\b{re.escape(alias)}\b", " ", texto)
    consulta_tokens = _termos(texto)
    if leis and not consulta_tokens:
        return candidatas[:limite]

    entradas = []
    frequencias = Counter()
    for fonte in candidatas:
        tema = _termos(fonte.tema)
        palavras = _termos(fonte.termos)
        resumo = _termos(fonte.resumo)
        frequencias.update(tema | palavras | resumo)
        entradas.append((fonte, tema, palavras, resumo))

    def peso(palavra: str) -> float:
        return 1 + log((1 + len(candidatas)) / (1 + frequencias[palavra]))

    classificacao = []
    for fonte, tema, palavras, resumo in entradas:
        pontos = sum(peso(palavra) * (3 * (palavra in tema) + 2 * (palavra in palavras) + (palavra in resumo))
                     for palavra in sorted(consulta_tokens))
        if pontos:
            classificacao.append((pontos, fonte))

    classificacao.sort(key=lambda item: item[0], reverse=True)
    if not classificacao:
        return []
    minimo = classificacao[0][0] * 0.34
    return [fonte for pontos, fonte in classificacao[:limite] if pontos >= minimo]
