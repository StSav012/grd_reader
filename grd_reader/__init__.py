# -*- coding: utf-8 -*-
from pathlib import Path
from typing import TextIO

import numpy as np
from numpy.typing import NDArray

__all__ = ["CurveData", "GraphData", "read_grd"]


class CurveData:
    def __init__(self) -> None:
        self.curve_number: int = 0
        self.start_date: str = ""
        self.key: str = ""
        self.duration: float = 0.0
        self.points: int = 0
        self.data: NDArray[np.float64] = np.empty(0)

    def __repr__(self) -> str:
        from os import linesep

        return linesep.join(
            (
                f"curve number: {self.curve_number}",
                f"start_date:   {self.start_date}",
                f"key:          {self.key}",
                f"duration:     {self.duration:.3f} [s]",
                f"points:       {self.points}",
            )
        )

    def __bool__(self) -> bool:
        return bool(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, col: int) -> NDArray[np.float64]:
        return self.data[..., col]


class GraphData:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.units: list[str] = []
        self.curves: list[CurveData] = []
        self.sample_name: str = ""
        self.date: str = ""
        self.specific_info: str = ""
        self.user_info: str = ""
        self.comment: list[str] = []

    def __repr__(self) -> str:
        from os import linesep

        return linesep.join(
            (
                f"sample name:   {self.sample_name}",
                f"date:          {self.date}",
                f"specific info: {self.specific_info}",
                f"user info:     {self.user_info}",
                f"comment:       {linesep.join(self.comment)}",
                f"names:         {self.names}",
                f"units:         {self.units}",
                "",
                "curves:",
                *map(repr, self.curves),
            )
        )

    def __bool__(self) -> bool:
        return bool(self.curves)

    def __getitem__(self, item: tuple[int, str]) -> NDArray[np.float64]:
        curve_number: int
        channel: str
        curve_number, channel = item
        col: int = self.names.index(channel)
        index: int = -1
        for i, c in enumerate(self.curves):
            if c.curve_number == curve_number:
                index = i
                break
        if index == -1:
            raise IndexError
        return self.curves[index][col]

    @property
    def curve(self) -> CurveData:
        return self.curves[-1]

    def unit(self, channel: str) -> str:
        col: int = self.names.index(channel)
        return self.units[col]


def read_grd(fn: Path) -> GraphData:
    data: GraphData = GraphData()
    f_in: TextIO
    with fn.open("rt") as f_in:
        lines: list[str] = f_in.read().splitlines()
        first_lines: bool = True
        reading_comment: bool = False
        reading_axes_description: int = -1
        reading_data: bool = False
        line: str
        for line in lines:
            if line.startswith("#START"):
                first_lines = False
            elif first_lines:
                if line.startswith(" Sample name :"):
                    data.sample_name = line.split(":", maxsplit=1)[-1]
                elif line.startswith(" Date        :"):
                    data.date = line.split(":", maxsplit=1)[-1]
                elif line.startswith(" Specific inf:"):
                    data.specific_info = line.split(":", maxsplit=1)[-1]
                elif line.startswith(" User info   :"):
                    data.user_info = line.split(":", maxsplit=1)[-1]
            if line.startswith("#START comment"):
                reading_comment = True
                continue
            elif reading_comment:
                if line.startswith("#END comment"):
                    reading_comment = False
                    if data.comment == [" "]:
                        data.comment.clear()
                else:
                    data.comment.append(line.strip())
                continue
            if line.startswith("#START axis description"):
                reading_axes_description = 0
                continue
            if reading_axes_description != -1:
                if line.startswith("#END axis description"):
                    reading_axes_description = -1
                    continue
                if reading_axes_description > 0:
                    data.names.append(
                        line.split(maxsplit=10)[-1].strip().replace(" ", "_")
                    )
                    data.units.append(
                        line.split(maxsplit=10)[-2].strip()
                        if len(line.split()) > 10
                        else ""
                    )
                reading_axes_description += 1
                continue
            if line.startswith("#START Curve description"):
                data.curves.append(CurveData())
                data.curve.curve_number = int(line.split()[3])
                reading_data = False
                continue
            if line.startswith("#START Date:"):
                data.curve.start_date = line.split(":", maxsplit=1)[1]
                continue
            if line.startswith("#START Time:"):
                times = line.split(":")[1].split()
                data.curve.duration = float(times[1].replace(",", ".")) - float(
                    times[0].replace(",", ".")
                )
                continue
            if line.startswith("#START Curve Legend "):
                data.curve.key = line.split(":", maxsplit=1)[1]
                continue
            if (
                data
                and data.curve.curve_number
                and line.startswith(f"#START Curve {data.curve.curve_number:d}")
            ):
                data.curve.points = int(line.split("=")[1])
                continue
            if line.startswith("#START Curve Data"):
                reading_data = True
                continue
            elif reading_data:
                if data.curve.curve_number and line.startswith(
                    f"#END Curve {data.curve.curve_number:d} -"
                ):
                    reading_data = False
                    continue
                if data.curve.data.shape[0]:
                    data.curve.data = np.vstack(
                        (
                            data.curve.data,
                            [float(item.replace(",", ".")) for item in line.split()],
                        )
                    )
                else:
                    data.curve.data = np.fromiter(
                        (float(item.replace(",", ".")) for item in line.split()),
                        dtype=np.float64,
                    )
                continue
        # end for line ...
    # end with open ...
    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.stderr.write(f"\033[1m\0usage:\033[0m {sys.argv[0]} file1 ...")

    for f in sys.argv[1:]:
        print(f"PROPERTIES OF {f}:")
        print(read_grd(Path(f)))
    print("done")
