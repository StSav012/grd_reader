# coding: utf-8
import math
from pathlib import Path
from typing import Optional, cast

import pyqtgraph as pg  # type: ignore
from PySide6.QtCore import QByteArray, QPoint, QPointF, QRect, QRectF, QSettings
from PySide6.QtGui import QCloseEvent, QScreen
from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget
from pyqtgraph import functions as fn  # type: ignore

from grd_reader import CurveData, GraphData, read_grd
from valuelabel import ValueLabel


class Cursor:
    def __init__(self, parent: pg.PlotItem) -> None:
        self._crosshair_v_line: pg.InfiniteLine = pg.InfiniteLine(angle=90, movable=False)
        self._crosshair_h_line: pg.InfiniteLine = pg.InfiniteLine(angle=0, movable=False)
        self._cursor_balloon: pg.TextItem = pg.TextItem()
        self._parent: pg.PlotItem = parent
        self._parent.addItem(self._crosshair_v_line, ignoreBounds=True)
        self._parent.addItem(self._crosshair_h_line, ignoreBounds=True)
        self._parent.addItem(self._cursor_balloon, ignoreBounds=True)

        self.format_string: str = '{scaled_value:.{decimals}f}{unit_gap}{si_prefix}{unit}'
        self.si_prefix: bool = True
        self.decimals: int = 3

    def show(self, do_show: bool = True) -> None:
        self._crosshair_h_line.setVisible(do_show)
        self._crosshair_v_line.setVisible(do_show)
        self._cursor_balloon.setVisible(do_show)

    def hide(self, do_hide: bool = True) -> None:
        self.show(not do_hide)

    def move(self, point: QPointF) -> None:
        axes: dict[str, pg.AxisItem] = self._parent.axes
        self._crosshair_v_line.setPos(point.x())
        self._crosshair_h_line.setPos(point.y())
        self._cursor_balloon.setHtml(self.format(point.x(), axes['bottom']['item'].labelUnits) + '<br>'
                                     + self.format(point.y(), axes['left']['item'].labelUnits))
        balloon_border: QRectF = self._cursor_balloon.boundingRect()
        sx: float
        sy: float
        sx, sy = self._parent.vb.viewPixelSize()
        balloon_width: float = balloon_border.width() * sx
        balloon_height: float = balloon_border.height() * sy
        anchor_x: float = self._cursor_balloon.anchor.x()
        anchor_y: float = self._cursor_balloon.anchor.y()
        if point.x() - axes['bottom']['item'].range[0] < balloon_width:
            anchor_x = 0.0
        if axes['bottom']['item'].range[1] - point.x() < balloon_width:
            anchor_x = 1.0
        if point.y() - axes['left']['item'].range[0] < balloon_height:
            anchor_y = 1.0
        if axes['left']['item'].range[1] - point.y() < balloon_height:
            anchor_y = 0.0
        if anchor_x != self._cursor_balloon.anchor.x() or anchor_y != self._cursor_balloon.anchor.y():
            self._cursor_balloon.anchor = pg.Point((anchor_x, anchor_y))
        self._cursor_balloon.setPos(point)

    def format(self, val: float, unit: str) -> str:
        if math.isnan(val):
            return ''

        # format_string the string
        parts = {'value': val, 'unit': unit, 'decimals': self.decimals}
        if self.si_prefix and unit:
            # SI prefix was requested, so scale the value accordingly
            (s, p) = fn.siScale(val)
            parts.update({'si_prefix': p, 'scaled_value': s * val})
        else:
            # no SI prefix /unit requested; scale is 1
            exp: int = int(math.floor(math.log10(abs(val)))) if val != 0.0 else 0
            man: float = val * math.pow(0.1, exp)
            parts.update({'si_prefix': '', 'scaled_value': val, 'exp': exp, 'mantissa': man})

        parts['unit_gap'] = ' ' if (parts['unit'] or parts['si_prefix']) else ''

        return self.format_string.format(**parts).replace('-', '−')


class Plot(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName('plot_window')

        self.settings: QSettings = QSettings('SavSoft', 'GRD Plotter', self)

        self.setWindowTitle(self.tr('Plot'))
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())

        self._plot: pg.PlotWidget = pg.PlotWidget(self, title='plot')
        self._canvas: pg.PlotItem = self._plot.plotItem
        self.setCentralWidget(self._plot)
        self._canvas.addLegend()

        self.status_bar: QStatusBar = QStatusBar(self)
        self.status_bar.setObjectName('status_bar')
        self._plot_cursor: Cursor = Cursor(self._canvas)
        self._cursor_x: ValueLabel = ValueLabel(self.status_bar, siPrefix=True)
        self._cursor_y: ValueLabel = ValueLabel(self.status_bar, siPrefix=True)
        self.status_bar.addWidget(self._cursor_x)
        self.status_bar.addWidget(self._cursor_y)
        self.setStatusBar(self.status_bar)

        self.load_settings()

        self._mouse_moved_signal_proxy: pg.SignalProxy = pg.SignalProxy(self._plot.scene().sigMouseMoved,
                                                                        rateLimit=10, slot=self.on_mouse_moved)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_settings()
        event.accept()

    def load_settings(self) -> None:
        # self.settings.beginGroup('location')
        # self._opened_file_name = cast(str, self.settings.value('open', str(Path.cwd()), str))
        # self._exported_file_name = cast(str, self.settings.value('export', str(Path.cwd()), str))
        # self.settings.endGroup()

        self.settings.beginGroup('window')
        # Fallback: Center the window
        desktop: QScreen = QApplication.primaryScreen()
        window_frame: QRect = self.frameGeometry()
        desktop_center: QPoint = desktop.availableGeometry().center()
        window_frame.moveCenter(desktop_center)
        self.move(window_frame.topLeft())

        self.restoreGeometry(cast(QByteArray, self.settings.value('geometry', QByteArray())))
        self.restoreState(cast(QByteArray, self.settings.value('state', QByteArray())))
        self.settings.endGroup()

    def save_settings(self) -> None:
        # self.settings.beginGroup('location')
        # self.settings.setValue('open', self._opened_file_name)
        # self.settings.setValue('export', self._exported_file_name)
        # self.settings.endGroup()

        self.settings.beginGroup('window')
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('state', self.saveState())
        self.settings.endGroup()
        self.settings.sync()

    def plot(self, filename: Path) -> None:
        grd_data: GraphData = read_grd(filename)
        if grd_data.sample_name:
            self._canvas.setTitle(f'{grd_data.sample_name}, {grd_data.date}')
        else:
            self._canvas.setTitle(grd_data.date)

        index: int
        curve: CurveData
        for index, curve in enumerate(grd_data.curves):
            self._canvas.plot(curve[0], curve[1], name=curve.key or None, pen=pg.mkColor(index))

        self._canvas.setLabel('bottom', grd_data.names[0], grd_data.units[0])
        self._canvas.setLabel('left', grd_data.names[1], grd_data.units[1])
        self._cursor_x.unit = grd_data.units[0]
        self._cursor_y.unit = grd_data.units[1]
        self.setWindowTitle(str(filename.absolute()))

    def on_mouse_moved(self, event: tuple[QPointF]) -> None:
        if not self._canvas.curves:
            return
        pos: QPointF = event[0]
        if self._plot.sceneBoundingRect().contains(pos):
            point: QPointF = self._canvas.vb.mapSceneToView(pos)
            if self._plot.visibleRange().contains(point):
                self.status_bar.clearMessage()
                self._plot_cursor.show()
                self._plot_cursor.move(point)
                self._cursor_x.setVisible(True)
                self._cursor_y.setVisible(True)
                self._cursor_x.setValue(point.x())
                self._cursor_y.setValue(point.y())
            else:
                self._plot_cursor.hide()
        else:
            self._plot_cursor.hide()


if __name__ == '__main__':
    def run() -> None:
        import sys

        app: QApplication = QApplication(sys.argv)
        plot: Plot = Plot()
        plot.plot(Path(sys.argv[1]))
        plot.show()
        app.exec()

    run()
