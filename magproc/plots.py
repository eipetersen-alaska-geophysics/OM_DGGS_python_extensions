import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

def plot_drape_qc(data, line, **kw):
    fig = plt.figure(**kw)
    gs = gridspec.GridSpec(5, 1, height_ratios=[1, 1, 1, 4, 1], hspace=0.1)
    
    ax1 = fig.add_subplot(gs[0], sharex=None)
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax5 = fig.add_subplot(gs[4], sharex=ax1)
    for ax in [ax1, ax2, ax3, ax4]:
        ax.label_outer()
    
    data.plot_line(line, columns=["Easting"], ax=ax1)
    data.plot_line(line, columns=["Northing"], ax=ax2)
    data.plot_line(line, columns=["speed"], ax=ax3)
    data.plot_line(line, columns=["drape_p15", "drape_m15", "GPSALT", "DEMIFSAR"], ax=ax4)
    data.plot_line(line, columns=["UTCTIME"], ax=ax5)

    return [ax1, ax2, ax3, ax4, ax5]
