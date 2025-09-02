from PyQt6 import uic, QtWidgets, QtGui, QtCore
import sys
import os
import json

from utils.drawable import Drawing, Point, Line, Circle, Poligon
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

	def paintEvent(self, event):
		painter = QtGui.QPainter(self)
		# scale buffer to widget size using fast transformation (nearest-neighbor) to keep pixels sharp
		scaled = self.buffer.scaled(self.width(), self.height(), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.FastTransformation)
		painter.drawImage(0, 0, scaled)
		# draw selection bbox if any (converted to widget coords)
		sel = self.controller.selected_index
		if sel is not None and 0 <= sel < len(self.controller.objects):
			obj = self.controller.objects[sel]
			rect_buf = self.controller.compute_bounding_rect_buf(obj)
			if rect_buf:
				rect_widget = self.buffer_rect_to_widget(rect_buf)
				pen = QtGui.QPen(QtGui.QColor('blue'))
				pen.setStyle(QtCore.Qt.PenStyle.DashLine)
				pen.setWidth(2)
				painter.setPen(pen)
				painter.drawRect(rect_widget)

	def set_pixel(self, x, y, color):
		# x,y are in buffer coordinates
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
		self.current_color = '#c80000'
		self.current_tool = 'point'
		self.objects = []  # list of dicts: {type, obj, color}
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
		self.btnSave.clicked.connect(self.action_save)
		self.btnLoad.clicked.connect(self.action_load)
		self.btnExport.clicked.connect(self.action_export)
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
		# request buffer resolution (small) to make raster differences visible
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

	def action_save(self):
		path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Salvar projeto', filter='JSON Files (*.json)')
		if not path: return
		data = {
			'buffer_width': self.canvas.buffer_w,
			'buffer_height': self.canvas.buffer_h,
			'objects': []
		}
		for item in self.objects:
			typ = item['type']
			col = item.get('color', '#000')
			if typ == 'point':
				p = item['obj']
				data['objects'].append({'type':'point','x':p.x,'y':p.y,'color':col})
			elif typ == 'line':
				l = item['obj']
				data['objects'].append({'type':'line','ax':l.pointA.x,'ay':l.pointA.y,'bx':l.pointB.x,'by':l.pointB.y,'color':col})
			elif typ == 'circle':
				c = item['obj']
				data['objects'].append({'type':'circle','cx':c.center.x,'cy':c.center.y,'r':c.radius,'color':col})
			elif typ == 'polygon':
				lines = item['obj'].Lines
				pts = []
				for ln in lines:
					pts.append({'ax':ln.pointA.x,'ay':ln.pointA.y,'bx':ln.pointB.x,'by':ln.pointB.y})
				data['objects'].append({'type':'polygon','lines':pts,'color':col})
		with open(path, 'w') as f:
			json.dump(data, f, indent=2)

	def action_load(self):
		path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Abrir projeto', filter='JSON Files (*.json)')
		if not path: return
		with open(path, 'r') as f:
			data = json.load(f)
		# recreate canvas with buffer size from file
		bw, bh = data.get('buffer_width', 80), data.get('buffer_height', 80)
		self.canvas.setParent(None)
		self.canvas = CanvasWidget(self, buffer_width=bw, buffer_height=bh)
		Drawing.set_canvas(self.canvas)
		self.canvasPlaceholder.layout().addWidget(self.canvas)
		self.canvas.clear()
		self.objects.clear()
		self.listObjects.clear()
		for obj in data.get('objects', []):
			col = obj.get('color', '#000')
			if obj['type'] == 'point':
				p = Point(obj['x'], obj['y'])
				self.add_object('point', p, col)
			elif obj['type'] == 'line':
				a = Point(obj['ax'], obj['ay'])
				b = Point(obj['bx'], obj['by'])
				self.add_object('line', Line(a,b), col)
			elif obj['type'] == 'circle':
				c = Circle(Point(obj['cx'], obj['cy']), obj['r'])
				self.add_object('circle', c, col)
			elif obj['type'] == 'polygon':
				lines = []
				for ln in obj['lines']:
					lines.append(Line(Point(ln['ax'],ln['ay']), Point(ln['bx'],ln['by'])))
				poly = Poligon(lines)
				self.add_object('polygon', poly, col)
		self.redraw_all()

	def action_export(self):
		path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Exportar PNG', filter='PNG Files (*.png)')
		if not path: return
		# save the buffer scaled to the current widget size for better visibility
		scaled = self.canvas.buffer.scaled(self.canvas.width(), self.canvas.height(), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.FastTransformation)
		scaled.save(path)

	def add_object(self, typ, obj, color):
		self.objects.append({'type':typ,'obj':obj,'color':color})
		self.listObjects.addItem(f"{typ} #{len(self.objects)-1}")

	def redraw_all(self):
		self.canvas.clear()
		for item in self.objects:
			typ = item['type']
			col = item.get('color', '#000')
			if typ == 'point':
				p = item['obj']
				Drawing.paintPixel(int(p.x), int(p.y), col)
			elif typ == 'line':
				l = item['obj']
				# clip if needed
				clip = self.comboClipping.currentText()
				if clip == 'Cohen-Sutherland':
					cs = ClippingCS(0, self.canvas.buffer_w-1, 0, self.canvas.buffer_h-1)
					clipped = cs.clip(l.pointA, l.pointB)
					if clipped is not None:
						ldraw = clipped
					else:
						ldraw = None
				else:
					ldraw = l
				if ldraw:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(ldraw, col)
					else:
						BresenhamLines().rasterizeLine(ldraw, col)
			elif typ == 'circle':
				c = item['obj']
				BresenhamCircle().rasterize(c, col)
			elif typ == 'polygon':
				poly = item['obj']
				for ln in poly.Lines:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(ln, item.get('color', '#000'))
					else:
						BresenhamLines().rasterizeLine(ln, item.get('color', '#000'))

	def on_list_selection(self):
		items = self.listObjects.selectedIndexes()
		if items:
			self.selected_index = items[0].row()
		else:
			self.selected_index = None
		self.canvas.update()

	def compute_bounding_rect(self, item):
		typ = item['type']
		xs, ys = [], []
		if typ == 'point':
			p = item['obj']
			xs = [p.x]
			ys = [p.y]
		elif typ == 'line':
			l = item['obj']
			xs = [l.pointA.x, l.pointB.x]
			ys = [l.pointA.y, l.pointB.y]
		elif typ == 'circle':
			c = item['obj']
			xs = [c.center.x - c.radius, c.center.x + c.radius]
			ys = [c.center.y - c.radius, c.center.y + c.radius]
		elif typ == 'polygon':
			for ln in item['obj'].Lines:
				xs += [ln.pointA.x, ln.pointB.x]
				ys += [ln.pointA.y, ln.pointB.y]
		if not xs: return None
		x1, x2 = int(min(xs)), int(max(xs))
		y1, y2 = int(min(ys)), int(max(ys))
		return QtCore.QRect(x1, y1, x2 - x1, y2 - y1)

	def compute_bounding_rect_buf(self, item):
		# same as compute_bounding_rect but returns QRect in buffer coordinates
		return self.compute_bounding_rect(item)

	def on_canvas_left_click(self, x, y):
		# map widget coords to buffer coords
		bx, by = self.canvas.widget_to_buffer(x, y)
		if self.current_tool == 'point':
			p = Point(bx, by)
			self.add_object('point', p, self.current_color)
			Drawing.paintPixel(bx, by, self.current_color)
		elif self.current_tool == 'line':
			self.temp_points.append((bx,by))
			if len(self.temp_points) == 2:
				a = Point(*self.temp_points[0])
				b = Point(*self.temp_points[1])
				l = Line(a,b)
				self.add_object('line', l, self.current_color)
				# draw
				if self.comboClipping.currentText() == 'Cohen-Sutherland':
					cs = ClippingCS(0, self.canvas.buffer_w-1, 0, self.canvas.buffer_h-1)
					clipped = cs.clip(a,b)
					if clipped:
						if self.comboRender.currentText() == 'DDA':
							DDA().rasterizeLine(clipped, self.current_color)
						else:
							BresenhamLines().rasterizeLine(clipped, self.current_color)
				else:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(l, self.current_color)
					else:
						BresenhamLines().rasterizeLine(l, self.current_color)
				self.temp_points = []
		elif self.current_tool == 'circle':
			self.temp_points.append((bx,by))
			if len(self.temp_points) == 2:
				cx, cy = self.temp_points[0]
				x2, y2 = self.temp_points[1]
				r = int(((cx-x2)**2 + (cy-y2)**2)**0.5)
				c = Circle(Point(cx,cy), r)
				self.add_object('circle', c, self.current_color)
				BresenhamCircle().rasterize(c, self.current_color)
				self.temp_points = []
		elif self.current_tool == 'polygon':
			# append point; expect user to double-click to finish
			self.temp_points.append((bx,by))
			if len(self.temp_points) > 1 and (abs(bx - self.temp_points[0][0]) < 3 and abs(by - self.temp_points[0][1]) < 3 and len(self.temp_points) > 2):
				# close polygon
				pts = self.temp_points[:-1]
				lines = []
				for i in range(len(pts)):
					a = Point(*pts[i])
					b = Point(*pts[(i+1)%len(pts)])
					lines.append(Line(a,b))
				poly = Poligon(lines)
				self.add_object('polygon', poly, self.current_color)
				for ln in lines:
					if self.comboRender.currentText() == 'DDA':
						DDA().rasterizeLine(ln, self.current_color)
					else:
						BresenhamLines().rasterizeLine(ln, self.current_color)
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
				ang, ok = QtWidgets.QInputDialog.getDouble(self, 'Rotacionar', 'angulo (graus):', 0.0)
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
		typ = item['type']
		if typ == 'point':
			p = item['obj']
			p.x += dx; p.y += dy
		elif typ == 'line':
			l = item['obj']
			l.pointA.x += dx; l.pointA.y += dy
			l.pointB.x += dx; l.pointB.y += dy
		elif typ == 'circle':
			c = item['obj']
			c.center.x += dx; c.center.y += dy
		elif typ == 'polygon':
			for ln in item['obj'].Lines:
				ln.pointA.x += dx; ln.pointA.y += dy
				ln.pointB.x += dx; ln.pointB.y += dy
		self.redraw_all()

	def apply_rotation(self, idx, angle_deg):
		item = self.objects[idx]
		# rotate around center
		rect = self.compute_bounding_rect(item)
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2
		for (x_ref,y_ref) in []:
			pass
		def rot_point(px,py):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.rotate(nx, ny, angle_deg)
			return rx + cx, ry + cy

		typ = item['type']
		if typ == 'point':
			p = item['obj']
			p.x, p.y = rot_point(p.x, p.y)
		elif typ == 'line':
			l = item['obj']
			l.pointA.x, l.pointA.y = rot_point(l.pointA.x, l.pointA.y)
			l.pointB.x, l.pointB.y = rot_point(l.pointB.x, l.pointB.y)
		elif typ == 'circle':
			c = item['obj']
			c.center.x, c.center.y = rot_point(c.center.x, c.center.y)
		elif typ == 'polygon':
			for ln in item['obj'].Lines:
				ln.pointA.x, ln.pointA.y = rot_point(ln.pointA.x, ln.pointA.y)
				ln.pointB.x, ln.pointB.y = rot_point(ln.pointB.x, ln.pointB.y)
		self.redraw_all()

	def apply_scale(self, idx, sx, sy):
		item = self.objects[idx]
		rect = self.compute_bounding_rect(item)
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2
		def sc(px,py):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.scale(nx, ny, sx, sy)
			return rx + cx, ry + cy
		typ = item['type']
		if typ == 'point':
			p = item['obj']
			p.x, p.y = sc(p.x, p.y)
		elif typ == 'line':
			l = item['obj']
			l.pointA.x, l.pointA.y = sc(l.pointA.x, l.pointA.y)
			l.pointB.x, l.pointB.y = sc(l.pointB.x, l.pointB.y)
		elif typ == 'circle':
			c = item['obj']
			c.center.x, c.center.y = sc(c.center.x, c.center.y)
			c.radius = int(c.radius * (sx+sy)/2)
		elif typ == 'polygon':
			for ln in item['obj'].Lines:
				ln.pointA.x, ln.pointA.y = sc(ln.pointA.x, ln.pointA.y)
				ln.pointB.x, ln.pointB.y = sc(ln.pointB.x, ln.pointB.y)
		self.redraw_all()

	def apply_reflect(self, idx, axis):
		item = self.objects[idx]
		typ = item['type']
		# reflect around center
		rect = self.compute_bounding_rect(item)
		if not rect: return
		cx = rect.x() + rect.width()/2
		cy = rect.y() + rect.height()/2
		def rf(px,py):
			nx = px - cx; ny = py - cy
			rx, ry = Transformations.reflect(nx, ny, axis)
			return rx + cx, ry + cy
		if typ == 'point':
			p = item['obj']
			p.x, p.y = rf(p.x, p.y)
		elif typ == 'line':
			l = item['obj']
			l.pointA.x, l.pointA.y = rf(l.pointA.x, l.pointA.y)
			l.pointB.x, l.pointB.y = rf(l.pointB.x, l.pointB.y)
		elif typ == 'circle':
			c = item['obj']
			c.center.x, c.center.y = rf(c.center.x, c.center.y)
		elif typ == 'polygon':
			for ln in item['obj'].Lines:
				ln.pointA.x, ln.pointA.y = rf(ln.pointA.x, ln.pointA.y)
				ln.pointB.x, ln.pointB.y = rf(ln.pointB.x, ln.pointB.y)
		self.redraw_all()


def main():
	app = QtWidgets.QApplication(sys.argv)
	w = MainWindow()
	w.show()
	sys.exit(app.exec())


if __name__ == '__main__':
	main()
