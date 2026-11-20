import re


TIPOS = ("Petição inicial", "Contestação", "Manifestação")
CAMPOS = {
    "Juízo": "[Vara, comarca e UF]",
    "Partes": "[Identificação e qualificação das partes]",
    "Processo": "[Número do processo]",
    "Fatos": "[Inserir a narrativa a partir dos documentos]",
    "Fundamentos": "[Inserir os fundamentos jurídicos revisados]",
    "Pedidos": "[Especificar cada pedido]",
    "Provas": "[Relacionar provas e documentos pertinentes]",
    "Valor da causa": "[Informar valor e critério de cálculo]",
    "Conciliação": "[Indicar a opção sobre audiência de conciliação ou mediação]",
}


def gerar_minuta(tipo: str, dados: str) -> str:
    if tipo not in TIPOS:
        raise ValueError("Selecione um tipo de peça.")

    campos = CAMPOS.copy()
    nomes = "|".join(map(re.escape, CAMPOS))
    partes = re.split(rf"(?im)^[ \t]*({nomes})[ \t]*:[ \t]*", dados)
    nomes_canonicos = {nome.casefold(): nome for nome in CAMPOS}
    if partes[0].strip():
        campos["Fatos"] = partes[0].strip()
    for chave, valor in zip(partes[1::2], partes[2::2]):
        if valor.strip():
            campos[nomes_canonicos[chave.casefold()]] = valor.strip()

    titulo_fatos = {
        "Petição inicial": "I. Dos fatos",
        "Contestação": "I. Síntese da demanda e versão da parte ré",
        "Manifestação": "I. Do objeto da manifestação",
    }[tipo]
    secoes = [f"Ao Juízo de {campos['Juízo']}", tipo.upper()]
    if tipo != "Petição inicial" or campos["Processo"] != CAMPOS["Processo"]:
        secoes.append(f"Processo: {campos['Processo']}")
    secoes.extend([
        f"Partes: {campos['Partes']}",
        f"{titulo_fatos}\n{campos['Fatos']}",
        f"II. Dos fundamentos\n{campos['Fundamentos']}",
        f"III. Dos pedidos\n{campos['Pedidos']}",
        f"IV. Das provas e dos documentos\n{campos['Provas']}",
    ])
    if tipo == "Petição inicial":
        secoes.extend([
            f"V. Do valor da causa\n{campos['Valor da causa']}",
            f"VI. Da conciliação ou mediação\n{campos['Conciliação']}",
        ])
    secoes.append("[Local e data]\n[Nome e OAB]")
    return "\n\n".join(secoes) + "\n"
