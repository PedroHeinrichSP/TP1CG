# TP1CG - Editor Gráfico (PyQt6)

Editor gráfico simples em PyQt6 que integra os algoritmos do diretório `utils/` (rasterização de linhas por DDA/Bresenham, círculos por Bresenham, recorte por Cohen-Sutherland e Liang-Barsky, e transformações 2D). O canvas usa um buffer lógico pequeno (padrão 80x80) e é escalado para preencher a tela, com uma grade sobreposta entre os pixels para facilitar a visualização.

## Requisitos

- Python 3.11+ (recomendado)
- Dependências do `requirements.txt` (PyQt6, Pillow, numpy)

## Como executar

1) (Opcional, mas recomendado) criar e ativar ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

2) Instalar dependências:

```bash
pip install -r requirements.txt
```

3) Executar a aplicação:

```bash
python main.py
```

## Uso rápido

- Escolha o algoritmo de linha (DDA/Bresenham) no combo da barra superior.
- Ferramentas: Ponto, Reta, Círculo, Polígono e Recorte (arraste para criar uma janela/viewport).
- O checkbox “Grid” liga/desliga a grade desenhada entre as células do buffer lógico.
- Clique no seletor de cor para mudar a cor de desenho.
- Selecione objetos na árvore lateral; clique direito sobre a bounding box para transformar (transladar/rotacionar/escalar/refletir).
