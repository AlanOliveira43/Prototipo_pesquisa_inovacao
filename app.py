import tkinter as tk

from juris.interface import Aplicativo


def main() -> None:
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()


if __name__ == "__main__":
    main()
