from dataclasses import dataclass
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from zipfile import ZipFile


LIMITE_TEXTO = 200_000
LIMITE_ARQUIVO = 12 * 1024 * 1024
LIMITE_PAGINAS = 200


@dataclass(frozen=True)
class Trecho:
    referencia: str
    texto: str


@dataclass(frozen=True)
class Documento:
    partes: tuple[str, ...]
    paginado: bool = False
    paginas_sem_texto: tuple[int, ...] = ()

    @property
    def texto(self) -> str:
        return "\n\n".join(self.partes)

    def trecho(self, parte: int, inicio: int, fim: int) -> Trecho:
        texto = self.partes[parte]
        primeira = texto.count("\n", 0, inicio) + 1
        ultima = texto.count("\n", 0, max(inicio, fim - 1)) + 1
        linhas = f"linha {primeira}" if primeira == ultima else f"linhas {primeira}–{ultima}"
        referencia = f"p. {parte + 1}, {linhas}" if self.paginado else linhas
        return Trecho(referencia, " ".join(texto[inicio:fim].split()))

    def localizar(self, evidencia: str) -> Trecho | None:
        palavras = evidencia.split()
        if not palavras or len(evidencia) > 600:
            return None
        padrao = re.compile(r"\s+".join(map(re.escape, palavras)))
        for indice, parte in enumerate(self.partes):
            encontro = padrao.search(parte)
            if encontro:
                return self.trecho(indice, *encontro.span())
        return None


def validar(documento: Documento) -> Documento:
    if not any(parte.strip() for parte in documento.partes):
        raise ValueError("Insira um texto ou importe um arquivo com texto selecionável.")
    if len(documento.texto) > LIMITE_TEXTO:
        raise ValueError("O limite é de 200 mil caracteres. Analise o documento em partes.")
    return documento


def abrir_documento(caminho: Path) -> Documento:
    if caminho.stat().st_size > LIMITE_ARQUIVO:
        raise ValueError("O arquivo excede o limite de 12 MB.")
    extensao = caminho.suffix.lower()
    if extensao == ".pdf":
        return _abrir_pdf(caminho)
    if extensao == ".docx":
        return validar(Documento(("\n".join(_abrir_word(caminho)),)))
    if extensao == ".txt":
        conteudo = caminho.read_bytes()
        try:
            texto = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = conteudo.decode("cp1252")
        texto = texto.replace("\r\n", "\n").replace("\r", "\n")
        if "\0" in texto:
            raise ValueError("Salve o arquivo de texto com codificação UTF-8.")
        return validar(Documento((texto,)))
    raise ValueError("Escolha um arquivo PDF, DOCX ou TXT.")


def _abrir_pdf(caminho: Path) -> Documento:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as erro:
        raise ValueError("Para abrir PDFs, instale as dependências do requirements.txt.") from erro

    try:
        with caminho.open("rb") as arquivo:
            leitor = PdfReader(arquivo)
            if leitor.is_encrypted:
                raise ValueError("Abra uma cópia do PDF sem proteção por senha.")
            if len(leitor.pages) > LIMITE_PAGINAS:
                raise ValueError("O PDF excede 200 páginas. Divida-o em arquivos menores.")

            partes = []
            tamanho = 0
            for pagina in leitor.pages:
                texto = (pagina.extract_text() or "").strip()
                partes.append(texto)
                tamanho += len(texto) + 2
                if tamanho > LIMITE_TEXTO + 2:
                    raise ValueError("O PDF ultrapassa 200 mil caracteres. Analise-o em partes.")
    except PyPdfError as erro:
        raise ValueError("Falha ao ler o PDF. Confira se o arquivo abre em um leitor de PDF.") from erro

    sem_texto = tuple(i for i, texto in enumerate(partes, start=1) if not texto)
    if len(sem_texto) == len(partes):
        raise ValueError("O PDF não contém texto selecionável. Use uma versão com OCR ou cole o texto.")
    return Documento(tuple(partes), paginado=True, paginas_sem_texto=sem_texto)


def _abrir_word(caminho: Path) -> list[str]:
    try:
        from docx import Document
        from docx.table import Table
    except ImportError as erro:
        raise ValueError("Para abrir arquivos do Word, instale as dependências do requirements.txt.") from erro

    with ZipFile(caminho) as pacote:
        if sum(item.file_size for item in pacote.infolist()) > 60 * 1024 * 1024:
            raise ValueError("O conteúdo descompactado do DOCX é muito grande.")

    linhas = []

    def ler_blocos(container) -> None:
        for bloco in container.iter_inner_content():
            if isinstance(bloco, Table):
                celulas_lidas = set()
                for linha in bloco.rows:
                    for celula in linha.cells:
                        if celula._tc not in celulas_lidas:
                            celulas_lidas.add(celula._tc)
                            ler_blocos(celula)
            else:
                linhas.append(bloco.text)

    ler_blocos(Document(caminho))
    return linhas


def salvar_peca(caminho: Path, texto: str) -> None:
    extensao = caminho.suffix.lower()
    if extensao not in {".txt", ".docx"}:
        raise ValueError("Use .docx ou .txt para salvar a minuta.")
    with NamedTemporaryFile(dir=caminho.parent, suffix=extensao, delete=False) as arquivo:
        temporario = Path(arquivo.name)
    try:
        if extensao == ".txt":
            temporario.write_text(texto, encoding="utf-8")
        else:
            _salvar_word(temporario, texto)
        temporario.replace(caminho)
    finally:
        temporario.unlink(missing_ok=True)


def _salvar_word(caminho: Path, texto: str) -> None:
    try:
        from docx import Document
    except ImportError as erro:
        raise ValueError("Para exportar em Word, instale as dependências ou selecione TXT.") from erro

    minuta = Document()
    for linha in texto.splitlines():
        minuta.add_paragraph(linha)
    minuta.save(caminho)
