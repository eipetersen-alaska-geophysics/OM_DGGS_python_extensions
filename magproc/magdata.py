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
import copy
from . import mapplot
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

    def get_lines(self):
        return self.data.index.get_level_values('Line').unique()
    
    def get_sample_frequency(self):
        if "sample_frequency" not in self.meta:
            timediffs = self.data.UTCTIME - self.data.UTCTIME.shift(1)
            self.meta["sample_frequency"] = float(
                1 / (timediffs[
                    self.data.index.get_level_values('Line')
                    == pd.Series(self.data.index.get_level_values('Line')).shift(1)
                ].mode()[0]))
        return self.meta["sample_frequency"]

    def as_geodataframe(self):
        crs = self.meta.get('crs', None)
        gdf = gpd.GeoDataFrame(
            self.data.copy(),
            geometry=gpd.points_from_xy(self.data.Easting, self.data.Northing),
            crs=crs or 3857
        )
        if crs is not None:
            gdf = gdf.to_crs(epsg=3857)
        return gdf

    def to_crs(self, crs):
        data = self.data.copy()
        geom = self.as_geodataframe().to_crs(crs).geometry

        data["Easting"] = geom.x.values
        data["Northing"] = geom.y.values

        meta = copy.deepcopy(self.meta)
        meta["crs"] = crs
        
        return type(self)(data, **meta)

    def append(self, other):
        assert self.meta.get("crs") == other.meta.get("crs"), "Both datasets need to have the same CRS to be merged. Use to_crs() first."

        def merge_meta(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                return {k: a[k] if k not in b else (b[k] if k not in a else merge_meta(a[k], b[k]))
                        for k in set(a.keys()).union(b.keys())}
            else:
                return a
                
        data = pd.concat((self.data, other.data), axis=0)
        meta = merge_meta(self.meta, other.meta)

        return type(self)(data, **meta)
    
    def plot_map(self, markersize=1, column="MAGCOM", zoom=9, max_points=5000, **kw):
        """Plot data with contextily basemap. Assumes Easting/Northing in self.meta['crs']."""
        gdf = self.as_geodataframe()
        ax = mapplot.plot_map(gdf, markersize=markersize, column=column, zoom=zoom, max_points=max_points, **kw)
        ax.set_title(f"Mag Data: {self.meta.get('filename', '')}")
        ax.set_axis_off()

        return ax
    
    def plot_line(self, line, **kw):
        from . import plots
        return plots.plot_line(self, line, **kw)
        
    def plot_lines(self, plotfn, lines=None, **kw):
        if lines is None:
            lines = self.get_lines()
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

    def as_geodataframe(self):
        crs = self.data.meta.get('crs', None)
        gdf = gpd.GeoDataFrame(
            self.crossings.copy(),
            geometry=gpd.points_from_xy(self.crossings.Easting_1, self.crossings.Northing_1),
            crs=crs or 3857
        )
        if crs is not None:
            gdf = gdf.to_crs(epsg=3857)
        return gdf
    
    def plot_map(self, markersize=1, column="MAGCOM_DIFF", zoom=9, **kw):
        gdf = self.as_geodataframe()
        return mapplot.plot_map(gdf, markersize=markersize, zoom=zoom, column=column, **kw)        
    
    def plot(self, figsize=(20, 6)):
        fig = plt.figure(figsize=figsize)

        gs = gridspec.GridSpec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1], hspace=0, wspace=0)

        ax0 = fig.add_subplot(gs[0, 0])
        ax1 = fig.add_subplot(gs[0, 1], sharey=ax0)
        ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)

        ax0.scatter(self.crossings.MAGCOM_DIFF, self.crossings.GPSALT_DIFF, s=1)
        ax0.set_xlabel("MAGCOM difference")
        ax0.set_ylabel("Altitude difference (m)")

        ax0.secondary_xaxis('top').set_xlabel("MAGCOM difference")
        
        ax1.hist(self.crossings.GPSALT_DIFF, bins=100, orientation='horizontal')
        ax1.set_xlabel("Number of line crossings")
        ax1.secondary_yaxis('right').set_ylabel("Altitude difference (m)")

        ax2.hist(self.crossings.MAGCOM_DIFF, bins=100, color="blue", label="MAGCOM")
        ax2.hist(self.crossings.MAGUNCOM_DIFF, bins=100, color="red", histtype='step', label="MAGUNCOM")
        ax2.set_xlabel("MAGCOM/MAGUNCOM difference")
        ax2.legend()
        ax2.invert_yaxis()
        ax2.secondary_yaxis('right').set_ylabel("Number of line crossings")

        
        ax0.tick_params(labelbottom=False)
        ax1.tick_params(labelleft=False)
        ax2.tick_params(labelleft=False)
        
        return [ax0, ax1, ax2]
