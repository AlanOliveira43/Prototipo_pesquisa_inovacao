# Juris — protótipo de assistente jurídico

Aplicativo desktop em Python, em português, com quatro módulos para experimentar fluxos de trabalho da advocacia brasileira.

## Executar no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Para uma demonstração com texto colado, TXT e pesquisa local, execute `python app.py`. O aplicativo usa o Tkinter distribuído com o instalador padrão do Python para Windows. As dependências de `requirements.txt` acrescentam leitura de PDF e leitura e exportação de DOCX.

## Experimentar os módulos

Escolha um módulo no menu lateral e clique em **Carregar exemplo** para preencher o campo com dados fictícios.

| Módulo | Como testar |
| --- | --- |
| Análise de contratos | Cole o contrato ou importe um PDF, DOCX ou TXT. Clique em **Analisar contrato**. O relatório mostra trechos sobre multas, renovação, foro e outros pontos para revisão. |
| Pesquisa jurídica | Digite um tema ou referência, como `arts. 319 e 320 do CPC`, e clique em **Buscar fontes**. O resultado identifica o artigo, apresenta um resumo editorial e abre a redação oficial no Planalto. |
| Editor de peças | Selecione **Petição inicial**, **Contestação** ou **Manifestação**. Preencha os dados e clique em **Gerar minuta**. Edite o texto no painel direito e salve em TXT ou DOCX. Você também pode abrir uma minuta existente para editar. |
| Extração processual | Cole ou importe o documento e clique em **Extrair informações**. O resultado lista até cinco trechos por campo e indica a página do PDF ou a linha do texto extraído. Datas e prazos são transcritos para conferência nos autos. |

Para preencher a minuta local, você pode começar cada campo numa linha com um dos rótulos `Juízo:`, `Partes:`, `Processo:`, `Fatos:`, `Fundamentos:`, `Pedidos:`, `Provas:`, `Valor da causa:` ou `Conciliação:`. Em texto livre, a entrada preenche a seção sobre os fatos. Campos pendentes aparecem entre colchetes.

## Ativar a IA opcional

Com uma chave válida da API da OpenAI, execute no mesmo PowerShell em que vai iniciar o aplicativo. A chave fica na variável de ambiente desse terminal. Os comandos abaixo pedem a chave sem exibi-la durante a digitação.

```powershell
$chave = Read-Host 'Chave da API da OpenAI' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $chave).Password
.\.venv\Scripts\python.exe app.py
```

Marque **Usar IA pela OpenAI** na interface. As funções com IA enviam à API o texto da tarefa que você executou. O modo local fica ativo por padrão, inclusive quando há chave configurada. Para testar com IA, utilize os exemplos fictícios ou dados cuja transmissão tenha sido autorizada. A API requer internet e pode gerar cobrança. O modelo padrão é `gpt-6-luna`. A variável opcional `OPENAI_MODEL` permite selecionar outro modelo compatível com a Responses API e saídas estruturadas. [Documentação da Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)

Na análise e na extração, o programa exibe evidências da IA quando localiza os trechos no texto original. Na pesquisa, as referências e os links vêm da base local e a síntese usa os resumos recuperados. No editor, **Revisar com IA** abre a proposta para conferência antes de aplicar a alteração.

## Alcance da demonstração

- A base demonstrativa reúne 18 artigos de quatro leis. Você pode acrescentar fontes legislativas em `juris/fontes.json`. A atualização é manual. [Código Civil](https://planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm) · [CPC](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105compilada.htm) · [CDC](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm) · [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm)
- A importação aceita arquivos de até 12 MB, texto de até 200 mil caracteres e PDFs de até 200 páginas. Para PDF digitalizado, use uma cópia com OCR ou cole a transcrição. Se você editar o texto de um PDF importado, as referências passam a indicar linhas do texto editado.
- O modo local usa regras de triagem, busca por termos e modelos de minuta. Confira cláusulas, referências, dados e prazos nos documentos originais. Revise a minuta antes de utilizá-la.

## Arquivos do projeto

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Ponto de entrada do aplicativo |
| `juris/interface.py` | Interface e execução das tarefas |
| `juris/documentos.py` | Leitura, localização de trechos e exportação |
| `juris/analise.py` | Regras locais de contrato e extração processual |
| `juris/pesquisa.py` e `juris/fontes.json` | Busca e base legislativa demonstrativa |
| `juris/pecas.py` | Modelos de minutas |
| `juris/ia.py` | Integração opcional com a API |
| `juris/exemplos.py` | Dados fictícios para testar os quatro módulos |
