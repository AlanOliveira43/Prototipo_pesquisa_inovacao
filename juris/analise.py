from dataclasses import dataclass
import re

from .documentos import Documento, Trecho, validar


@dataclass(frozen=True)
class Achado:
    titulo: str
    trecho: Trecho
    observacao: str = ""


REGRAS_CONTRATO = (
    ("Multas e penalidades", r"\b(?:multas?|penalidades?|cl[áa]usula penal)\b",
     "Confira os gatilhos, a base de cálculo, os limites e as hipóteses de cumulação."),
    ("Rescisão e aviso prévio", r"\b(?:rescis[ãa]o|rescind\w*|resili[çc][ãa]o|den[uú]ncia|aviso pr[ée]vio)\b",
     "Confira prazos de aviso, obrigações após o encerramento e custos de saída."),
    ("Renovação e vigência", r"\b(?:renova\w*|prorroga\w*|vig[êe]ncia)\b",
     "Confira se há renovação automática e quando comunicar a intenção de encerrar."),
    ("Responsabilidade e indenização", r"\b(?:indeniza\w*|responsabilidade|danos indiretos|isen\w*)\b",
     "Confira exclusões, limites de responsabilidade e se a proteção vale para ambas as partes."),
    ("Foro e solução de conflitos", r"\b(?:foro|arbitragem|media[çc][ãa]o|cl[áa]usula compromiss[óo]ria)\b",
     "Confira o local, o procedimento previsto e os custos de resolver um conflito."),
    ("Reajuste e pagamento", r"\b(?:reajust\w*|corre[çc][ãa]o monet[áa]ria|vencimento|pagamento|juros)\b",
     "Confira datas, índice de reajuste e consequências do atraso."),
    ("Confidencialidade e dados", r"\b(?:confidencial\w*|sigilo|dados pessoais|LGPD)\b",
     "Confira o prazo de sigilo, o uso autorizado dos dados e as responsabilidades de cada parte."),
    ("Exclusividade e restrições", r"\b(?:exclusiv\w*|n[ãa]o concorr[êe]ncia|n[ãa]o aliciamento)\b",
     "Confira duração, território, atividades abrangidas e consequências da restrição."),
)

NUMERO_CNJ = r"(?<!\d)\d{7}\s*-\s*\d{2}\s*\.\s*\d{4}\s*\.\s*\d\s*\.\s*\d{2}\s*\.\s*\d{4}(?!\d)"
DIA = r"(?:0?[1-9]|[12]\d|3[01])"
DATA = (rf"(?<!\d\.)\b(?:{DIA}[/.-](?:0?[1-9]|1[0-2])[/.-](?:\d{{4}}|\d{{2}})(?!\.\d)|"
        rf"{DIA}\s+de\s+(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)\s+de\s+\d{4})\b")
REGRAS_PROCESSO = (
    ("Número do processo", NUMERO_CNJ),
    ("Órgão julgador", r"^[ \t]*(?:(?:\d{1,3}[ªºa.]*[ \t]+)?vara\b|ju[íi]zo[ \t]*(?::|d[aeo])|tribunal\b|comarca\b)[^\n]{0,220}"),
    ("Partes identificadas", r"(?:^|[;|])[ \t]*(?:autor[ae]?(?:es|s)?|parte autora|requerent[ea]s?|requerid[oa]s?|"
     r"r[ée](?:u|us|s)?|parte r[ée]|reclamante|reclamad[oa]|exequente|executad[oa])\s*(?::|\s[-–]\s)\s*[^\n;|]{1,160}"),
    ("Classe e assunto", r"^[ \t]*(?:classe(?: processual)?|assunto)\s*:\s*[^\n]{1,170}"),
    ("Valor da causa", r"\bvalor da causa\s*:?\s*(?:de\s+|é\s+de\s+)?R\$\s*[\d.]+(?:,\d{2})?"),
    ("Prazos expressos", r"\b(?:prazo\s*(?::|de|é de)?\s*(?:até\s+)?(?:" + DATA
     + r"|\d{1,3}(?:\s*\([^\n)]{1,40}\))?\s+(?:dias?|horas?|mes(?:es)?)(?:\s+(?:úteis|corridos?))?)|"
     r"(?:em|dentro de)\s+\d{1,3}(?:\s*\([^\n)]{1,40}\))?\s+(?:dias?|horas?|mes(?:es)?)(?:\s+(?:úteis|corridos?))?)\b"),
    ("Audiências e sessões", r"\b(?:audi[êe]ncia|sess[ãa]o de julgamento)\b"),
    ("Determinações e decisões", r"\b(?:determino|intimem?-se|citem?-se|designo|defiro|indefiro|homologo|julgo)\b"),
    ("Datas citadas", DATA),
)


def _ocorrencias(documento: Documento, padrao: str, limite: int, contexto: bool) -> list[Trecho]:
    expressao = re.compile(padrao, re.IGNORECASE | re.MULTILINE)
    trechos = []
    vistos = set()
    for indice, parte in enumerate(documento.partes):
        for encontro in expressao.finditer(parte):
            inicio, fim = encontro.span()
            if contexto:
                quebra_anterior = parte.rfind("\n", 0, inicio)
                quebra_seguinte = parte.find("\n", fim)
                inicio = max(quebra_anterior + 1, inicio - 100)
                fim = min(quebra_seguinte if quebra_seguinte != -1 else len(parte), fim + 165)
            trecho = documento.trecho(indice, inicio, fim)
            chave = trecho.texto if not contexto else (trecho.referencia, trecho.texto)
            if chave not in vistos:
                vistos.add(chave)
                trechos.append(trecho)
            if len(trechos) == limite:
                return trechos
    return trechos


def analisar_contrato(documento: Documento) -> list[Achado]:
    validar(documento)
    return [Achado(titulo, trecho, nota)
            for titulo, padrao, nota in REGRAS_CONTRATO
            for trecho in _ocorrencias(documento, padrao, limite=2, contexto=True)]


def extrair_processo(documento: Documento) -> list[tuple[str, list[Trecho]]]:
    validar(documento)
    categorias_de_contexto = {"Prazos expressos", "Audiências e sessões", "Determinações e decisões"}
    return [(titulo, _ocorrencias(documento, padrao, limite=5, contexto=titulo in categorias_de_contexto))
            for titulo, padrao in REGRAS_PROCESSO]
