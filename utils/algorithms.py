import math
from utils.drawable import Drawing, Point, Line, Circle, Polygon
## Transformadas 2D

class Transformations:
    def __init__(self):
        pass

    @staticmethod
    def translate(x, y, deltaX, deltaY):
        return x + deltaX, y + deltaY

    @staticmethod
    def scale(x, y, scaleX, scaleY):
        return round((x * scaleX)+ 0.000001), round((y * scaleY)+ 0.000001)

    @staticmethod
    def rotate(x, y, theta):  # theta está em graus
        angle = math.radians(theta)
        newX = x * math.cos(angle) - y * math.sin(angle)
        newY = x * math.sin(angle) + y * math.cos(angle)
        # print(round(newX + 0.000001), round(newY + 0.000001))
        return round(newX + 0.000001), round(newY + 0.000001)

    @staticmethod
    def reflect(x, y, axis):
        if axis == 'x':
            return x, -y
        elif axis == 'y':
            return -x, y
        elif axis == 'yx':
            return y, x


## Rasterização

class DDA:
    def __init__(self):
        pass
    
    @staticmethod
    def rasterizeLine(line=None, xA=None, yA=None, xB=None, yB=None):
        if line is not None: xA, yA, xB, yB = line.pointA.x, line.pointA.y, line.pointB.x, line.pointB.y
        deltaX = xA - xB
        deltaY = yA - yB
        x = float(xA)
        y = float(yA)
        Drawing.paintPixel(int(x), int(y), line.color)
        steps = max(abs(deltaX), abs(deltaY))
        if steps == 0:
            return
        xIncr = deltaX/steps
        yIncr = deltaY/steps

        for _ in range(int(steps)):
            x -= xIncr
            y -= yIncr
            # Pela forma como float funciona é necessário o "+ 0.000001" para garantir que frações que gerem 5 no final sejam aproximadas pra cima
            Drawing.paintPixel(round(x + 0.000001), round(y+ 0.000001), line.color)




class BresenhamLines:
    def __init__(self):
        pass

    @staticmethod
    def rasterizeLine(line=None, xA=None, yA=None, xB=None, yB=None):
            if line is not None: xA, yA, xB, yB = line.pointA.x, line.pointA.y, line.pointB.x, line.pointB.y
            deltaX, deltaY = int(xB - xA), int(yB - yA)
            x, y = int(xA), int(yA)
            Drawing.paintPixel(x, y, line.color)

            if deltaX > 0: xIncr = 1
            else: xIncr, deltaX = -1, -deltaX

            if deltaY > 0: yIncr = 1
            else: yIncr, deltaY = -1, -deltaY

            if deltaX > deltaY:
                p = 2*deltaY - deltaX
                const1 = 2*deltaY
                const2 = 2*(deltaY-deltaX)
                for _ in range(deltaX):
                    x += xIncr
                    if p < 0: p += const1
                    else: 
                        p += const2 
                        y += yIncr
                    Drawing.paintPixel(x, y, line.color)
            else:
                p = 2*deltaX - deltaY
                const1 = 2*deltaX
                const2 = 2*(deltaX-deltaY)
                for _ in range(deltaY):
                    y += yIncr
                    if p < 0: p += const1
                    else: 
                        p += const2 
                        x += xIncr
                    Drawing.paintPixel(x, y, line.color)



class BresenhamCircle:
    def __init__(self):
        pass

    @staticmethod
    def drawSimmetry(a, b, xc, yc, color):
        Drawing.paintPixel(a+xc, b+yc, color)
        Drawing.paintPixel(a+xc, -b+yc, color)
        Drawing.paintPixel(-a+xc, b+yc, color)
        Drawing.paintPixel(-a+xc, -b+yc, color)
        Drawing.paintPixel(b+xc, a+yc, color)
        Drawing.paintPixel(b+xc, -a+yc, color)
        Drawing.paintPixel(-b+xc, a+yc, color)
        Drawing.paintPixel(-b+xc, -a+yc, color)
        
    def rasterize(self, circle):
        x = 0
        y = circle.radius
        p = 3 - 2*circle.radius
        self.drawSimmetry(x, y, circle.center.x, circle.center.y, circle.color)
        while(x < y):
            if p < 0: p += 4*x + 6
            else :
                p += 4*(x-y) + 10
                y -= 1
            x += 1
            self.drawSimmetry(x, y, circle.center.x, circle.center.y, circle.color)


        


## Recorte

# Recorte Cohen-Sutherland
class ClippingCS:
    def __init__(self, xMin, xMax, yMin, yMax):
        self.xMin = xMin
        self.xMax = xMax
        self.yMin = yMin
        self.yMax = yMax

    def _get_code(self, x, y):
        code = 0
        if x < self.xMin: code |= 1     # bit 0: esquerda
        if x > self.xMax: code |= 2     # bit 1: direita
        if y < self.yMin: code |= 4     # bit 2: abaixo
        if y > self.yMax: code |= 8     # bit 3: acima
        return code

    def clip_line(self, line: Line) -> Line | None:
        pointA = Point(line.pointA.x, line.pointA.y)
        pointB = Point(line.pointB.x, line.pointB.y)
        accept = False
        done = False

        while not done:
            codeA = self._get_code(pointA.x, pointA.y)
            codeB = self._get_code(pointB.x, pointB.y)

            if codeA == 0 and codeB == 0:
                accept = True
                done = True
            elif (codeA & codeB) != 0:
                done = True
            else:
                if codeA != 0:
                    cOut = codeA
                    x, y = pointA.x, pointA.y
                else:
                    cOut = codeB
                    x, y = pointB.x, pointB.y

                if cOut & 1:
                    xInt = self.xMin
                    yInt = y + (pointB.y - pointA.y) * ((self.xMin - x) / (pointB.x - pointA.x))
                elif cOut & 2:
                    xInt = self.xMax
                    yInt = y + (pointB.y - pointA.y) * ((self.xMax - x) / (pointB.x - pointA.x))
                elif cOut & 4:
                    yInt = self.yMin
                    xInt = x + (pointB.x - pointA.x) * ((self.yMin - y) / (pointB.y - pointA.y))
                else:  # cOut & 8
                    yInt = self.yMax
                    xInt = x + (pointB.x - pointA.x) * ((self.yMax - y) / (pointB.y - pointA.y))

                if cOut == codeA:
                    pointA.x, pointA.y = round(xInt + 0.000001), round(yInt + 0.000001)
                else:
                    pointB.x, pointB.y = round(xInt + 0.000001), round(yInt + 0.000001)

        if accept:
            return Line(Point(pointA.x, pointA.y), Point(pointB.x, pointB.y), getattr(line, 'color', None))
        return None

# Recorte Liang-Barsky
class ClippingLB:
    def __init__(self, xMin, xMax, yMin, yMax):
        self.xMin = xMin
        self.xMax = xMax
        self.yMin = yMin
        self.yMax = yMax

    @staticmethod
    def _clipTest(p, q, uA, uB):
        result = True
        if p < 0:
            r = q / p
            if r > uB:
                result = False
            elif r > uA:
                uA = r
        elif p > 0:
            r = q / p
            if r < uA:
                result = False
            elif r < uB:
                uB = r
        elif q < 0:
            result = False
        return result, uA, uB

    def clip_line(self, line: Line) -> Line | None:
        xA, yA = line.pointA.x, line.pointA.y
        xB, yB = line.pointB.x, line.pointB.y
        uA, uB = 0.0, 1.0
        deltaX, deltaY = xB - xA, yB - yA
        ok, uA, uB = self._clipTest(-deltaX, xA - self.xMin, uA, uB)
        if ok:
            ok, uA, uB = self._clipTest(deltaX, self.xMax - xA, uA, uB)
            if ok:
                ok, uA, uB = self._clipTest(-deltaY, yA - self.yMin, uA, uB)
                if ok:
                    ok, uA, uB = self._clipTest(deltaY, self.yMax - yA, uA, uB)
                    if ok:
                        if uB < 1.0:
                            xB = xA + deltaX * uB
                            yB = yA + deltaY * uB
                        if uA > 0.0:
                            xA = xA + deltaX * uA
                            yA = yA + deltaY * uA
                        return Line(Point(round(xA + 0.000001), round(yA + 0.000001)),
                                    Point(round(xB + 0.000001), round(yB + 0.000001)),
                                    getattr(line, 'color', None))
        return None


