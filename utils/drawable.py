"""Módulo de entidades desenháveis.

Define classes de apoio para desenho em um canvas abstrato, incluindo:
- Drawing: base com acesso estático ao canvas e utilitário para pintar pixels;
- Point, Line, Circle e Polygon: primitivas geométricas com metadados de cor.

As classes não implementam lógica de rasterização; isso é responsabilidade
dos algoritmos em `utils.algorithms`. Aqui apenas guardamos dados e fornecemos
um ponto único (Drawing.canvas) por onde os algoritmos escrevem pixels.
"""


class Drawing:
    """Classe base para objetos desenháveis.

    Mantém uma referência estática a um canvas que recebe pixels via
    `set_pixel(x, y, color)`.
    """

    canvas = None

    def __init__(self):
        pass

    @staticmethod
    def set_canvas(canvas):
        """Registra o objeto de canvas que receberá os pixels.

        O canvas deve expor um método `set_pixel(x: int, y: int, color: str)`.
        """
        Drawing.canvas = canvas

    @staticmethod
    def paintPixel(x, y, color):
        """Pinta um único pixel (x, y) no canvas, se houver um canvas ativo.

        Parâmetros
        - x, y: coordenadas inteiras no buffer lógico do canvas
        - color: cor no formato aceito pelo canvas (ex.: "#RRGGBB")
        """
        if Drawing.canvas:
            Drawing.canvas.set_pixel(int(x), int(y), color)


class Point(Drawing):
    """Ponto (x, y) com cor opcional."""

    def __init__(self, x=None, y=None, color=None):
        self.x = x
        self.y = y
        self.color = color

    def __str__(self):
        return f'Ponto Coordenadas:\nX: {self.x}\tY: {self.y}'


class Line(Drawing):
    """Segmento de reta entre dois pontos, com cor opcional."""

    def __init__(self, pointA, pointB, color=None):
        self.pointA = pointA
        self.pointB = pointB
        self.color = color

    def __str__(self):
        return (
            f'Linha Coordenadas:\nX1: {self.pointA.x} \tY1: {self.pointA.y}\n'
            f'X2: {self.pointB.x} \tY2: {self.pointB.y}'
        )


class Circle(Drawing):
    """Círculo definido por centro, raio e cor opcional."""

    def __init__(self, center, radius, color=None):
        self.center = center
        self.radius = radius
        self.color = color

    def __str__(self):
        return (
            f'Circulo Coordenadas:\nX: {self.center.x} \tY: {self.center.y} '
            f'\tRaio: {self.radius}'
        )


class Polygon(Drawing):
    """Polígono definido por uma lista de segmentos de reta (linhas)."""

    def __init__(self, lines):
        self.lines = lines

    def __str__(self):
        ret = "Poligono Coordenadas:\n"
        idx = 1
        for ln in self.lines:
            ret += f'{idx}. '
            ret += ln.__str__()
            ret += "\n"
            idx += 1
        return ret
    