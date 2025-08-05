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
    def load(cls, path: str):
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
        return cls(df.set_index(["Line", "FIDCOUNT"]), **meta)

    def save(self, path: str):
        """Save mag data to file. Filename should end in .mag.zip"""
        with zipfile.ZipFile(path, 'w') as z:
            csv_buffer = StringIO()
            self.data.reset_index().to_csv(csv_buffer, index=False)
            z.writestr("data.csv", csv_buffer.getvalue())
            z.writestr("meta.yaml", yaml.dump(self.meta))

    def __repr__(self):
        return f"""{yaml.dump(self.meta)}

        {self.data.describe().T.to_string()}"""


    def plot(self, zoom=12, max_points=5000, **kw):
        """Plot data with contextily basemap. Assumes Easting/Northing in self.meta['crs']."""
        crs = self.meta.get('crs', None)

        plot_data = self.data.sample(n=min(len(self.data), max_points), random_state=42)

        gdf = gpd.GeoDataFrame(
            plot_data,
            geometry=gpd.points_from_xy(plot_data.Easting, plot_data.Northing),
            crs=crs or 3857)
        if crs is not None:
            gdf = gdf.to_crs(epsg=3857)

        ax = gdf.plot(**kw)

        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=zoom)
        ax.set_title(f"Mag Data: {self.meta.get('filename', '')}")
        ax.set_axis_off()
        if "ax" not in kw:
            plt.tight_layout()
            plt.show()
        return ax
