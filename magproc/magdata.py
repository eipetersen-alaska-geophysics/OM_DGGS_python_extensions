import pandas as pd
import yaml
import zipfile
from io import BytesIO, StringIO
from typing import Dict
import os.path
import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point

class MagData:
    def __init__(self, data: pd.DataFrame, **meta):
        self.data = data
        self.meta = meta
        
    @classmethod
    def load(cls, path: str, **kws):
        """Load mag data from file. Filename should end in .mag.zip or .csv"""
        if path.endswith(".csv"):
            with open(path) as f:
                df = pd.read_csv(f)
                meta = {}
        else:
            with zipfile.ZipFile(path, 'r') as z:
                with z.open("data.csv") as f:
                    df = pd.read_csv(f)
                with z.open("meta.yaml") as f:
                    meta = yaml.safe_load(f)
        meta["filename"] = os.path.split(path)[-1]
        meta.update(kws)
        return cls(df.set_index(["Line", "FIDCOUNT"]), **meta)

    def save(self, path: str):
        """Save mag data to file. Filename should end in .mag.zip"""
        with zipfile.ZipFile(path, 'w') as z:
            csv_buffer = StringIO()
            self.data.reset_index().to_csv(csv_buffer, index=False)
            z.writestr("data.csv", csv_buffer.getvalue())
            z.writestr("meta.yaml", yaml.dump(self.meta))

    def __repr__(self):
        self.get_sample_frequency()
        return f"""{yaml.dump(self.meta)}

        {self.data.describe().T.to_string()}"""

    def get_sample_frequency(self):
        if "sample_frequency" not in self.meta:
            timediffs = self.data.UTCTIME - self.data.UTCTIME.shift(1)
            self.meta["sample_frequency"] = float(
                1 / (timediffs[
                    self.data.index.get_level_values('Line')
                    == pd.Series(self.data.index.get_level_values('Line')).shift(1)
                ].mode()[0]))
        return self.meta["sample_frequency"]
    
    def plot_map(self, zoom=12, max_points=5000, **kw):
        """Plot data with contextily basemap. Assumes Easting/Northing in self.meta['crs']."""
        crs = self.meta.get('crs', None)

        gdf = gpd.GeoDataFrame(
            self.data.copy(),
            geometry=gpd.points_from_xy(self.data.Easting, self.data.Northing),
            crs=crs or 3857
        )

        if crs is not None:
            gdf = gdf.to_crs(epsg=3857)


        if "ax" in kw:
            ax = kw["ax"]
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
        else:
            # Get full bounds of the data (to estimate center)
            xmin, ymin, xmax, ymax = gdf.total_bounds
            x_center = (xmin + xmax) / 2
            y_center = (ymin + ymax) / 2
            tile_size = 40075016.68557849 / (2 ** zoom)  # world extent / 2^zoom
            half_size = tile_size / 2

            xlim = (x_center - half_size, x_center + half_size)
            ylim = (y_center - half_size, y_center + half_size)

        gdf = gdf.cx[xlim[0]:xlim[1], ylim[0]:ylim[1]]
        gdf = gdf.sample(n=min(len(gdf), max_points), random_state=42)

        ax = gdf.plot(**kw)
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=zoom)
        ax.set_title(f"Mag Data: {self.meta.get('filename', '')}")
        ax.set_axis_off()

        if "ax" not in kw:
            plt.tight_layout()
            plt.show()

        return ax

    def plot_line(self, line, columns=["MAGCOM", "Diurnal", "Residual"], ax=None):
        linedata = self.data.loc[line]

        ax1 = ax
        if ax is None:
            fig, ax1 = plt.subplots()
        ax2 = None

        ax1cols = []
        for column in columns:
            if column == "Residual":
                ax2 = ax1.twinx()
                ax2.plot(linedata.index, linedata.MAGCOM - linedata.Diurnal, c="blue", label="Residual (MAGCOM - Diurnal)")
                ax2.set_ylabel("Residual")
                ax2.tick_params(axis='y')
            else:
                ax1.plot(linedata.index, linedata[column], label=column)
                ax1cols.append(column)

        ax1.set_ylabel(" / ".join(ax1cols))
        ax1.tick_params(axis='y')

        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels() if ax2 is not None else ([], [])
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")

        return [ax1, ax2] if ax2 is not None else [ax1]
        
    def plot_lines(self, plotfn, **kw):
        for line in self.data.index.get_level_values('Line').unique():
            axs = plotfn(self, line, **kw)
            axs[0].set_title(f"Line: {line}")        
            plt.show()
        
    def plot(self, columns=["MAGCOM", "Diurnal", "Residual"], **kw):
        self.plot_lines(MagData.plot_line, columns=columns, **kw)
