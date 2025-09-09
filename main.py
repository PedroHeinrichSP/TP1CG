"""Aplicação PyQt para desenho e transformações 2D.

Este módulo provê a janela principal e o widget de canvas com buffer lógico
pequeno para evidenciar algoritmos de rasterização (DDA/Bresenham), além de
operações de recorte (Cohen–Sutherland, Liang–Barsky) e transformações
geométricas (translação, rotação, escala e reflexão).
"""

from PyQt6 import uic, QtWidgets, QtGui, QtCore
import sys
import os

from utils.drawable import Drawing, Point, Line, Circle, Polygon
from utils.algorithms import Transformations, DDA, BresenhamLines, BresenhamCircle, ClippingCS, ClippingLB

class CanvasWidget(QtWidgets.QWidget):
	"""Widget de desenho com buffer lógico.

	Mantém uma QImage de baixa resolução (buffer_w x buffer_h) que é escalada
	para o tamanho do widget, facilitando a visualização dos pixels.
	"""

	def __init__(self, controller, buffer_width=80, buffer_height=80):
		super().__init__()
		self.controller = controller
		# resolução lógica do buffer (pequena para evidenciar rasterização)
		self.buffer_w = max(1, int(buffer_width))
		self.buffer_h = max(1, int(buffer_height))
		self.buffer = QtGui.QImage(self.buffer_w, self.buffer_h, QtGui.QImage.Format.Format_RGB32)
		self.buffer.fill(QtGui.QColor('white'))
		# permite expandir para ocupar a área disponível
		self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
		self.setMouseTracking(True)
		self.dragging = False
		self.drag_start = None
		self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
		# retângulo de recorte lógico em coords de buffer (limitador de escrita)
		self.clip_rect = None
		# retângulo de seleção (overlay) em coords de widget (durante arrasto)
		self.drag_select_start = None
		self.drag_select_end = None
		# grade (linhas) sobre o canvas
		self.show_grid = True
		# pivô (coords de buffer) para transformações
		self.pivot_point = None

	def paintEvent(self, event):
		"""Desenha a imagem de buffer escalada e sobreposições (grade, seleção, pivô)."""
		painter = QtGui.QPainter(self)
		scaled = self.buffer.scaled(self.width(), self.height(), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio, QtCore.Qt.TransformationMode.FastTransformation)
		painter.drawImage(0, 0, scaled)
		# grade entre pixels para facilitar contagem/visualização
		if self.show_grid and self.buffer_w > 0 and self.buffer_h > 0:
			pen = QtGui.QPen(QtGui.QColor(180, 180, 180, 160))
			pen.setCosmetic(True)
			pen.setWidth(1)
			painter.setPen(pen)
			cell_w = self.width() / self.buffer_w
			cell_h = self.height() / self.buffer_h
			# linhas verticais
			for i in range(1, self.buffer_w):
				x = round(i * cell_w)
				painter.drawLine(x, 0, x, self.height())
			# linhas horizontais
			for j in range(1, self.buffer_h):
				y = round(j * cell_h)
				painter.drawLine(0, y, self.width(), y)
			# borda externa
			painter.drawRect(0, 0, self.width()-1, self.height()-1)
		# retângulo de seleção durante o arrasto
		if self.drag_select_start and self.drag_select_end:
			pen = QtGui.QPen(QtGui.QColor(0, 180, 255))
			pen.setStyle(QtCore.Qt.PenStyle.DashLine)
			pen.setWidth(2)
			painter.setPen(pen)
			rect = QtCore.QRect(self.drag_select_start, self.drag_select_end).normalized()
			painter.drawRect(rect)
		rect_buf = self.controller.get_selected_rect_buf()
		if rect_buf:
			rect_widget = self.buffer_rect_to_widget(rect_buf)
			pen = QtGui.QPen(QtGui.QColor('purple'))
			pen.setStyle(QtCore.Qt.PenStyle.DashLine)
			pen.setWidth(2)
			painter.setPen(pen)
			painter.drawRect(rect_widget)

		# marca do pivô (cruz) no pixel selecionado
		if self.pivot_point is not None:
			bx, by = self.pivot_point
			sx = self.width() / max(1, self.buffer_w)
			sy = self.height() / max(1, self.buffer_h)
			# alinhar com o retângulo do pixel para combinar com a grade
			x0 = int(round(bx * sx))
			x1 = int(round((bx + 1) * sx)) - 1
			y0 = int(round(by * sy))
			y1 = int(round((by + 1) * sy)) - 1
			cx = (x0 + x1) // 2
			cy = (y0 + y1) // 2
			pen = QtGui.QPen(QtGui.QColor(220, 50, 50))
			pen.setWidth(2)
			painter.setPen(pen)
			painter.drawLine(cx-6, cy, cx+6, cy)
			painter.drawLine(cx, cy-6, cx, cy+6)

	def drawGrid(self, show: bool = True):
		"""Liga/desliga a grade de visualização."""
		self.show_grid = show
		self.update()

	def set_pixel(self, x, y, color):
		"""Define a cor de um pixel no buffer, respeitando o recorte ativo."""
		if 0 <= x < self.buffer.width() and 0 <= y < self.buffer.height():
			if self.clip_rect is not None:
				if not self.clip_rect.contains(int(x), int(y)):
					return
			col = QtGui.QColor(color)
			self.buffer.setPixelColor(int(x), int(y), col)
			self.update()

	def clear(self, color='white'):
		"""Limpa o buffer com a cor especificada."""
		self.buffer.fill(QtGui.QColor(color))
		self.update()

	def widget_to_buffer(self, x, y):
		"""Converte coords do widget para coords do buffer lógico."""
		if self.width() == 0 or self.height() == 0:
			return 0, 0
		bx = int(x * self.buffer_w / self.width())
		by = int(y * self.buffer_h / self.height())
		bx = max(0, min(self.buffer_w-1, bx))
		by = max(0, min(self.buffer_h-1, by))
		return bx, by

	def buffer_rect_to_widget(self, rect_buf):
		"""Converte um QRect em coords de buffer para coords do widget."""
		sx = self.width() / max(1, self.buffer_w)
		sy = self.height() / max(1, self.buffer_h)
		x = int(rect_buf.x() * sx)
		y = int(rect_buf.y() * sy)
		w = int(rect_buf.width() * sx)
		h = int(rect_buf.height() * sy)
		return QtCore.QRect(x, y, max(1, w), max(1, h))

	def set_clip_rect(self, rect_buf: QtCore.QRect | None):
		"""Define o retângulo de recorte ativo (coords de buffer) ou limpa-o."""
		self.clip_rect = rect_buf
		self.update()

	def set_pivot(self, bx=None, by=None):
		"""Define o pivô em coords de buffer; passe None para limpar."""
		if bx is None or by is None:
			self.pivot_point = None
		else:
			self.pivot_point = (int(bx), int(by))
		self.update()

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
	"""Janela principal: gerencia objetos, ferramentas, views e canvas."""

	def __init__(self):
		super().__init__()
		ui_path = self.resource_path(os.path.join('ui', 'editor.ui'))
		uic.loadUi(ui_path, self)

		# state
		self.current_color = "#000000"
		self.current_tool = 'point'
		self.objects = []
		self.selected_index = None
		self.temp_points = []

	# cria o canvas (buffer pequeno para evidenciar diferenças de raster)
		self.canvas = CanvasWidget(self, buffer_width=80, buffer_height=80)
		Drawing.set_canvas(self.canvas)
	# garante que o placeholder tenha um layout para hospedar o widget
		if not hasattr(self.canvasPlaceholder, 'layout') or self.canvasPlaceholder.layout() is None:
			self.canvasPlaceholder.setLayout(QtWidgets.QVBoxLayout())
		self.canvasPlaceholder.layout().setContentsMargins(0,0,0,0)
		self.canvasPlaceholder.layout().addWidget(self.canvas)

	# conexões de UI
		self.colorButton.clicked.connect(self.choose_color)
		self.toolPointBtn.clicked.connect(lambda: self.set_tool('point'))
		self.toolLineBtn.clicked.connect(lambda: self.set_tool('line'))
		self.toolCircleBtn.clicked.connect(lambda: self.set_tool('circle'))
		self.toolPolyBtn.clicked.connect(lambda: self.set_tool('polygon'))
		self.btnNew.clicked.connect(self.action_new)
	# ferramenta de recorte e seleção na árvore
		self.toolClipBtn.clicked.connect(lambda: self.set_tool('clip'))
	# ferramenta de seleção do pivô
		if hasattr(self, 'toolPivotBtn'):
			self.toolPivotBtn.clicked.connect(lambda: self.set_tool('pivot'))
		self.treeObjects.itemSelectionChanged.connect(self.on_tree_selection)
	# checkbox da grade
		if hasattr(self, 'showGridCheck'):
			self.showGridCheck.setChecked(True)
			self.showGridCheck.toggled.connect(lambda v: self.canvas.drawGrid(v))

		# initial UI setup
		self.set_tool('point')

	# raiz da árvore e views
		self.views = []  # [{'name': str, 'rect': QRect, 'objects': list}]
		self.active_view = None
		self.selected_view_obj_index = None
		self.treeObjects.clear()
		root = QtWidgets.QTreeWidgetItem(["Canvas"])
		root.setData(0, QtCore.Qt.ItemDataRole.UserRole, {'type': 'root'})
		self.treeObjects.addTopLevelItem(root)
		self.tree_root = root
		self.treeObjects.expandItem(root)
		# garante um algoritmo de recorte selecionado por padrão
		if hasattr(self, 'comboClipping') and self.comboClipping.count() > 0:
			self.comboClipping.setCurrentIndex(0)

	def resource_path(self, relative_path: str) -> str:
		"""Resolve caminho de recursos (compatível com PyInstaller e dev)."""
		base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
		if os.path.isabs(relative_path):
			return relative_path
		return os.path.join(base_path, relative_path)

	def set_tool(self, tool):
		"""Seleciona a ferramenta atual (point, line, circle, polygon, clip, pivot)."""
		self.current_tool = tool
		self.temp_points = []

	def choose_color(self):
		"""Abre um seletor de cores e aplica a cor atual."""
		col = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
		if col.isValid():
			self.current_color = col.name()
			self.colorButton.setStyleSheet(f'background: {self.current_color};')

	def action_new(self):
		"""Cria um novo canvas solicitando resolução do buffer ao usuário."""
		w, ok = QtWidgets.QInputDialog.getInt(self, 'Largura (pixels)', 'Largura (buffer):', 80, 4, 200)
		if not ok: return
		h, ok = QtWidgets.QInputDialog.getInt(self, 'Altura (pixels)', 'Altura (buffer):', 80, 4, 200)
		if not ok: return
		# recria o canvas com buffer lógico pequeno
		self.canvas.setParent(None)
		self.canvas = CanvasWidget(self, buffer_width=w, buffer_height=h)
		Drawing.set_canvas(self.canvas)
		self.canvasPlaceholder.layout().addWidget(self.canvas)
		self.canvas.clear()
		self.objects.clear()
		# reseta views e árvore
		self.views = []
		self.active_view = None
		self.treeObjects.clear()
		root = QtWidgets.QTreeWidgetItem(["Canvas"])
		root.setData(0, QtCore.Qt.ItemDataRole.UserRole, {'type': 'root'})
		self.treeObjects.addTopLevelItem(root)
		self.tree_root = root
		self.treeObjects.expandItem(root)
		self.selected_index = None
		self.canvas.drawGrid()
		# limpa pivô
		self.canvas.set_pivot(None, None)

	def add_object(self, obj):
		"""Adiciona um objeto à lista e à árvore de objetos."""
		self.objects.append({'obj':obj})
		idx = len(self.objects)-1
		label = obj.__class__.__name__ + f" #{idx}"
		node = QtWidgets.QTreeWidgetItem([label])
		node.setData(0, QtCore.Qt.ItemDataRole.UserRole, {'type': 'object', 'index': idx})
		self.tree_root.addChild(node)
		self.treeObjects.expandItem(self.tree_root)

	def draw_objects(self, obj_list):
		"""Desenha uma lista de objetos usando o algoritmo selecionado."""
		for o in obj_list:
			if isinstance(o, Point):
				Drawing.paintPixel(int(o.x), int(o.y), o.color)
			elif isinstance(o, Line):
				if self.comboRender.currentText() == 'DDA':
					DDA.rasterizeLine(o)
				else:
					BresenhamLines.rasterizeLine(o)
			elif isinstance(o, Circle):
				BresenhamCircle().rasterize(o)
			elif isinstance(o, Polygon):
				for ln in o.lines:
					if self.comboRender.currentText() == 'DDA':
						DDA.rasterizeLine(ln)
					else:
						BresenhamLines.rasterizeLine(ln)

	def collect_root_objects(self):
		"""Retorna apenas os objetos da raiz (fora de views)."""
		return [it['obj'] for it in self.objects]

	def redraw_all(self):
		"""Limpa e redesenha a cena conforme a view ativa (se houver)."""
		self.canvas.clear()
		self.canvas.set_clip_rect(self.active_view['rect'] if self.active_view else None)
		if self.active_view:
			self.draw_objects(self.active_view['objects'])
		else:
			self.draw_objects(self.collect_root_objects())

	def on_tree_selection(self):
		"""Atualiza seleção (raiz/view/objeto) a partir da árvore."""
		item = self.treeObjects.currentItem()
		if not item:
			return
		data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
		if not data:
			return
		if data['type'] == 'root':
			self.active_view = None
			self.selected_index = None
			self.selected_view_obj_index = None
		elif data['type'] == 'view':
			self.active_view = data['ref']
			self.selected_index = None
			self.selected_view_obj_index = None
		elif data['type'] == 'view-object':
			# seleciona um objeto dentro da view ativa
			self.active_view = data['view']
			self.selected_view_obj_index = data['index']
			self.selected_index = None
		elif data['type'] == 'object':
			self.selected_index = data['index']
			self.active_view = None
			self.selected_view_obj_index = None
		self.redraw_all()

	def get_selected_rect_buf(self):
		"""Retorna o retângulo (buffer) do item atualmente selecionado."""
		if self.selected_index is not None:
			return self.compute_bounding_rect(self.objects[self.selected_index])
		if self.active_view and self.selected_view_obj_index is not None:
			obj = self.active_view['objects'][self.selected_view_obj_index]
			return self.compute_bounding_rect({'obj': obj})
		return None

	def compute_bounding_rect(self, item):
		"""Calcula o QRect (coords de buffer) que envolve o item dado."""
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
		"""Alias de compute_bounding_rect (coords já em buffer)."""
		return self.compute_bounding_rect(item)

	def on_canvas_left_click(self, x, y):
		"""Trata cliques com botão esquerdo no canvas (desenho e seleção)."""
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
			# adiciona ponto; espera retorno próximo à origem para fechar
			self.temp_points.append((bx,by))
			if len(self.temp_points) > 1 and (abs(bx - self.temp_points[0][0]) < 3 and abs(by - self.temp_points[0][1]) < 3 and len(self.temp_points) > 2):
				# fecha o polígono
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
		elif self.current_tool == 'clip':
			# inicia o retângulo de seleção em coords de widget
			self.canvas.drag_select_start = QtCore.QPoint(x, y)
			self.canvas.drag_select_end = QtCore.QPoint(x, y)
			self.canvas.update()
		elif self.current_tool == 'pivot':
			# define o pivô para o pixel clicado
			self.canvas.set_pivot(bx, by)

	def on_canvas_right_click(self, x, y):
		"""Menu de contexto para aplicar transformações no item clicado."""
		bx, by = self.canvas.widget_to_buffer(x, y)
		# alvo: preferir a seleção atual; caso contrário, um hit-test simples
		target_kind = None
		target_index = None
		item_wrapper = None
		# 1) objeto de view selecionado
		if self.active_view and self.selected_view_obj_index is not None:
			obj = self.active_view['objects'][self.selected_view_obj_index]
			item_wrapper = {'obj': obj}
			rect = self.compute_bounding_rect(item_wrapper)
			if rect and rect.contains(bx, by):
				target_kind = 'view'
				target_index = self.selected_view_obj_index
		# 2) objeto da raiz selecionado
		elif self.selected_index is not None:
			item_wrapper = self.objects[self.selected_index]
			rect = self.compute_bounding_rect(item_wrapper)
			if rect and rect.contains(bx, by):
				target_kind = 'root'
				target_index = self.selected_index
		# 3) hit-test nos objetos da view ativa
		elif self.active_view:
			for i, vo in enumerate(self.active_view['objects']):
				wrap = {'obj': vo}
				rect = self.compute_bounding_rect(wrap)
				if rect and rect.contains(bx, by):
					self.selected_view_obj_index = i
					item_wrapper = wrap
					target_kind = 'view'
					target_index = i
					break
		# 4) hit-test nos objetos da raiz
		else:
			for i, it in enumerate(self.objects):
				rect = self.compute_bounding_rect(it)
				if rect and rect.contains(bx, by):
					self.selected_index = i
					item_wrapper = it
					target_kind = 'root'
					target_index = i
					break

		if target_kind is None or item_wrapper is None:
			return

		# Build and show the context menu
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
			# For view objects, pass idx=None to route correctly
			self.apply_translation(target_index if target_kind == 'root' else None, dx, dy)
		elif action == t_rotate:
			ang, ok = QtWidgets.QInputDialog.getDouble(self, 'Rotacionar', 'Ângulo (graus):', 0.0)
			if not ok: return
			self.apply_rotation(target_index if target_kind == 'root' else None, ang)
		elif action == t_scale:
			sx, ok = QtWidgets.QInputDialog.getDouble(self, 'Escalar', 'scaleX:', 1.0)
			if not ok: return
			sy, ok = QtWidgets.QInputDialog.getDouble(self, 'Escalar', 'scaleY:', 1.0)
			if not ok: return
			self.apply_scale(target_index if target_kind == 'root' else None, sx, sy)
		elif action == t_reflect:
			items = ['x','y','yx']
			txt, ok = QtWidgets.QInputDialog.getItem(self, 'Refletir', 'axis:', items, 0, False)
			if not ok: return
			self.apply_reflect(target_index if target_kind == 'root' else None, txt)

	def on_canvas_move(self, x, y):
		"""Atualiza o retângulo de seleção durante o arrasto do recorte."""
		if QtWidgets.QApplication.mouseButtons() & QtCore.Qt.MouseButton.LeftButton:
			if self.current_tool == 'clip' and self.canvas.drag_select_start is not None:
				self.canvas.drag_select_end = QtCore.QPoint(x, y)
				self.canvas.update()

	def on_canvas_release(self):
		"""Finaliza a seleção do recorte e cria uma view com os objetos recortados."""
		if self.current_tool == 'clip' and self.canvas.drag_select_start and self.canvas.drag_select_end:
			p1 = self.canvas.drag_select_start
			p2 = self.canvas.drag_select_end
			bx1, by1 = self.canvas.widget_to_buffer(p1.x(), p1.y())
			bx2, by2 = self.canvas.widget_to_buffer(p2.x(), p2.y())
			x1, x2 = sorted([bx1, bx2])
			y1, y2 = sorted([by1, by2])
			rect = QtCore.QRect(x1, y1, max(1, x2-x1+1), max(1, y2-y1+1))
			self.create_view(rect)
			self.canvas.drag_select_start = None
			self.canvas.drag_select_end = None
	def create_view(self, rect_buf: QtCore.QRect):
		"""Cria uma view contendo objetos recortados pelo algoritmo escolhido."""
		algo = self.comboClipping.currentText()
		view_objects = []
		for it in self.objects:
			obj = it['obj']
			clipper = ClippingCS(rect_buf.left(), rect_buf.right(), rect_buf.top(), rect_buf.bottom()) if algo == 'Cohen-Sutherland' else ClippingLB(rect_buf.left(), rect_buf.right(), rect_buf.top(), rect_buf.bottom())
			if isinstance(obj, Point):
				if rect_buf.contains(int(obj.x), int(obj.y)):
					view_objects.append(Point(obj.x, obj.y, obj.color))
			elif isinstance(obj, Line):
				cl = clipper.clip_line(obj)
				if cl is not None:
					view_objects.append(Line(cl.pointA, cl.pointB, obj.color))
			elif isinstance(obj, Circle):
				# inclusão simples se a bbox intersecta
				xs = [obj.center.x - obj.radius, obj.center.x + obj.radius]
				ys = [obj.center.y - obj.radius, obj.center.y + obj.radius]
				cb = QtCore.QRect(min(xs), min(ys), abs(xs[1]-xs[0])+1, abs(ys[1]-ys[0])+1)
				if rect_buf.intersects(cb):
					view_objects.append(Circle(Point(obj.center.x, obj.center.y), obj.radius, obj.color))
			elif isinstance(obj, Polygon):
				clipped_lines = []
				for ln in obj.lines:
					cl = clipper.clip_line(ln)
					if cl is not None:
						clipped_lines.append(Line(cl.pointA, cl.pointB, ln.color))
				if clipped_lines:
					view_objects.append(Polygon(clipped_lines))
		# register view in tree
		name = f"Viewport {len(self.views)+1}"
		view = {'name': name, 'rect': rect_buf, 'objects': view_objects}
		self.views.append(view)
		node = QtWidgets.QTreeWidgetItem([name])
		node.setData(0, QtCore.Qt.ItemDataRole.UserRole, {'type': 'view', 'ref': view})
		self.tree_root.addChild(node)
		# add children for view objects
		for i, vo in enumerate(view_objects):
			label = vo.__class__.__name__ + f" #{i}"
			child = QtWidgets.QTreeWidgetItem([label])
			child.setData(0, QtCore.Qt.ItemDataRole.UserRole, {'type': 'view-object', 'view': view, 'index': i})
			node.addChild(child)
		self.treeObjects.expandItem(node)
		# activate view
		self.active_view = view
		self.treeObjects.setCurrentItem(node)
		self.redraw_all()

	def apply_translation(self, idx, dx, dy):
		"""Aplica translação ao objeto alvo (na view ativa ou na raiz)."""
		if self.active_view and self.selected_view_obj_index is not None and idx is None:
			obj = self.active_view['objects'][self.selected_view_obj_index]
			target = {'obj': obj}
		else:
			target = self.objects[idx]
		item = target['obj']
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

	def apply_rotation(self, idx, angle_deg):
		"""Aplica rotação (em graus) ao redor do pivô ou centro da bbox."""
		if self.active_view and self.selected_view_obj_index is not None and idx is None:
			target = {'obj': self.active_view['objects'][self.selected_view_obj_index]}
		else:
			target = self.objects[idx]
		item = target
		rect = self.compute_bounding_rect(item)
		item = item['obj']
		
		if not rect: return
		# usa pivô se definido; senão, centro da bbox
		if self.canvas.pivot_point is not None:
			cx, cy = self.canvas.pivot_point
		else:
			cx = rect.x() + rect.width()/2
			cy = rect.y() + rect.height()/2

		# rotaciona ao redor do ponto (cx, cy)
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

	def apply_scale(self, idx, sx, sy):
		"""Aplica escala em torno do pivô ou centro da bbox (sx, sy)."""
		if self.active_view and self.selected_view_obj_index is not None and idx is None:
			target = {'obj': self.active_view['objects'][self.selected_view_obj_index]}
		else:
			target = self.objects[idx]
		item = target
		rect = self.compute_bounding_rect(item)
		if not rect: return
		# usa pivô se definido; senão, centro da bbox
		if self.canvas.pivot_point is not None:
			cx, cy = self.canvas.pivot_point
		else:
			cx = rect.x() + rect.width()/2
			cy = rect.y() + rect.height()/2

		# escala ao redor do ponto (cx, cy)
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
		"""Reflete em torno do pivô ou centro da bbox (eixos: 'x', 'y' ou 'yx')."""
		if self.active_view and self.selected_view_obj_index is not None and idx is None:
			target = {'obj': self.active_view['objects'][self.selected_view_obj_index]}
		else:
			target = self.objects[idx]
		item = target
		rect = self.compute_bounding_rect(item)
		if not rect: return
		# usa pivô se definido; senão, centro da bbox
		if self.canvas.pivot_point is not None:
			cx, cy = self.canvas.pivot_point
		else:
			cx = rect.x() + rect.width()/2
			cy = rect.y() + rect.height()/2
		item = item['obj']

		# reflexão ao redor do ponto (cx, cy)
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
				ln.pointA.x, ln.pointA.y = rft(ln.pointA.x, ln.pointA.y, axis=axis)
				ln.pointB.x, ln.pointB.y = rft(ln.pointB.x, ln.pointB.y, axis=axis)
		self.redraw_all()

def main():
	"""Ponto de entrada da aplicação."""
	app = QtWidgets.QApplication(sys.argv)
	w = MainWindow()
	w.show()
	sys.exit(app.exec())

if __name__ == '__main__':
	main()
