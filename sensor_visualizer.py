#!/usr/bin/env python3
"""
Sensor Visualizer - Real-time visualization for 5 finger sensors
Shows force and position data on a hand diagram
"""
import sys
import os
import math
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import serial

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
HAND_IMAGE_PATH = os.path.join(ASSETS_DIR, 'Hand.png')

# Data class to store sensor measurements
@dataclass
class SensorSample:
	x_mm: float  # X position in millimeters
	y_mm: float  # Y position in millimeters
	force_g: float  # Force/pressure in grams
	z_mm: float = 0.0  # Z position (optional)

# Reads data from serial port in a separate thread
class SerialWorker(QtCore.QObject):
	# Signals for when we get data, status updates, or finish
	sampleReceived = QtCore.pyqtSignal(int, object)  # sensor index and data
	statusChanged = QtCore.pyqtSignal(str)
	finished = QtCore.pyqtSignal()

	def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200, parent=None):
		super().__init__(parent)
		self._port_name = port
		self._baudrate = baudrate
		self._running = False
		self._serial: Optional[serial.Serial] = None
		self._last_update = 0
		self._update_interval = 0.03  # Update ~33 times per second
		self._last_by_sensor: Dict[int, SensorSample] = {}

	@QtCore.pyqtSlot()
	def start(self):
		self._running = True
		try:
			self._serial = serial.Serial(self._port_name, self._baudrate, timeout=0.05)
			self._serial.reset_input_buffer()
			self.statusChanged.emit(f'Connected to {self._port_name}')
		except Exception as e:
			self.statusChanged.emit(f'ERROR: Could not open {self._port_name}: {e}')
			self._running = False
			self.finished.emit()
			return
		# Keep reading data from serial port
		buffer = ''
		while self._running:
			try:
				# Read data from serial port
				chunk = self._serial.read(512).decode('utf-8', errors='ignore')
				if chunk:
					buffer += chunk
					# Split into lines
					lines = buffer.split('\n')
					buffer = lines[-1]  # Keep incomplete line in buffer
					# Process each complete line
					for raw in lines[:-1]:
						text = raw.strip()
						if not text:
							continue
						updates = self._parse_line_multi(text)
						if not updates:
							continue
						# Send updates at limited rate (so UI doesn't lag)
						now = time.time()
						if now - self._last_update >= self._update_interval:
							for idx, sample in updates:
								self._last_by_sensor[idx] = sample
								self.sampleReceived.emit(idx, sample)
							self._last_update = now
			except Exception as e:
				self.statusChanged.emit(f'Serial read error: {e}')
				break
		self._cleanup()
		self.finished.emit()

	@QtCore.pyqtSlot()
	def stop(self):
		self._running = False
		self._cleanup()

	def _cleanup(self):
		if self._serial is not None:
			try:
				self._serial.close()
			except Exception:
				pass
		self._serial = None

	# Parse incoming sensor data (supports multiple formats)
	def _parse_line_multi(self, text: str) -> List[Tuple[int, SensorSample]]:
		"""
		Parse sensor data from different formats:
		- "Sensor 1: x,y,z; Sensor 2: x,y,z; ..." (labeled with semicolons)
		- "x1,y1,z1,x2,y2,z2,..." (flat CSV with 15 values for 5 sensors)
		- "x1,y1,z1,l1,x2,y2,z2,l2,..." (flat CSV with 20 values including load)
		"""
		updates: List[Tuple[int, SensorSample]] = []
		line = text.strip()
		if not line:
			return updates
		low = line.lower()
		
		# Skip header lines like "x,y,z,load"
		if 'x,y,z' in low or low.startswith('x,'):
			return updates

		# Check for labeled format: "Sensor N: x,y,z"
		if 'sensor' in low:
			segments = re.split(r'[;|]', line)
			for seg in segments:
				seg = seg.strip()
				if not seg:
					continue
				# Parse "Sensor N: x,y,z"
				m = re.match(r'^\s*sensor\s*(\d+)\s*:\s*(.*)$', seg, re.IGNORECASE)
				if not m:
					continue
				idx = max(1, min(5, int(m.group(1)))) - 1  # Clamp to 0-4
				payload = m.group(2).strip()
				if payload.endswith(','):
					payload = payload[:-1]
				parts = [p.strip() for p in payload.split(',') if p.strip()]
				if len(parts) >= 3:
					try:
						x = float(parts[0]); y = float(parts[1]); z = float(parts[2])
						force = float(parts[3]) if len(parts) >= 4 else math.sqrt(x*x + y*y + z*z)
						updates.append((idx, SensorSample(x, y, force, z)))
					except Exception:
						pass
			return updates

		# Check for flat CSV format (all 5 sensors at once)
		parts = [p.strip() for p in line.split(',') if p.strip()]
		if len(parts) in (15, 20):
			# 15 values = 5 sensors * (x,y,z)  |  20 values = 5 sensors * (x,y,z,load)
			cursor = 0
			for sensor_idx in range(5):
				try:
					x = float(parts[cursor]); y = float(parts[cursor+1]); z = float(parts[cursor+2])
					cursor += 3
					if len(parts) == 20:
						force = float(parts[cursor]); cursor += 1
					else:
						force = math.sqrt(x*x + y*y + z*z)
					updates.append((sensor_idx, SensorSample(x, y, force, z)))
				except Exception:
					break
			return updates

		# Try to parse as single sensor data
		if len(parts) >= 3:
			try:
				x = float(parts[0]); y = float(parts[1]); z = float(parts[2])
				force = float(parts[3]) if len(parts) >= 4 else math.sqrt(x*x + y*y + z*z)
				updates.append((0, SensorSample(x, y, force, z)))
			except Exception:
				return []
		return updates

# Helper functions for graphics
def clamp(value: float, min_value: float, max_value: float) -> float:
	"""Clamp a value between min and max"""
	return max(min_value, min(max_value, value))

def lerp(a: float, b: float, t: float) -> float:
	"""Linear interpolation between a and b"""
	return a + (b - a) * t

def color_for_force(force_g: float) -> Tuple[int, int, int]:
	"""Convert force value to RGB color (green -> yellow -> red)"""
	# Scale force from 0-500 to 0-1
	t = clamp(force_g / 500.0, 0.0, 1.0)
	if t < 0.5:
		# Green to yellow
		k = t / 0.5
		r = int(lerp(0, 255, k))
		g = int(lerp(180, 200, k))
		b = 0
	else:
		# Yellow to red
		k = (t - 0.5) / 0.5
		r = int(lerp(255, 230, k))
		g = int(lerp(200, 0, k))
		b = 0
	return r, g, b

# Widget that displays the hand image with sensor overlays
class HandOverlayWidget(QtWidgets.QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setMinimumSize(520, 680)
		self._pixmap = QtGui.QPixmap(HAND_IMAGE_PATH)
		# Normalized positions for each fingertip (0.0 to 1.0 relative to image)
		self._finger_positions_norm: List[QtCore.QPointF] = [
			QtCore.QPointF(0.30, 0.25),  # thumb
			QtCore.QPointF(0.48, 0.12),  # index finger
			QtCore.QPointF(0.63, 0.10),  # middle finger
			QtCore.QPointF(0.76, 0.13),  # ring finger
			QtCore.QPointF(0.86, 0.18),  # pinky
		]
		self._finger_states: List[SensorSample] = [SensorSample(0, 0, 0, 0) for _ in range(5)]
		self._bg = QtGui.QColor(255, 255, 255)

	def setFingerSample(self, finger_index: int, sample: SensorSample):
		if 0 <= finger_index < 5:
			self._finger_states[finger_index] = sample
			self.update()

	def paintEvent(self, event: QtGui.QPaintEvent):
		p = QtGui.QPainter(self)
		p.setRenderHint(QtGui.QPainter.Antialiasing, True)
		p.fillRect(self.rect(), self._bg)

		# Draw the hand image in the center
		if not self._pixmap.isNull():
			scaled = self._pixmap.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
			x = (self.width() - scaled.width()) // 2
			y = (self.height() - scaled.height()) // 2
			p.drawPixmap(x, y, scaled)
			image_rect = QtCore.QRect(x, y, scaled.width(), scaled.height())
		else:
			image_rect = self.rect()

		# Draw overlays for each finger
		for i, state in enumerate(self._finger_states):
			# Calculate where to draw based on normalized position
			pos_norm = self._finger_positions_norm[i]
			cx = image_rect.x() + pos_norm.x() * image_rect.width()
			cy = image_rect.y() + pos_norm.y() * image_rect.height()

			# Choose color based on force (green to red)
			r, g, b = color_for_force(state.force_g)
			# Circle size changes with force
			t = clamp(state.force_g / 500.0, 0.0, 1.0)
			radius = lerp(8.0, 30.0, t)

			# Draw glowing circle
			grad = QtGui.QRadialGradient(QtCore.QPointF(cx, cy), radius)
			grad.setColorAt(0.0, QtGui.QColor(r, g, b, 220))
			grad.setColorAt(0.8, QtGui.QColor(r, g, b, 60))
			grad.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
			p.setBrush(QtGui.QBrush(grad))
			p.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1.0))
			p.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

			# Draw arrow showing direction of force
			vec_scale = 1.5
			vx = clamp(state.x_mm, -50.0, 50.0) * vec_scale
			vy = clamp(-state.y_mm, -50.0, 50.0) * vec_scale
			pen = QtGui.QPen(QtGui.QColor(r, g, b), 2.6)
			p.setPen(pen)
			p.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(cx + vx, cy + vy))
			# Draw arrowhead
			if abs(vx) + abs(vy) > 1.0:
				ang = math.atan2(vy, vx)
				h = 9.0
				left = QtCore.QPointF(cx + vx - h * math.cos(ang - math.pi / 6), cy + vy - h * math.sin(ang - math.pi / 6))
				right = QtCore.QPointF(cx + vx - h * math.cos(ang + math.pi / 6), cy + vy - h * math.sin(ang + math.pi / 6))
				p.drawLine(QtCore.QPointF(cx + vx, cy + vy), left)
				p.drawLine(QtCore.QPointF(cx + vx, cy + vy), right)

# Panel that shows force as a circle and position as an arrow
class CircleArrowPanel(QtWidgets.QFrame):
	def __init__(self, title: str, parent=None):
		super().__init__(parent)
		self.setFrameShape(QtWidgets.QFrame.StyledPanel)
		self.setStyleSheet('QFrame { background-color: #ffffff; border: 1px solid #dcdcdc; border-radius: 8px; }')
		self._title = QtWidgets.QLabel(title)
		self._title.setStyleSheet('QLabel { color: #111111; font-weight: 600; font-size: 14px; }')
		self._canvas = QtWidgets.QLabel()
		self._canvas.setMinimumSize(240, 200)
		self._canvas.installEventFilter(self)
		self._pixmap = QtGui.QPixmap(480, 360)
		self._pixmap.fill(QtGui.QColor(255, 255, 255))
		self._state = SensorSample(0, 0, 0, 0)
		self._bg = QtGui.QColor(255, 255, 255)
		layout = QtWidgets.QVBoxLayout()
		layout.setContentsMargins(12, 10, 12, 12)
		layout.setSpacing(8)
		layout.addWidget(self._title)
		layout.addWidget(self._canvas)
		self.setLayout(layout)
		self._redraw()

	def setSample(self, sample: SensorSample):
		self._state = sample
		self._redraw()

	def eventFilter(self, obj, event):
		if obj is self._canvas and event.type() == QtCore.QEvent.Resize:
			self._pixmap = QtGui.QPixmap(self._canvas.width(), self._canvas.height())
			self._redraw()
		return super().eventFilter(obj, event)

	def _redraw(self):
		if self._pixmap.isNull():
			return
		self._pixmap.fill(self._bg)
		p = QtGui.QPainter(self._pixmap)
		p.setRenderHint(QtGui.QPainter.Antialiasing, True)

		w = self._pixmap.width()
		h = self._pixmap.height()
		cx, cy = w / 2.0, h / 2.0

		# Axes with labels
		p.setPen(QtGui.QPen(QtGui.QColor(160, 160, 160), 1))
		p.drawLine(QtCore.QPointF(10, cy), QtCore.QPointF(w - 10, cy))
		p.drawLine(QtCore.QPointF(cx, 10), QtCore.QPointF(cx, h - 10))
		
		# Axis labels
		font = QtGui.QFont(); font.setPointSize(10)
		p.setFont(font)
		p.setPen(QtGui.QPen(QtGui.QColor(80, 80, 80)))
		p.drawText(QtCore.QRectF(w-30, cy-10, 20, 20), QtCore.Qt.AlignCenter, "X")
		p.drawText(QtCore.QRectF(cx-10, 5, 20, 20), QtCore.Qt.AlignCenter, "Y")

		# Circle by force
		r, g, b = color_for_force(self._state.force_g)
		t = clamp(self._state.force_g / 500.0, 0.0, 1.0)
		radius = lerp(12.0, 44.0, t)
		grad = QtGui.QRadialGradient(QtCore.QPointF(cx, cy), radius)
		grad.setColorAt(0.0, QtGui.QColor(r, g, b, 220))
		grad.setColorAt(0.9, QtGui.QColor(r, g, b, 40))
		grad.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
		p.setBrush(QtGui.QBrush(grad))
		p.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1.2))
		p.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

		# Arrow for x-y - reduced sensitivity
		vec_scale = 2.0
		vx = clamp(self._state.x_mm, -50.0, 50.0) * vec_scale
		vy = clamp(-self._state.y_mm, -50.0, 50.0) * vec_scale
		p.setPen(QtGui.QPen(QtGui.QColor(r, g, b), 2.6))
		p.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(cx + vx, cy + vy))
		if abs(vx) + abs(vy) > 1.0:
			ang = math.atan2(vy, vx)
			h = 9.0
			left = QtCore.QPointF(cx + vx - h * math.cos(ang - math.pi / 6), cy + vy - h * math.sin(ang - math.pi / 6))
			right = QtCore.QPointF(cx + vx - h * math.cos(ang + math.pi / 6), cy + vy - h * math.sin(ang + math.pi / 6))
			p.drawLine(QtCore.QPointF(cx + vx, cy + vy), left)
			p.drawLine(QtCore.QPointF(cx + vx, cy + vy), right)

		p.end()
		self._canvas.setPixmap(self._pixmap)

# Tab that shows real-time graphs for all 5 sensors
class TimeSeriesTab(QtWidgets.QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._plots: List[pg.PlotWidget] = []
		layout = QtWidgets.QGridLayout()
		layout.setContentsMargins(10, 10, 10, 10)
		layout.setSpacing(12)
		for i in range(5):
			pw = pg.PlotWidget(background='w')
			pw.setMinimumHeight(200)
			pw.showGrid(x=True, y=True, alpha=0.2)
			pw.addLegend()
			pw.setTitle(f'Sensor {i+1} – X, Y, Z Displacement', color='#000000', size='12pt')
			pw.getAxis('bottom').setPen(pg.mkPen(color=(0, 0, 0), width=1))
			pw.getAxis('left').setPen(pg.mkPen(color=(0, 0, 0), width=1))
			pw.getAxis('bottom').setTextPen(pg.mkColor(0, 0, 0))
			pw.getAxis('left').setTextPen(pg.mkColor(0, 0, 0))
			pw.setLabel('left', 'Displacement (mm)', color='#000000', size='10pt')
			pw.setLabel('bottom', 'Time (samples)', color='#000000', size='10pt')
			curve_x = pw.plot(pen=pg.mkPen('#1f77b4', width=2.2), name='X-axis')
			curve_y = pw.plot(pen=pg.mkPen('#ff7f0e', width=2.2), name='Y-axis')
			curve_z = pw.plot(pen=pg.mkPen('#2ca02c', width=2.2), name='Z-axis')
			pw.setYRange(-100, 100, padding=0.05)
			pw.setXRange(0, 800, padding=0.01)
			self._plots.append((pw, curve_x, curve_y, curve_z))
			layout.addWidget(pw, i // 2, i % 2)
		self.setLayout(layout)

		self._window = 800
		self._buffers = [
			{
				'x': np.zeros(self._window),
				'y': np.zeros(self._window),
				'z': np.zeros(self._window),
			}
			for _ in range(5)
		]
		self._index = 0
		self._x_axis = np.arange(self._window)

	def addSample(self, finger_index: int, sample: SensorSample):
		"""Add new sensor data to the graph"""
		if not (0 <= finger_index < 5):
			return
		buf = self._buffers[finger_index]
		idx = self._index % self._window
		# Store x, y, z values
		buf['x'][idx] = sample.x_mm
		buf['y'][idx] = sample.y_mm
		buf['z'][idx] = sample.z_mm
		self._index += 1
		# Shift buffer so newest data is on the right (scrolls left-to-right)
		shift = (idx + 1) % self._window
		plot_x = np.roll(buf['x'], -shift)
		plot_y = np.roll(buf['y'], -shift)
		plot_z = np.roll(buf['z'], -shift)
		# Update the plot
		pw, cx, cy, cz = self._plots[finger_index]
		cx.setData(self._x_axis, plot_x)
		cy.setData(self._x_axis, plot_y)
		cz.setData(self._x_axis, plot_z)

# Main window that puts everything together
class MainWindow(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle('Sensor Visualization Suite')
		self.resize(1400, 900)
		self.setStyleSheet('QMainWindow { background-color: #ffffff; }')

		# Start serial reading in separate thread (so UI stays smooth)
		self._thread = QtCore.QThread(self)
		self._worker = SerialWorker(port='/dev/ttyACM0')
		self._worker.moveToThread(self._thread)
		self._thread.started.connect(self._worker.start)
		self._worker.finished.connect(self._thread.quit)
		self._worker.finished.connect(self._worker.deleteLater)
		self._thread.finished.connect(self._thread.deleteLater)
		self._worker.sampleReceived.connect(self._onSample)
		self._worker.statusChanged.connect(self._onStatus)

		# Create tabs for different views
		tabs = QtWidgets.QTabWidget()
		tabs.setStyleSheet('QTabBar::tab { background: #f3f3f3; color: #111; padding: 8px 14px; } QTabBar::tab:selected { background: #e9e9e9; } QTabWidget::pane { border: 1px solid #dcdcdc; }')
		self.setCentralWidget(tabs)

		# First tab: Hand diagram + sensor panels
		page1 = QtWidgets.QWidget()
		p1_layout = QtWidgets.QHBoxLayout()
		p1_layout.setContentsMargins(10, 10, 10, 10)
		p1_layout.setSpacing(12)

		self._hand = HandOverlayWidget()
		p1_layout.addWidget(self._hand, 2)

		right_col = QtWidgets.QWidget()
		right_layout = QtWidgets.QGridLayout()
		right_layout.setContentsMargins(0, 0, 0, 0)
		right_layout.setSpacing(10)
		self._panels: List[CircleArrowPanel] = []
		for i, name in enumerate(['Thumb (Live)', 'Index (Live)', 'Middle (Live)', 'Ring (Live)', 'Pinky (Live)']):
			panel = CircleArrowPanel(f'Sensor {i+1} – {name}')
			self._panels.append(panel)
			right_layout.addWidget(panel, i // 2, i % 2)
		right_col.setLayout(right_layout)
		p1_layout.addWidget(right_col, 3)
		page1.setLayout(p1_layout)
		tabs.addTab(page1, 'Hand & Panels')

		# Second tab: Real-time graphs
		self._timeSeries = TimeSeriesTab()
		tabs.addTab(self._timeSeries, 'Time Series')

		# Status bar at bottom
		self._status = QtWidgets.QLabel('Ready')
		self.statusBar().addPermanentWidget(self._status)

		# Start reading data
		self._thread.start()

	def closeEvent(self, event):
		try:
			if hasattr(self, '_worker') and self._worker is not None:
				self._worker.stop()
		except Exception:
			pass
		try:
			if hasattr(self, '_thread') and self._thread is not None and self._thread.isRunning():
				self._thread.quit()
				self._thread.wait(1000)
		except Exception:
			pass
		super().closeEvent(event)

	def _onStatus(self, text: str):
		self._status.setText(text)

	@QtCore.pyqtSlot(int, object)
	def _onSample(self, sensor_index: int, sample: SensorSample):
		"""Update all displays with new sensor data"""
		self._hand.setFingerSample(sensor_index, sample)
		self._panels[sensor_index].setSample(sample)
		self._timeSeries.addSample(sensor_index, sample)

def main():
	app = QtWidgets.QApplication(sys.argv)
	mw = MainWindow()
	mw.show()
	return app.exec_()

if __name__ == '__main__':
	sys.exit(main())
