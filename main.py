from PyQt6 import uic, QtWidgets, QtGui, QtCore
import sys
import os

from utils.drawable import Drawing, Point, Line, Circle, Polygon
from utils.algorithms import Transformations, DDA, BresenhamLines, BresenhamCircle, ClippingCS, ClippingLB


class CanvasWidget(QtWidgets.QWidget):
	def __init__(self, controller, buffer_width=80, buffer_height=80):
		super().__init__()
		self.controller = controller
		# logical buffer resolution (small) to show rasterization differences
		self.buffer_w = max(1, int(buffer_width))
		self.buffer_h = max(1, int(buffer_height))
		self.buffer = QtGui.QImage(self.buffer_w, self.buffer_h, QtGui.QImage.Format.Format_RGB32)
		self.buffer.fill(QtGui.QColor('white'))
		# allow the widget to expand to fill the available area
		self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
		self.setMouseTracking(True)
		self.dragging = False
		self.drag_start = None
		self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)

	# Pinta a bounding box
	def paintEvent(self, event):
		painter = QtGui.QPainter(self)
		scaled = self.buffer.scaled(self.width(), self.height(), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.FastTransformation)
		painter.drawImage(0, 0, scaled)
		sel = self.controller.selected_index
		if sel is not None and 0 <= sel < len(self.controller.objects):
			obj = self.controller.objects[sel]
			rect_buf = self.controller.compute_bounding_rect_buf(obj)
			if rect_buf:
				rect_widget = self.buffer_rect_to_widget(rect_buf)
				pen = QtGui.QPen(QtGui.QColor('purple'))
				pen.setStyle(QtCore.Qt.PenStyle.DashLine)
				pen.setWidth(2)
				painter.setPen(pen)
				painter.drawRect(rect_widget)

	# TODO: Corrigir logica
	def drawGrid(self):
		# Cria um QPainter para desenhar diretamente no buffer
		painter = QtGui.QPainter(self.buffer)
		painter.setPen(QtGui.QPen(QtGui.QColor(150, 150, 150), 1, QtCore.Qt.PenStyle.DotLine))  # Linhas cinza claro pontilhadas

		# Desenha linhas verticais
		for x in range(0, self.buffer.width()):
			painter.drawLine(x, 0, x, self.buffer.height())

		# Desenha linhas horizontais
		for y in range(0, self.buffer.height()):
			painter.drawLine(0, y, self.buffer.width(), y)

		painter.end()  # Finaliza o desenho no buffer

	def set_pixel(self, x, y, color):
		# colore pixel
		if 0 <= x < self.buffer.width() and 0 <= y < self.buffer.height():
			col = QtGui.QColor(color)
			self.buffer.setPixelColor(int(x), int(y), col)
			self.update()

	def clear(self, color='white'):
		self.buffer.fill(QtGui.QColor(color))
		self.update()

	def widget_to_buffer(self, x, y):
		# map widget coordinates to buffer coordinates
		if self.width() == 0 or self.height() == 0:
			return 0, 0
		bx = int(x * self.buffer_w / self.width())
		by = int(y * self.buffer_h / self.height())
		bx = max(0, min(self.buffer_w-1, bx))
		by = max(0, min(self.buffer_h-1, by))
		return bx, by

	def buffer_rect_to_widget(self, rect_buf):
		# rect_buf is QRect in buffer coords
		sx = self.width() / max(1, self.buffer_w)
		sy = self.height() / max(1, self.buffer_h)
		x = int(rect_buf.x() * sx)
		y = int(rect_buf.y() * sy)
		w = int(rect_buf.width() * sx)
		h = int(rect_buf.height() * sy)
		return QtCore.QRect(x, y, max(1, w), max(1, h))

	def mousePressEvent(self, event):
		xw = event.position().x(); yw = event.position().y()
		if event.button() == QtCore.Qt.MouseButton.LeftButton:
			self.controller.on_canvas_left_click(int(xw), int(yw))
		elif event.button() == QtCore.Qt.MouseButton.RightButton:
			self.controller.on_canvas_right_click(int(xw), int(yw))

	def mouseMoveEvent(self, event):
		xw = int(event.position().x()); yw = int(event.position().y())
		self.controller.on_canvas_move(xw, yw)

	def mouseReleaseEvent(self, event):
		if event.button() == QtCore.Qt.MouseButton.LeftButton:
			self.controller.on_canvas_release()


class MainWindow(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'editor.ui')
		uic.loadUi(ui_path, self)

		# state
		self.current_color = "#000000"
		self.current_tool = 'point'
		self.objects = []
		self.selected_index = None
		self.temp_points = []

		# create canvas widget inside placeholder (small buffer to highlight raster differences)
		self.canvas = CanvasWidget(self, buffer_width=80, buffer_height=80)
		Drawing.set_canvas(self.canvas)
		# ensure placeholder has a layout to host the widget
		if not hasattr(self.canvasPlaceholder, 'layout') or self.canvasPlaceholder.layout() is None:
			self.canvasPlaceholder.setLayout(QtWidgets.QVBoxLayout())
		self.canvasPlaceholder.layout().setContentsMargins(0,0,0,0)
		self.canvasPlaceholder.layout().addWidget(self.canvas)

		# connect UI
		self.colorButton.clicked.connect(self.choose_color)
		self.toolPointBtn.clicked.connect(lambda: self.set_tool('point'))
		self.toolLineBtn.clicked.connect(lambda: self.set_tool('line'))
		self.toolCircleBtn.clicked.connect(lambda: self.set_tool('circle'))
		self.toolPolyBtn.clicked.connect(lambda: self.set_tool('polygon'))
		self.btnNew.clicked.connect(self.action_new)
		self.listObjects.itemSelectionChanged.connect(self.on_list_selection)

		# initial UI setup
		self.set_tool('point')

	def set_tool(self, tool):
		self.current_tool = tool
		# if switching tool, reset temp
		self.temp_points = []

	def choose_color(self):
		col = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
		if col.isValid():
			self.current_color = col.name()
			self.colorButton.setStyleSheet(f'background: {self.current_color};')

	def action_new(self):
		# request buffer resolution
		w, ok = QtWidgets.QInputDialog.getInt(self, 'Largura (pixels)', 'Largura (buffer):', 80, 4, 200)
		if not ok: return
		h, ok = QtWidgets.QInputDialog.getInt(self, 'Altura (pixels)', 'Altura (buffer):', 80, 4, 200)
		if not ok: return
		# recreate canvas with small logical buffer
		self.canvas.setParent(None)
		self.canvas = CanvasWidget(self, buffer_width=w, buffer_height=h)
		Drawing.set_canvas(self.canvas)
		self.canvasPlaceholder.layout().addWidget(self.canvas)
		self.canvas.clear()
		self.objects.clear()
		self.listObjects.clear()
		self.selected_index = None
		self.canvas.drawGrid()



	def add_object(self, obj):
		self.objects.append({'obj':obj})
		if isinstance(obj,Point):
			self.listObjects.addItem(f"Point #{len(self.objects)-1}")
		elif isinstance(obj,Line):
			self.listObjects.addItem(f"Line #{len(self.objects)-1}")
		elif isinstance(obj,Circle):
			self.listObjects.addItem(f"Circle #{len(self.objects)-1}")
		elif isinstance(obj,Polygon):
			self.listObjects.addItem(f"Polygon #{len(self.objects)-1}")

	def redraw_all(self):
		self.canvas.clear()
		for item in self.objects:
			item = item['obj'] 
			if isinstance(item, Point):
				Drawing.paintPixel(int(item.x), int(item.y), item.color)
			elif isinstance(item, Line):
				if self.comboRender.currentText() == 'DDA':
					DDA().rasterizeLine(item)
				else:
					BresenhamLines().rasterizeLine(item)
			elif isinstance(item, Circle):
				BresenhamCircle().rasterize(item)
			elif isinstance(item, Polygon):
				for ln in item.lines:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(ln)
					else:
						BresenhamLines().rasterizeLine(ln)

	def on_list_selection(self):
		items = self.listObjects.selectedIndexes()
		if items:
			self.selected_index = items[0].row()
			item = self.objects[self.selected_index]
			item = item['obj']
			print(item.__str__())
		else:
			self.selected_index = None
		self.canvas.update()

	def compute_bounding_rect(self, item):
		item = item['obj'] 
		xs, ys = [], []
		if isinstance(item, Point):
			xs = [item.x, item.x]
			ys = [item.y, item.y]
		elif isinstance(item, Line):
			xs = [item.pointA.x, item.pointB.x]
			ys = [item.pointA.y, item.pointB.y]
		elif isinstance(item, Circle):
			xs = [item.center.x - item.radius, item.center.x + item.radius]
			ys = [item.center.y - item.radius, item.center.y + item.radius]
		elif isinstance(item, Polygon):
			for ln in item.lines:
				xs += [ln.pointA.x, ln.pointB.x]
				ys += [ln.pointA.y, ln.pointB.y]
		if not xs: return None
		x1, x2 = int(min(xs)), int(max(xs))
		y1, y2 = int(min(ys)), int(max(ys))
		return QtCore.QRect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)

	def compute_bounding_rect_buf(self, item):
		# same as compute_bounding_rect but returns QRect in buffer coordinates
		return self.compute_bounding_rect(item)

	def on_canvas_left_click(self, x, y):
		# map widget coords to buffer coords
		bx, by = self.canvas.widget_to_buffer(x, y)
		if self.current_tool == 'point':
			p = Point(bx, by, self.current_color)
			self.add_object(p)
			Drawing.paintPixel(p.x, p.y, p.color)
		elif self.current_tool == 'line':
			self.temp_points.append((bx,by))
			if len(self.temp_points) == 2:
				a = Point(*self.temp_points[0])
				b = Point(*self.temp_points[1])
				l = Line(a,b, self.current_color)
				self.add_object(l)
				# draw
				if self.comboRender.currentText() == 'DDA':
					DDA().rasterizeLine(line=l)
				else:
					BresenhamLines().rasterizeLine(line=l)
				self.temp_points = []
		elif self.current_tool == 'circle':
			self.temp_points.append((bx,by))
			if len(self.temp_points) == 2:
				cx, cy = self.temp_points[0]
				x2, y2 = self.temp_points[1]
				r = int(((cx-x2)**2 + (cy-y2)**2)**0.5)
				c = Circle(Point(cx,cy), r, self.current_color)
				self.add_object(c)
				BresenhamCircle().rasterize(c)
				self.temp_points = []
		elif self.current_tool == 'polygon':
			# append point; expect user to return to origin to finish
			self.temp_points.append((bx,by))
			if len(self.temp_points) > 1 and (abs(bx - self.temp_points[0][0]) < 3 and abs(by - self.temp_points[0][1]) < 3 and len(self.temp_points) > 2):
				# close polygon
				pts = self.temp_points[:-1]
				lines = []
				for i in range(len(pts)):
					a = Point(*pts[i])
					b = Point(*pts[(i+1)%len(pts)])
					lines.append(Line(a,b, self.current_color))
				poly = Polygon(lines)
				self.add_object(poly)
				for ln in lines:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(ln)
					else:
						BresenhamLines().rasterizeLine(ln)
				self.temp_points = []

	def on_canvas_right_click(self, x, y):
		# if click inside selected object's bbox, show transform menu
		if self.selected_index is None: return
		item = self.objects[self.selected_index]
		# map widget click to buffer coords
		bx, by = self.canvas.widget_to_buffer(x, y)
		rect = self.compute_bounding_rect(item)
		if rect and rect.contains(bx,by):
			menu = QtWidgets.QMenu(self)
			t_translate = menu.addAction('Transladar')
			t_rotate = menu.addAction('Rotacionar')
			t_scale = menu.addAction('Escalar')
			t_reflect = menu.addAction('Refletir')
			action = menu.exec(QtGui.QCursor.pos())
			if action == t_translate:
				dx, ok = QtWidgets.QInputDialog.getInt(self, 'Transladar', 'dx:', 0)
				if not ok: return
				dy, ok = QtWidgets.QInputDialog.getInt(self, 'Transladar', 'dy:', 0)
				if not ok: return
				self.apply_translation(self.selected_index, dx, dy)
			elif action == t_rotate:
				ang, ok = QtWidgets.QInputDialog.getDouble(self, 'Rotacionar', 'Ângulo (graus):', 0.0)
				if not ok: return
				self.apply_rotation(self.selected_index, ang)
			elif action == t_scale:
				sx, ok = QtWidgets.QInputDialog.getDouble(self, 'Escalar', 'scaleX:', 1.0)
				if not ok: return
				sy, ok = QtWidgets.QInputDialog.getDouble(self, 'Escalar', 'scaleY:', 1.0)
				if not ok: return
				self.apply_scale(self.selected_index, sx, sy)
			elif action == t_reflect:
				items = ['x','y','yx']
				txt, ok = QtWidgets.QInputDialog.getItem(self, 'Refletir', 'axis:', items, 0, False)
				if not ok: return
				self.apply_reflect(self.selected_index, txt)

	def on_canvas_move(self, x, y):
		# support dragging selected object by left mouse + move (simple approach)
		if QtWidgets.QApplication.mouseButtons() & QtCore.Qt.MouseButton.LeftButton:
			if self.selected_index is not None and hasattr(self, 'last_drag_pos') and self.last_drag_pos is not None:
				dx = x - self.last_drag_pos[0]
				dy = y - self.last_drag_pos[1]
				self.apply_translation(self.selected_index, dx, dy)
				self.last_drag_pos = (x,y)
		else:
			# update last pos when mouse pressed in bbox
			pass

	def on_canvas_release(self):
		self.last_drag_pos = None

	def apply_translation(self, idx, dx, dy):
		item = self.objects[idx]
		item = item['obj']
		if isinstance(item,Point):
			item.x,item.y = Transformations.translate(item.x, item.y, dx, dy)
		elif isinstance(item,Line):
			item.pointA.x,item.pointA.y = Transformations.translate(item.pointA.x,item.pointA.y, dx, dy)
			item.pointB.x,item.pointB.y = Transformations.translate(item.pointB.x,item.pointB.y, dx, dy)
		elif isinstance(item,Circle):
			item.center.x,item.center.y = Transformations.translate(item.center.x, item.center.y, dx, dy)
		elif isinstance(item,Polygon):
			for ln in item.lines:
				ln.pointA.x,ln.pointA.y = Transformations.translate(ln.pointA.x,ln.pointA.y, dx, dy)
				ln.pointB.x,ln.pointB.y = Transformations.translate(ln.pointB.x,ln.pointB.y, dx, dy)
		self.redraw_all()

	#TODO: select a point in the object as rotation origin
	def apply_rotation(self, idx, angle_deg):
		item = self.objects[idx]
		rect = self.compute_bounding_rect(item)
		item = item['obj']
		
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2

		#rotate around point (center)
		def rot_point(px,py):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.rotate(nx, ny, angle_deg)
			return round(rx + cx + 0.000001), round(ry + cy + 0.000001)

		if isinstance(item,Point):
			item.x, item.y = rot_point(item.x, item.y)
		elif isinstance(item,Line):
			item.pointA.x, item.pointA.y = rot_point(item.pointA.x, item.pointA.y)
			item.pointB.x, item.pointB.y = rot_point(item.pointB.x, item.pointB.y)
		elif isinstance(item,Circle):
			item.center.x, item.center.y = rot_point(item.center.x, item.center.y)
		elif isinstance(item,Polygon):
			for ln in item.lines:
				ln.pointA.x, ln.pointA.y = rot_point(ln.pointA.x, ln.pointA.y)
				ln.pointB.x, ln.pointB.y = rot_point(ln.pointB.x, ln.pointB.y)
		self.redraw_all()

	#TODO: select a point in the object as scale origin
	def apply_scale(self, idx, sx, sy):
		item = self.objects[idx]
		rect = self.compute_bounding_rect(item)
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2

		#scale around point (center)
		def sc(px,py):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.scale(nx, ny, sx, sy)
			return round(rx + cx + 0.000001), round(ry + cy + 0.000001)
		
		obj = item['obj']
		if isinstance(obj,Point):
			obj.x, obj.y = sc(obj.x, obj.y)
		elif isinstance(obj,Line):
			obj.pointA.x, obj.pointA.y = sc(obj.pointA.x, obj.pointA.y)
			obj.pointB.x, obj.pointB.y = sc(obj.pointB.x, obj.pointB.y)
			print("bosta")
		elif isinstance(obj,Circle):
			obj.center.x, obj.center.y = sc(obj.center.x, obj.center.y)
			obj.radius = int(obj.radius * (sx+sy)/2)
		elif isinstance(obj,Polygon):
			for ln in obj.lines:
				ln.pointA.x, ln.pointA.y = sc(ln.pointA.x, ln.pointA.y)
				ln.pointB.x, ln.pointB.y = sc(ln.pointB.x, ln.pointB.y)
		self.redraw_all()

	#TODO: select a point in the object as reflect origin
	def apply_reflect(self, idx, axis):
		item = self.objects[idx]
		rect = self.compute_bounding_rect(item)
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2
		item = item['obj']

		#reflect around point (center)
		def rft(px, py, axis):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.reflect(nx, ny, axis)
			return round(rx + cx + 0.000001), round(ry + cy + 0.000001)

		if isinstance(item,Point):
			item.x,item.y = rft(item.x, item.y, axis=axis)
		elif isinstance(item,Line):
			item.pointA.x,item.pointA.y = rft(item.pointA.x,item.pointA.y, axis=axis)
			item.pointB.x,item.pointB.y = rft(item.pointB.x,item.pointB.y, axis=axis)
		elif isinstance(item,Circle):
			item.center.x,item.center.y = rft(item.center.x, item.center.y,axis=axis)
		elif isinstance(item,Polygon):
			for ln in item.lines:
				ln.pointA.x,item.pointA.y = rft(ln.pointA.x,ln.pointA.y,axis=axis)
				ln.pointB.x,item.pointB.y = rft(ln.pointB.x,ln.pointB.y,axis=axis)
		self.redraw_all()


def main():
	app = QtWidgets.QApplication(sys.argv)
	w = MainWindow()
	w.show()
	sys.exit(app.exec())


if __name__ == '__main__':
	main()
