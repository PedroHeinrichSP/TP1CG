class Drawing:
    canvas = None
    
    def __init__(self):
        pass

    @staticmethod
    def set_canvas(canvas):
        Drawing.canvas = canvas

    @staticmethod
    def paintPixel(x, y, color):
        if Drawing.canvas:
            Drawing.canvas.set_pixel(int(x), int(y), color)

class Point(Drawing):
 
    def __init__(self, x=None, y=None, color=None):
        self.x = x
        self.y = y
        self.color = color

    def __str__(self):
        return f'Ponto Coordenadas:\nX: {self.x}\tY: {self.y}'

class Line(Drawing):
    def __init__(self, pointA, pointB, color=None):
        self.pointA = pointA
        self.pointB = pointB
        self.color = color
    
    def __str__(self):
        return f'Linha Coordenadas:\nX1: {self.pointA.x} \tY1: {self.pointA.y}\nX2: {self.pointB.x} \tY2: {self.pointB.y}'

class Circle(Drawing):
    def __init__(self, center, radius, color=None):
        self.center = center
        self.radius = radius
        self.color = color

    def __str__(self):
        return f'Circulo Coordenadas:\nX: {self.center.x} \tY: {self.center.y} \tRaio: {self.radius}'

class Polygon(Drawing):
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
    