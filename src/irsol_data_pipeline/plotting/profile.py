from matplotlib import pyplot as plt
import numpy as np
from typing import Optional
from irsol_data_pipeline.core.types import StokesParameters


def plot(
    data: StokesParameters,
    /,
    vrange_si=False,
    vrange_sq=False,
    vrange_su=False,
    vrange_sv=False,
    title=None,
    filename_save=None,
    pix_low=None,
    pix_high=None,
    pix_quiet_low=None,
    pix_quiet_high=None,
    alpha_px=0.21,
    colors_lines=["tab:blue", "tab:orange", "tab:green", "tab:red"],
    a0: Optional[float] = None,
    a1: Optional[float] = None,
):
    """
    Plot the Stokes profiles, similar as it is done in the ZIMPOL sw.
    Here the script assumes that si, sq, su, sv are 2D arrays of the same shape:
              si.shape = (n_spatial_points, n_wavelengths)
              the same for sq, su, sv

    Parameters:
    -----------
        data: StokesParametes to be plotted.
        vrange_sq : list or tuple, optional
            Two-element list or tuple specifying the vmin and vmax for Stokes Q/I plot.
            If False, it will be set automatically.
        vrange_su : list or tuple, optional
            Two-element list or tuple specifying the vmin and vmax for Stokes U/I plot.
            If False, it will be set automatically.
        vrange_sv : list or tuple, optional
            Two-element list or tuple specifying the vmin and vmax for Stokes V/I plot.
            If False, it will be set automatically.
        title : str, optional
            Title for the entire figure.
        filename_save : str, optional
            If provided, the figure will be saved to this filename.
        show : bool, optional
            If True, the plot will be displayed. If False, it will not be shown.
        pix_low : list, optional
            List of lower pixel indices to highlight on the plots, which indicate the
            location of the spatial average.
        pix_high : list, optional
            List of higher pixel indices to highlight on the plots, which indicate the
            location of the spatial average.
        pix_quiet_low : list, optional
            List of lower pixel indices to highlight quiet Sun regions on the plots.
        pix_quiet_high : list, optional
            List of higher pixel indices to highlight quiet Sun regions on the plots.
        alpha_px : float, optional
            Transparency of the shaded areas defined by pix_low and pix_high
        colors_lines : list, optional
            List of colors to use for highlighting the pixel ranges.
        a0 : float, optional
            Wavelength offset in Angstroms. When both a0 and a1 are provided,
            the x-axis is displayed in Angstroms instead of pixels.
        a1 : float, optional
            Wavelength dispersion in Angstroms/pixel. When both a0 and a1 are
            provided, the x-axis is displayed in Angstroms instead of pixels.
    """

    si, sq, su, sv = data
    ### If no TCU has been used, then Q, U and V might have an offset that has to be considered for vrange
    if vrange_sq is False:
        dq = 0.01
        mean_sq = np.mean(sq)
        vrange_sq = [mean_sq - dq, mean_sq + dq]
    if vrange_su is False:
        du = 0.01
        mean_su = np.mean(su)
        vrange_su = [mean_su - du, mean_su + du]
    if vrange_sv is False:
        dv = 0.01
        mean_sv = np.mean(sv)
        vrange_sv = [mean_sv - dv, mean_sv + dv]

    # Create the figure with the four Stokes components
    plt.rcParams["font.size"] = 16
    fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=True)
    plt.subplots_adjust(hspace=0)

    if title is not None:
        plt.suptitle(title, fontsize=24, y=0.97)

    # Define extent for imshow (to set proper axes)
    if a0 is not None and a1 is not None:
        wavelength_min = a0
        wavelength_max = a0 + a1 * (si.shape[1] - 1)
        str_wlt_axis = r"Wavelength [$\AA{}$]"
    else:
        wavelength_min, wavelength_max = 0, si.shape[1]
        str_wlt_axis = "Wavelength dimension [px]"
    spatial_min, spatial_max = 0, si.shape[0]
    extent = [wavelength_min, wavelength_max, spatial_min, spatial_max]

    ## Plot Stokes I
    if vrange_si is False:
        im0 = axes[0].imshow(
            si, cmap="gist_gray", aspect="auto", extent=extent, origin="lower"
        )
    else:
        im0 = axes[0].imshow(
            si,
            cmap="gist_gray",
            aspect="auto",
            extent=extent,
            origin="lower",
            vmin=vrange_si[0],
            vmax=vrange_si[1],
        )
    axes[0].set_ylabel("Spatial dimension [px]")
    axes[0].text(
        0.02,
        0.9,
        "I",
        transform=axes[0].transAxes,
        color="white",
        fontweight="bold",
        fontsize=15,
        bbox=dict(facecolor="black", alpha=0.5),
    )
    plt.colorbar(im0, ax=axes[0], orientation="vertical", pad=0.01)

    ## Plot Stokes Q/I
    im1 = axes[1].imshow(
        sq,
        cmap="gist_gray",
        aspect="auto",
        extent=extent,
        vmin=vrange_sq[0],
        vmax=vrange_sq[1],
        origin="lower",
    )
    axes[1].set_ylabel("Spatial dimension [px]")
    axes[1].text(
        0.02,
        0.9,
        "Q/I",
        transform=axes[1].transAxes,
        color="white",
        fontweight="bold",
        fontsize=15,
        bbox=dict(facecolor="black", alpha=0.5),
    )
    plt.colorbar(im1, ax=axes[1], orientation="vertical", pad=0.01)

    ## Plot Stokes U/I
    im2 = axes[2].imshow(
        su,
        cmap="gist_gray",
        aspect="auto",
        extent=extent,
        vmin=vrange_su[0],
        vmax=vrange_su[1],
        origin="lower",
    )
    axes[2].set_ylabel("Spatial dimension [px]")
    axes[2].text(
        0.02,
        0.9,
        "U/I",
        transform=axes[2].transAxes,
        color="white",
        fontweight="bold",
        fontsize=15,
        bbox=dict(facecolor="black", alpha=0.5),
    )
    plt.colorbar(im2, ax=axes[2], orientation="vertical", pad=0.01)

    ## Plot Stokes V/I
    im3 = axes[3].imshow(
        sv,
        cmap="gist_gray",
        aspect="auto",
        extent=extent,
        vmin=vrange_sv[0],
        vmax=vrange_sv[1],
        origin="lower",
    )
    axes[3].set_xlabel(str_wlt_axis)
    axes[3].set_ylabel("Spatial dimension [px]")
    axes[3].text(
        0.02,
        0.9,
        "V/I",
        transform=axes[3].transAxes,
        color="white",
        fontweight="bold",
        fontsize=15,
        bbox=dict(facecolor="black", alpha=0.5),
    )
    plt.colorbar(im3, ax=axes[3], orientation="vertical", pad=0.01)

    # Add pixel ranges highlights
    if pix_low is not None and pix_high is not None:
        for i in range(len(pix_low)):
            axes[0].axhspan(
                pix_high[i], pix_low[i], color=colors_lines[i], alpha=alpha_px, zorder=0
            )
            axes[1].axhspan(
                pix_high[i], pix_low[i], color=colors_lines[i], alpha=alpha_px, zorder=0
            )
            axes[2].axhspan(
                pix_high[i], pix_low[i], color=colors_lines[i], alpha=alpha_px, zorder=0
            )
            axes[3].axhspan(
                pix_high[i], pix_low[i], color=colors_lines[i], alpha=alpha_px, zorder=0
            )

    if pix_quiet_low is not None and pix_quiet_high is not None:
        for i in range(len(pix_quiet_low)):
            axes[0].axhline(
                pix_quiet_high[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[0].axhline(
                pix_quiet_low[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[1].axhline(
                pix_quiet_high[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[1].axhline(
                pix_quiet_low[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[2].axhline(
                pix_quiet_high[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[2].axhline(
                pix_quiet_low[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[3].axhline(
                pix_quiet_high[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )
            axes[3].axhline(
                pix_quiet_low[i],
                color="black",
                linestyle="--",
                linewidth=1,
                zorder=0,
                alpha=0.7,
            )

    for ax in [axes[0], axes[1], axes[2], axes[3]]:
        # ax.set_xticklabels([])
        # Also hide the x-axis ticks themselves
        # ax.tick_params(axis='x', which='both', length=0)
        ax.tick_params(
            axis="x", which="major", direction="in", length=7, width=1.5, top=True
        )
        ax.tick_params(
            axis="y", which="major", direction="in", length=7, width=1.5, right=True
        )

    # Improve overall appearance
    plt.tight_layout(h_pad=-0.7, w_pad=0)
    plt.savefig(filename_save, dpi=100, bbox_inches="tight")
