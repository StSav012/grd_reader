# -*- coding: utf-8 -*-


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.stderr.write("\033[1musage:\033[0m %s file1 ..." % sys.argv[0])

    else:

        def run() -> None:
            import sys
            from pathlib import Path
            from qtpy.QtWidgets import QApplication
            from grd_reader import plot

            app: QApplication = QApplication(sys.argv)
            plot: plot.Plot = plot.Plot()
            plot.plot(Path(sys.argv[1]))
            plot.show()
            app.exec()

        run()
