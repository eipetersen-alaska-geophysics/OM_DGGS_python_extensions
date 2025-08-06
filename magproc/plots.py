import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

def plot_line(data, line, columns=["MAGCOM", "Diurnal", "Residual"], xcolumn="index", ax=None):
    linedata = data.data.loc[line]

    ax1 = ax
    if ax is None:
        fig, ax1 = plt.subplots()
    ax2 = None

    if xcolumn == "index":
        xdata = linedata.index
    else:
        xdata = linedata[xcolumn]

    ax1cols = []
    for column in columns:
        if column == "Residual":
            ax2 = ax1.twinx()
            ax2.plot(xdata, linedata.MAGCOM - linedata.Diurnal, c="blue", label="Residual (MAGCOM - Diurnal)")
            ax2.set_ylabel("Residual")
            ax2.tick_params(axis='y')
        else:
            ax1.plot(xdata, linedata[column], label=column)
            ax1cols.append(column)

    ax1.set_xlabel(xcolumn)
    ax1.set_ylabel(" / ".join(ax1cols))
    ax1.tick_params(axis='y')

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels() if ax2 is not None else ([], [])
    if len(labels_1 + labels_2) > 1:
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")

    return [ax1, ax2] if ax2 is not None else [ax1]


def plot_drape_qc(data, line, figsize=(20, 15), **kw):
    fig = plt.figure(figsize=figsize)
    gs = gridspec.GridSpec(5, 1, height_ratios=[1, 1, 1, 4, 1], hspace=0.1)
    
    ax1 = fig.add_subplot(gs[0], sharex=None)
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax5 = fig.add_subplot(gs[4], sharex=ax1)
    
    plot_line(data, line, columns=["Easting"], ax=ax1, **kw)
    plot_line(data, line, columns=["Northing"], ax=ax2, **kw)
    plot_line(data, line, columns=["speed"], ax=ax3, **kw)
    plot_line(data, line, columns=["drape_p15", "drape_m15", "GPSALT", "DEMIFSAR"], ax=ax4, **kw)
    plot_line(data, line, columns=["UTCTIME"], ax=ax5, **kw)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.label_outer()
    
    return [ax1, ax2, ax3, ax4, ax5]

def plot_diurnal_qc(data, line, figsize=(10, 10), **kw):
    fig = plt.figure(figsize=figsize)
    gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1], hspace=0.1)
    
    ax1 = fig.add_subplot(gs[0], sharex=None)
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    
    
    plot_line(data, line, columns=["L_magDIFF60", "zero"], ax=ax1, **kw)
    plot_line(data, line, columns=["L_magDIFF15", "zero"], ax=ax2, **kw)
    plot_line(data, line, columns=["MAGCOM", "Diurnal"], ax=ax3, **kw)

    for ax in [ax1, ax2]:
        ax.label_outer()
    
    return [ax1, ax2, ax3]

def plot_hf_noise_qc(data, line, figsize=(10, 10), **kw):
    fig = plt.figure(figsize=figsize)
    gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1], hspace=0.1)
    
    ax1 = fig.add_subplot(gs[0], sharex=None)
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    
    plot_line(data, line, columns=["MAGCOM", "MAGUNCOM"], ax=ax1, **kw)
    plot_line(data, line, columns=["hf_noise", "MAGCOM_4th"], ax=ax2, **kw)

    ax1.label_outer()
    
    return [ax1, ax2]
