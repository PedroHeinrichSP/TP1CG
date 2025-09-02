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
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Line(Drawing):
    def __init__(self, pointA, pointB):
        self.pointA = pointA
        self.pointB = pointB

class Circle(Drawing):
    def __init__(self, center, radius):
        self.center = center
        self.radius = radius

class Poligon(Drawing):
    def __init__(self, Lines):
        self.Lines = Lines
