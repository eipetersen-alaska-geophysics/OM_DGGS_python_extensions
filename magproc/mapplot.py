import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import geopandas as gpd
import contextily as ctx

def plot_map(gdf, zoom=12, background_size=512, max_points=None, **kw):
    """Plot data with contextily basemap. Assumes Easting/Northing in self.meta['crs']."""

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

    extent = zoom_to_extent(zoom, background_size)
    xlim = (x_center - extent / 2, x_center + extent / 2)
    ylim = (y_center - extent / 2, y_center + extent / 2)

    if "ax" in kw:
        ax = kw.pop("ax")
    else:
        ax = plt.gca()

    sample = gdf.cx[xlim[0]:xlim[1], ylim[0]:ylim[1]]
    if max_points is not None and len(sample) > max_points:
        sample = sample.sample(n=min(len(sample), max_points), random_state=42)
        
    sample.plot(ax=ax, **kw)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    ctx.add_basemap(ax, source=ctx.providers.OpenTopoMap, zoom=zoom)
    
    return ax
