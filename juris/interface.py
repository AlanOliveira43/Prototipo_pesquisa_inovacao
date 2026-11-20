from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from . import exemplos
from .analise import Achado, analisar_contrato, extrair_processo
from .documentos import Documento, abrir_documento, salvar_peca, validar
from .ia import AssistenteIA, FalhaIA
from .pecas import TIPOS, gerar_minuta
from .pesquisa import buscar_fontes


FUNDO = "#F2F3ED"
BRANCO = "#FFFFFF"
TEXTO = "#1C302C"
SUAVE = "#4B635B"
LINHA = "#D6DFD7"
ESCURA = "#142D29"
DESTAQUE = "#146452"
TEXTO_LATERAL = "#D8E7DF"
FONTE = "Segoe UI"


@dataclass(frozen=True)
class Modulo:
    menu: str
    titulo: str
    descricao: str
    entrada: str
    saida: str
    acao: str
    exemplo: str


MODULOS = {
    "contrato": Modulo("Análise de contratos", "Análise de contratos",
                       "Localize cláusulas sensíveis e veja o que conferir em cada trecho.",
                       "Texto do contrato", "Pontos de revisão", "Analisar contrato", exemplos.CONTRATO),
    "pesquisa": Modulo("Pesquisa jurídica", "Pesquisa jurídica",
                       "Consulte artigos de uma base demonstrativa de legislação brasileira.",
                       "Pergunta ou referência", "Fontes encontradas", "Buscar fontes", exemplos.PESQUISA),
    "peca": Modulo("Editor de peças", "Editor de peças jurídicas",
                   "Gere uma minuta com os dados disponíveis e revise o texto antes de exportar.",
                   "Dados do caso", "Minuta editável", "Gerar minuta", exemplos.PECA),
    "processo": Modulo("Extração processual", "Extração processual",
                       "Localize partes, datas, prazos expressos e determinações no documento.",
                       "Texto do processo", "Informações encontradas", "Extrair informações", exemplos.PROCESSO),
}
ARQUIVOS = [("Documentos PDF, Word e texto", ("*.pdf", "*.docx", "*.txt")), ("Todos os arquivos", "*.*")]


@dataclass(frozen=True)
class Bloco:
    titulo: str
    corpo: str = ""
    link: str = ""


class AreaTexto(tk.Frame):
    def __init__(self, pai: tk.Misc, editavel: bool = True):
        super().__init__(pai, bg=LINHA, padx=1, pady=1)
        self.editavel = editavel
        self.campo = tk.Text(self, wrap="word", undo=editavel, borderwidth=0, highlightthickness=0,
                             bg=BRANCO if editavel else "#F9FBF8", fg=TEXTO, insertbackground=TEXTO,
                             font=(FONTE, 11), padx=13, pady=11, spacing1=2, spacing3=2, width=18, height=8)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.campo.yview)
        self.campo.configure(yscrollcommand=barra.set, state="normal" if editavel else "disabled")
        self.campo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.campo.tag_configure("titulo", foreground=DESTAQUE, font=(FONTE, 11, "bold"), spacing1=4)
        self.campo.tag_configure("link", foreground=DESTAQUE, underline=True)
        self.campo.bind("<Tab>", self._foco_seguinte)
        self.campo.bind("<Shift-Tab>", self._foco_anterior)

    def _foco_seguinte(self, evento):
        self.campo.tk_focusNext().focus_set()
        return "break"

    def _foco_anterior(self, evento):
        self.campo.tk_focusPrev().focus_set()
        return "break"

    def obter(self) -> str:
        return self.campo.get("1.0", "end-1c")

    def escrever(self, texto: str) -> None:
        self.campo.configure(state="normal")
        self.campo.replace("1.0", "end-1c", texto)
        self.campo.see("1.0")
        self.bloquear(False)

    def mostrar(self, blocos: list[Bloco]) -> None:
        self.campo.configure(state="normal")
        self.campo.delete("1.0", "end")
        for tag in self.campo.tag_names():
            if tag.startswith("fonte_"):
                self.campo.tag_delete(tag)
        for indice, bloco in enumerate(blocos):
            self.campo.insert("end", bloco.titulo + "\n", "titulo")
            if bloco.corpo:
                self.campo.insert("end", bloco.corpo + "\n")
            if bloco.link:
                tag = f"fonte_{indice}"
                self.campo.insert("end", "Abrir texto oficial no Planalto\n", ("link", tag))
                self.campo.tag_bind(tag, "<Button-1>", lambda evento, url=bloco.link: webbrowser.open_new_tab(url))
                self.campo.tag_bind(tag, "<Enter>", lambda evento: self.campo.configure(cursor="hand2"))
                self.campo.tag_bind(tag, "<Leave>", lambda evento: self.campo.configure(cursor="xterm"))
            self.campo.insert("end", "\n")
        self.campo.see("1.0")
        self.bloquear(False)

    def bloquear(self, bloqueado: bool) -> None:
        self.campo.configure(state="disabled" if bloqueado or not self.editavel else "normal")


@dataclass
class Painel:
    moldura: tk.Frame
    entrada: AreaTexto
    saida: AreaTexto
    estado: tk.StringVar
    acoes: list[ttk.Widget] = field(default_factory=list)
    documento: Documento | None = None


def _bloco_achado(item: Achado) -> Bloco:
    corpo = f'{item.trecho.referencia} · “{item.trecho.texto}”'
    if item.observacao:
        corpo += "\n" + item.observacao
    return Bloco(item.titulo, corpo)


def _analisar(chave: str, documento: Documento, assistente: AssistenteIA | None) -> tuple[list[Bloco], str]:
    validar(documento)
    if chave == "contrato":
        blocos = [_bloco_achado(item) for item in analisar_contrato(documento)]
        if not blocos:
            blocos = [Bloco("Nenhum termo de triagem encontrado", "Leia o contrato integralmente para conferir outras cláusulas.")]
    else:
        campos = extrair_processo(documento)
        blocos = [Bloco(titulo, "\n".join(f'{item.referencia} · “{item.texto}”' for item in trechos))
                  for titulo, trechos in campos if trechos]
        ausentes = [titulo for titulo, trechos in campos if not trechos]
        if ausentes:
            blocos.append(Bloco("Campos não localizados na triagem", ", ".join(ausentes) + "."))
        blocos.append(Bloco("Conferência de prazos", "As datas e os prazos são transcritos para conferência nos autos."))

    estado = "Triagem concluída. Confira as evidências no documento original."
    if documento.paginas_sem_texto:
        paginas = ", ".join(map(str, documento.paginas_sem_texto))
        blocos.insert(0, Bloco("Páginas sem texto selecionável", f"Páginas {paginas}. Confira-as no PDF ou use OCR."))
    if assistente:
        try:
            adicionais = assistente.contrato(documento) if chave == "contrato" else assistente.processo(documento)
            blocos.append(Bloco("Revisão assistida por IA", "Confira a interpretação de cada trecho.") if adicionais
                          else Bloco("Revisão assistida por IA", "Nenhum trecho adicional pôde ser confirmado no texto."))
            blocos.extend(_bloco_achado(item) for item in adicionais)
        except FalhaIA as erro:
            estado = f"Resultados da triagem local. {erro}"
    return blocos, estado


def _pesquisar(consulta: str, assistente: AssistenteIA | None) -> tuple[list[Bloco], str]:
    if len(consulta) > 2_500:
        raise ValueError("Reduza a consulta para até 2.500 caracteres.")
    fontes = buscar_fontes(consulta)
    if not fontes:
        return [Bloco("Nenhuma fonte localizada", "Experimente um artigo ou assunto do CC, CPC, CDC ou LGPD.")], "Busca concluída."
    blocos = [Bloco(f"[{fonte.identificador}] {fonte.tema}",
                    f"{fonte.lei} · Art. {fonte.artigo}\n{fonte.resumo}", fonte.url) for fonte in fontes]
    estado = f"{len(fontes)} fonte(s) da base demonstrativa. Confira a redação oficial."
    if assistente:
        try:
            nota = assistente.pesquisa(consulta, fontes)
            if nota:
                blocos.insert(0, Bloco("Síntese assistida por IA", nota))
        except FalhaIA as erro:
            estado = f"Fontes locais disponíveis. {erro}"
    return blocos, estado


def _redigir(tipo: str, dados: str, assistente: AssistenteIA | None) -> tuple[str, str]:
    if len(dados) > 200_000:
        raise ValueError("O limite dos dados do caso é de 200 mil caracteres.")
    modelo = gerar_minuta(tipo, dados)
    if assistente:
        try:
            return assistente.redigir(tipo, dados, modelo), "Minuta assistida por IA. Confira fatos, pedidos e campos pendentes."
        except FalhaIA as erro:
            return modelo, f"Modelo local preenchido. {erro}"
    return modelo, "Modelo local preenchido. Edite a minuta no painel à direita."


class Aplicativo:
    def __init__(self, janela: tk.Tk):
        self.janela = janela
        self.janela.title("Juris — Assistente jurídico")
        self.janela.geometry("1120x650")
        self.janela.minsize(940, 600)
        self.janela.configure(bg=FUNDO)
        self.assistente = AssistenteIA.do_ambiente()
        self.permitir_ia = tk.BooleanVar(janela, value=False)
        self.ocupado = False
        self.paineis: dict[str, Painel] = {}
        self.navegacao: dict[str, tk.Button] = {}
        self.tipo_peca = tk.StringVar(janela, value=TIPOS[0])
        self._estilos()

        lateral = tk.Frame(janela, bg=ESCURA, width=218)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        tk.Label(lateral, text="Juris", bg=ESCURA, fg=BRANCO, font=("Georgia", 30)).pack(anchor="w", padx=23, pady=(22, 0))
        tk.Label(lateral, text="Assistente jurídico", bg=ESCURA, fg=TEXTO_LATERAL,
                 font=(FONTE, 10)).pack(anchor="w", padx=25, pady=(0, 27))

        for chave, modulo in MODULOS.items():
            botao = tk.Button(lateral, text=modulo.menu, anchor="w", bd=0, relief="flat", padx=11, pady=10,
                              font=(FONTE, 11), bg=ESCURA, fg=TEXTO_LATERAL, activebackground="#255047",
                              activeforeground=BRANCO, highlightbackground=ESCURA, highlightcolor="#85CCB8",
                              highlightthickness=1, cursor="hand2", command=lambda nome=chave: self.mostrar(nome))
            botao.pack(fill="x", padx=12, pady=2)
            self.navegacao[chave] = botao

        opcoes = tk.Frame(lateral, bg=ESCURA)
        opcoes.pack(side="bottom", fill="x", padx=23, pady=24)
        tk.Frame(opcoes, bg="#38584F", height=1).pack(fill="x", pady=(0, 12))
        self.botao_ia = tk.Checkbutton(opcoes, text="Usar IA pela OpenAI", variable=self.permitir_ia,
                                      bg=ESCURA, fg=BRANCO, activebackground=ESCURA, activeforeground=BRANCO,
                                      selectcolor="#365C53", disabledforeground="#A5B8B2", anchor="w",
                                      highlightbackground=ESCURA, highlightcolor="#85CCB8", font=(FONTE, 10, "bold"))
        self.botao_ia.pack(anchor="w")
        mensagem = ("Quando ativada, a IA recebe o texto da tarefa." if self.assistente.chave
                    else "Modo local. Configure OPENAI_API_KEY para ativar a IA.")
        if not self.assistente.chave:
            self.botao_ia.configure(state="disabled")
        tk.Label(opcoes, text=mensagem, bg=ESCURA, fg=TEXTO_LATERAL, font=(FONTE, 10), justify="left",
                 wraplength=167).pack(anchor="w", pady=(3, 0))

        self.principal = tk.Frame(janela, bg=FUNDO)
        self.principal.pack(side="left", fill="both", expand=True)
        for chave, modulo in MODULOS.items():
            self.paineis[chave] = self._montar_painel(chave, modulo)
        self.ativa = "contrato"
        self.mostrar(self.ativa)

    def _estilos(self) -> None:
        estilo = ttk.Style(self.janela)
        estilo.theme_use("clam")
        estilo.configure("TButton", font=(FONTE, 10), padding=(9, 6), background="#F6F8F4", foreground=TEXTO,
                         bordercolor=LINHA, lightcolor="#F6F8F4", darkcolor="#F6F8F4", focuscolor=DESTAQUE)
        estilo.map("TButton", background=[("active", "#E7EEE7")], foreground=[("disabled", "#6D7B72")])
        estilo.configure("Acao.TButton", font=(FONTE, 10, "bold"), background=DESTAQUE, foreground=BRANCO,
                         bordercolor=DESTAQUE, lightcolor=DESTAQUE, darkcolor=DESTAQUE, focuscolor=BRANCO)
        estilo.map("Acao.TButton", background=[("disabled", "#DCE5DD"), ("active", "#104C40")],
                   foreground=[("disabled", "#53665B")])
        estilo.configure("Vertical.TScrollbar", background="#E1E9E1", troughcolor="#F6F8F4", arrowcolor=SUAVE,
                         bordercolor=LINHA, lightcolor="#E1E9E1", darkcolor="#E1E9E1")
        estilo.configure("TCombobox", padding=5, font=(FONTE, 10))

    def _montar_painel(self, chave: str, modulo: Modulo) -> Painel:
        moldura = tk.Frame(self.principal, bg=FUNDO, padx=24, pady=22)
        tk.Label(moldura, text=modulo.titulo, bg=FUNDO, fg=TEXTO, font=("Georgia", 27), anchor="w").pack(fill="x")
        tk.Label(moldura, text=modulo.descricao, bg=FUNDO, fg=SUAVE, font=(FONTE, 11), anchor="w").pack(fill="x", pady=(4, 19))

        rodape = tk.Frame(moldura, bg=FUNDO)
        rodape.pack(side="bottom", fill="x", pady=(13, 0))
        estado = tk.StringVar(moldura, value="Use um exemplo fictício para testar este módulo.")
        tk.Label(rodape, textvariable=estado, bg=FUNDO, fg=SUAVE, font=(FONTE, 10), anchor="w",
                 justify="left", wraplength=645).pack(side="left", fill="x", expand=True, anchor="center")
        principal = ttk.Button(rodape, text=modulo.acao, style="Acao.TButton", command=lambda: self.executar(chave))
        principal.pack(side="right", padx=(12, 0))

        grade = tk.Frame(moldura, bg=FUNDO)
        grade.pack(fill="both", expand=True)
        grade.grid_rowconfigure(0, weight=1)
        grade.grid_columnconfigure((0, 1), weight=1, uniform="coluna")
        esquerda = tk.Frame(grade, bg=BRANCO, highlightbackground=LINHA, highlightthickness=1, padx=13, pady=12)
        direita = tk.Frame(grade, bg=BRANCO, highlightbackground=LINHA, highlightthickness=1, padx=13, pady=12)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        direita.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        for coluna, rotulo in ((esquerda, modulo.entrada), (direita, modulo.saida)):
            tk.Label(coluna, text=rotulo, bg=BRANCO, fg=TEXTO, font=(FONTE, 13, "bold"), anchor="w").pack(fill="x", pady=(0, 8))

        barra_esq = tk.Frame(esquerda, bg=BRANCO)
        barra_dir = tk.Frame(direita, bg=BRANCO)
        barra_esq.pack(side="top", fill="x", pady=(0, 9))
        barra_dir.pack(side="top", fill="x", pady=(0, 9))
        acoes = [principal]

        if chave in {"contrato", "processo"}:
            acoes.append(self._botao(barra_esq, "Importar arquivo", lambda: self.importar(chave)))
        if chave == "peca":
            tipos = ttk.Combobox(barra_esq, values=TIPOS, textvariable=self.tipo_peca, width=15, state="readonly",
                                  font=(FONTE, 10))
            tipos.pack(side="left", padx=(0, 5))
            acoes.append(tipos)
            acoes.extend([self._botao(barra_dir, "Abrir minuta", lambda: self.importar("peca", minuta=True)),
                          self._botao(barra_dir, "Revisar com IA", self.revisar),
                          self._botao(barra_dir, "Salvar", self.salvar)])
        else:
            dica = "Resumo editorial e link oficial por artigo" if chave == "pesquisa" else "Evidências com indicação de origem"
            tk.Label(barra_dir, text=dica, bg=BRANCO, fg=SUAVE, height=2, font=(FONTE, 9), anchor="w").pack(fill="x")

        acoes.append(self._botao(barra_esq, "Carregar exemplo", lambda: self.carregar_exemplo(chave)))
        entrada = AreaTexto(esquerda)
        entrada.pack(fill="both", expand=True)
        saida = AreaTexto(direita, editavel=chave == "peca")
        saida.pack(fill="both", expand=True)
        return Painel(moldura, entrada, saida, estado, acoes)

    def _botao(self, pai: tk.Misc, texto: str, comando: Callable) -> ttk.Button:
        botao = ttk.Button(pai, text=texto, command=comando)
        botao.pack(side="left", padx=(0, 5))
        return botao

    def mostrar(self, chave: str) -> None:
        self.paineis[self.ativa].moldura.pack_forget()
        self.navegacao[self.ativa].configure(bg=ESCURA, fg=TEXTO_LATERAL)
        self.paineis[chave].moldura.pack(fill="both", expand=True)
        self.navegacao[chave].configure(bg="#255047", fg=BRANCO)
        self.ativa = chave

    def carregar_exemplo(self, chave: str) -> None:
        painel = self.paineis[chave]
        exemplo = MODULOS[chave].exemplo
        atual = painel.entrada.obter().strip()
        if atual and atual != exemplo and not self._confirmar("Substituir a entrada pelo exemplo fictício?"):
            return
        painel.entrada.escrever(exemplo)
        painel.documento = None
        painel.estado.set("Exemplo fictício carregado.")
        painel.entrada.campo.focus_set()

    def importar(self, chave: str, minuta: bool = False) -> None:
        painel = self.paineis[chave]
        destino = painel.saida if minuta else painel.entrada
        if destino.obter().strip() and not self._confirmar("Substituir o texto atual pelo arquivo importado?"):
            return
        nome = filedialog.askopenfilename(parent=self.janela, title="Abrir documento", filetypes=ARQUIVOS)
        if not nome:
            return
        caminho = Path(nome)

        def receber(documento: Documento) -> None:
            destino.escrever(documento.texto)
            if not minuta:
                painel.documento = documento
            estado = f"Arquivo importado: {caminho.name}"
            if documento.paginas_sem_texto:
                estado += f" · {len(documento.paginas_sem_texto)} página(s) sem texto selecionável."
            painel.estado.set(estado)

        self._trabalho(painel, lambda: abrir_documento(caminho), receber, "Lendo o arquivo…")

    def executar(self, chave: str) -> None:
        painel = self.paineis[chave]
        texto = painel.entrada.obter()
        assistente = self.assistente if self.permitir_ia.get() else None
        if chave == "peca":
            if painel.saida.obter().strip() and not self._confirmar("Substituir a minuta atual pela nova versão?"):
                return
            tipo = self.tipo_peca.get()
            tarefa = lambda: _redigir(tipo, texto, assistente)
        elif chave == "pesquisa":
            tarefa = lambda: _pesquisar(texto, assistente)
        else:
            original = painel.documento
            documento = original if original and original.texto == texto else Documento((texto,))
            tarefa = lambda: _analisar(chave, documento, assistente)

        def receber(resultado: tuple) -> None:
            conteudo, estado = resultado
            if chave == "peca":
                painel.saida.escrever(conteudo)
                painel.saida.campo.focus_set()
            else:
                painel.saida.mostrar(conteudo)
            painel.estado.set(estado)

        progresso = "Processando a solicitação com IA…" if assistente else "Processando localmente…"
        self._trabalho(painel, tarefa, receber, progresso)

    def revisar(self) -> None:
        painel = self.paineis["peca"]
        minuta = painel.saida.obter()
        if not minuta.strip():
            painel.estado.set("Escreva, abra ou gere uma minuta para revisar.")
            return
        if not self.permitir_ia.get():
            painel.estado.set("Ative a IA pela OpenAI para pedir uma revisão automática.")
            return
        pedido = simpledialog.askstring("Revisar minuta", "O que você quer ajustar? Ex.: simplificar o parágrafo dos fatos.",
                                         parent=self.janela)
        if not pedido or not pedido.strip():
            return

        def receber(proposta: str) -> None:
            dialogo = tk.Toplevel(self.janela, bg=FUNDO)
            dialogo.title("Proposta de revisão")
            dialogo.geometry("760x590")
            dialogo.transient(self.janela)
            tk.Label(dialogo, text="Confira a proposta antes de substituir a minuta.", bg=FUNDO, fg=TEXTO,
                     font=(FONTE, 12, "bold")).pack(anchor="w", padx=18, pady=(14, 9))
            previa = AreaTexto(dialogo, editavel=False)
            previa.pack(expand=True, fill="both", padx=18)
            previa.escrever(proposta)
            botoes = tk.Frame(dialogo, bg=FUNDO)
            botoes.pack(pady=12)

            def aplicar() -> None:
                painel.saida.escrever(proposta)
                painel.estado.set("Revisão aplicada à minuta.")
                dialogo.destroy()

            ttk.Button(botoes, text="Aplicar revisão", style="Acao.TButton", command=aplicar).pack(side="left", padx=5)
            self._botao(botoes, "Fechar proposta", dialogo.destroy)
            dialogo.bind("<Escape>", lambda evento: dialogo.destroy())
            dialogo.grab_set()
            dialogo.focus_set()
            painel.estado.set("Proposta de revisão pronta para conferência.")

        self._trabalho(painel, lambda: self.assistente.revisar(minuta, pedido), receber, "Preparando a proposta de revisão…")

    def salvar(self) -> None:
        painel = self.paineis["peca"]
        texto = painel.saida.obter()
        if not texto.strip():
            painel.estado.set("Escreva ou gere uma minuta para salvar.")
            return
        nome = filedialog.asksaveasfilename(parent=self.janela, title="Salvar minuta", initialfile="minuta.txt",
                                            defaultextension=".txt", filetypes=[("Texto", "*.txt"), ("Word", "*.docx")])
        if nome:
            caminho = Path(nome)
            self._trabalho(painel, lambda: salvar_peca(caminho, texto),
                           lambda _: painel.estado.set(f"Minuta salva em {caminho.name}."), "Salvando minuta…")

    def _confirmar(self, mensagem: str) -> bool:
        return messagebox.askyesno("Confirmar substituição", mensagem, parent=self.janela)

    def _trabalho(self, painel: Painel, tarefa: Callable, receber: Callable, progresso: str) -> None:
        if self.ocupado:
            painel.estado.set("Aguarde a operação em andamento.")
            return
        self.ocupado = True
        painel.estado.set(progresso)
        painel.entrada.bloquear(True)
        painel.saida.bloquear(True)
        for botao in painel.acoes:
            botao.state(["disabled"])
        respostas = Queue()

        def rodar() -> None:
            try:
                respostas.put((True, tarefa()))
            except (ValueError, FalhaIA) as erro:
                respostas.put((False, str(erro)))
            except Exception:
                respostas.put((False, "A operação falhou. Confira o arquivo ou a pasta de destino e tente novamente."))

        def conferir() -> None:
            try:
                sucesso, resultado = respostas.get_nowait()
            except Empty:
                self.janela.after(40, conferir)
                return
            self.ocupado = False
            for botao in painel.acoes:
                botao.state(["!disabled"])
            painel.entrada.bloquear(False)
            painel.saida.bloquear(False)
            if sucesso:
                receber(resultado)
            else:
                painel.estado.set(resultado)

        Thread(target=rodar, daemon=True).start()
        self.janela.after(40, conferir)
