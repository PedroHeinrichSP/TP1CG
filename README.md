# TP1CG - Editor Gráfico (PyQt6)

Este repositório agora inclui uma interface PyQt6 que integra as implementações de algoritmos no diretório `utils/`.

Funcionalidades principais:
- Ferramentas: Ponto, Reta, Círculo, Polígono (fechado automaticamente ao voltar ao primeiro vértice).
- Algoritmos de rasterização: escolha entre DDA e Bresenham para linhas; círculos usam Bresenham.
- Recorte: opção entre Cohen-Sutherland e nenhum (Liang-Barsky placeholder disponível no código).
- Seleção de objetos via lista lateral; ao selecionar um objeto, uma bounding box é desenhada e pode-se aplicar transformações.
- Transformações suportadas: translação, rotação, escala, reflexão — acessíveis por clique direito no objeto ou via diálogos numéricos.
- Projeto: criar novo canvas (definir resolução), salvar/abrir projeto em JSON, exportar canvas como PNG.
- Seleção de cor na caixa vermelha (clicar abre o seletor de cores).

Arquivos novos/alterados importantes:
- `ui/editor.ui` - arquivo da interface (Qt Designer XML).
- `main.py` - aplicação PyQt6 que carrega `ui/editor.ui` e integra `utils/algorithms.py` e `utils/drawable.py`.
- `requirements.txt` - dependências mínimas (PyQt6, Pillow, numpy).

Como executar

1. Crie e ative um ambiente virtual (recomendado):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instale dependências:

```bash
pip install -r requirements.txt
```

3. Execute o editor:

```bash
python main.py
```

## Empacotar (Windows, Linux x86_64 e macOS)

Usamos PyInstaller. Instale-o no ambiente atual:

```
pip install pyinstaller
```

Importante: empacote nativamente no sistema-alvo. Ou seja, gere o .exe no Windows, o binário no Linux x86_64 e o .app/.bin no macOS rodando o comando em cada OS (PyInstaller não faz cross-compile real entre plataformas).

O projeto carrega o arquivo de UI via `resource_path()` (suporta PyInstaller). Lembre-se de incluir `ui/editor.ui` com `--add-data`.

- Windows (gera TP1CG.exe):

```
pyinstaller --noconfirm \
	--onefile --windowed \
	--name TP1CG \
	--add-data "ui\\editor.ui;ui" \
	main.py
```

- Linux x86_64 (gera dist/TP1CG):

```
pyinstaller --noconfirm \
	--onefile --windowed \
	--name TP1CG \
	--add-data "ui/editor.ui:ui" \
	main.py
```

- macOS (gera .app e binário em dist/TP1CG):

```
pyinstaller --noconfirm \
	--onefile --windowed \
	--name TP1CG \
	--add-data "ui/editor.ui:ui" \
	main.py
```

Dicas:
- Se faltar algum plugin do Qt (ex.: platforms), o hook do PyInstaller para PyQt6 normalmente resolve automaticamente. Certifique-se de estar com PyInstaller atualizado.
- Para incluir imagens adicionais (ex.: `silksong3.png`, `tela.png`) use mais `--add-data` no mesmo formato.
- Para debug, remova `--windowed` e rode o executável no terminal para ver logs.

Notas de uso e limitações
- Ao desenhar uma linha: selecione a ferramenta "Reta" e clique em dois pontos.
- Ao desenhar um círculo: clique no centro e em um ponto na circunferência para definir o raio.
- Ao desenhar um polígono: clique em cada vértice e clique próximo ao primeiro vértice para fechar o polígono.
- Seleção: use a lista lateral para selecionar um objeto (0/x indicado como índice). Uma bounding box aparecerá.
- Transformações: clique com o botão direito dentro da bounding box do objeto selecionado para abrir opções de transformação e inserir valores numéricos.
- Export: salve o projeto em JSON para edição posterior; exporte como PNG para imagem final.
