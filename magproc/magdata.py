import pandas as pd
import numpy as np
import yaml
import zipfile
from io import BytesIO, StringIO
from typing import Dict
import os.path
import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point
from scipy.spatial import cKDTree
import matplotlib.gridspec as gridspec
from . import loader

class MagData:
    def __init__(self, data: pd.DataFrame, **meta):
        self.data = data
        self.meta = meta
        
    @classmethod
    def load(cls, path: str, **kws):
        """Load mag data from file. Filename should end in .mag.zip or .csv"""
        if path.endswith(".mag.zip"):
            with zipfile.ZipFile(path, 'r') as z:
                with z.open("data.csv") as f:
                    df = pd.read_csv(f)
                with z.open("meta.yaml") as f:
                    meta = yaml.safe_load(f)
        else:
            df = loader.parse(path)
            meta = {}
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

        xmin, ymin, xmax, ymax = gdf.total_bounds
        x_center = (xmin + xmax) / 2
        y_center = (ymin + ymax) / 2

        def zoom_to_extent(zoom, pixels):
            # Define zoom level and corresponding resolution in meters/pixel
            # Based on Web Mercator tile scale (Google Maps / OSM)
            tile_size = 256  # pixels
            initial_resolution = 2 * np.pi * 6378137 / tile_size  # ≈ 156543.03
            res = initial_resolution / (2 ** zoom)
            extent_meters = tile_size * res
            return extent_meters * (pixels // tile_size)

        extent = zoom_to_extent(zoom, 512) # Two tiles width
        xlim = (x_center - extent / 2, x_center + extent / 2)
        ylim = (y_center - extent / 2, y_center + extent / 2)

        if "ax" in kw:
            ax = kw.pop("ax")
        else:
            fig, ax = plt.subplots()
        gdf.plot(ax=ax, **kw)

        ax.set_xlim(xlim)
        ax.set_ylim(ylim)

        ctx.add_basemap(ax, source=ctx.providers.OpenTopoMap, zoom=zoom)
        ax.set_title(f"Mag Data: {self.meta.get('filename', '')}")
        ax.set_axis_off()
        plt.tight_layout()
        plt.show()            

        return ax
    
    def plot_line(self, line, **kw):
        from . import plots
        return plots.plot_line(self, line, **kw)
        
    def plot_lines(self, plotfn, lines=None, **kw):
        if lines is None:
            lines = self.data.index.get_level_values('Line').unique()
        for line in lines:
            axs = plotfn(self, line, **kw)
            axs[0].set_title(f"Line: {line}")        
            plt.show()
        
    def plot(self, columns=["MAGCOM", "Diurnal", "Residual"], **kw):
        self.plot_lines(MagData.plot_line, columns=columns, **kw)


    def find_line_crossings(self, max_dist = 10):
        df = self.data.reset_index()

        xs = df.Easting.values
        ys = df.Northing.values

        coords = np.vstack((xs, ys)).T
        tree = cKDTree(coords)

        pairs = tree.query_pairs(r=max_dist, output_type="ndarray")
        lines = df['Line'].values

        # Filter pairs where Line differs
        mask = lines[pairs[:, 0]] != lines[pairs[:, 1]]
        filtered_pairs = pairs[mask]

        p1xs = xs[filtered_pairs[:,0]]
        p1ys = ys[filtered_pairs[:,0]]

        p2xs = xs[filtered_pairs[:,1]]
        p2ys = ys[filtered_pairs[:,1]]

        distances = np.sqrt((p1xs - p2xs)**2 + (p1ys - p2ys)**2)

        results = pd.concat([
            df.iloc[filtered_pairs[:, 0]].rename(
                columns={name: name + "_1" for name in df.columns}).reset_index(drop=True),
            df.iloc[filtered_pairs[:, 1]].rename(
                columns={name: name + "_2" for name in df.columns}).reset_index(drop=True)], axis=1
                        ).assign(distance=distances)

        results = results.assign(
            GPSALT_DIFF = np.abs(results.GPSALT_1 - results.GPSALT_2),
            MAGCOM_DIFF = np.abs(results.MAGCOM_1 - results.MAGCOM_2),
            MAGUNCOM_DIFF = np.abs(results.MAGUNCOM_1 - results.MAGUNCOM_2))
        
        min_idx = results.groupby(['Line_1', 'Line_2'])['distance'].idxmin()
        return MagDataLineCrossings(
            self, results.loc[min_idx].reset_index(drop=True),
            max_dist = max_dist)

class MagDataLineCrossings:
    def __init__(self, data: MagData, crossings: pd.DataFrame, max_dist: float):
        self.data = data
        self.crossings = crossings
        self.max_dist = max_dist

    def __repr__(self):
        return f"""Max distance: {self.max_dist}
Filename: {self.data.meta.get("filename", "")}
        
{self.crossings[["GPSALT_DIFF", "MAGCOM_DIFF", "MAGUNCOM_DIFF", "distance"]].describe().T.to_string()}"""
        
    def plot(self, figsize=(20, 6)):
        fig = plt.figure(figsize=figsize)

        gs = gridspec.GridSpec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1], hspace=0, wspace=0)

        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
        ax3 = fig.add_subplot(gs[0, 1], sharey=ax1)

        ax1.hist(self.crossings.GPSALT_DIFF, bins=100, orientation='horizontal')
        ax1.set_ylabel("Altitude difference (m)")
        ax1.set_xlabel("Number of line crossings")

        ax2.hist(self.crossings.MAGCOM_DIFF, bins=100, orientation='horizontal', color="blue", label="MAGCOM")
        ax2.hist(self.crossings.MAGUNCOM_DIFF, bins=100, orientation='horizontal', color="red", histtype='step', label="MAGUNCOM")
        ax2.set_ylabel("MAGCOM/MAGUNCOM difference")
        ax2.set_xlabel("Number of line crossings")
        ax2.legend()
        
        ax3.scatter(self.crossings.MAGCOM_DIFF, self.crossings.GPSALT_DIFF, s=1)
        ax3.set_xlabel("MAGCOM difference")

        ax1.tick_params(labelbottom=False)
        ax3.tick_params(labelleft=False)
        
        return [ax1, ax2, ax3]
