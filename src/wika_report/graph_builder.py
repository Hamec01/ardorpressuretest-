import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Headless mode
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wika_report.config import GraphConfig
from wika_report.models import AnalysisResult


def build_pressure_graph(
    df: pd.DataFrame,
    analysis: AnalysisResult,
    graph_cfg: GraphConfig,
    output_path: Path,
    filename_title: str
) -> Path:
    """
    Generates and saves a high-quality PNG pressure trend graph matching the required format.
    """
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    # Create figure with extra top padding for the header info block
    fig = plt.figure(figsize=(graph_cfg.width_inches, graph_cfg.height_inches), dpi=graph_cfg.dpi)
    
    # We allocate top space for the metadata block: [left, bottom, width, height]
    # Main graph coordinates: left=0.08, bottom=0.20, width=0.74, height=0.62
    ax = fig.add_axes([0.08, 0.20, 0.74, 0.60])

    x_min = df["time_rel_min"].values
    y_press = df["pressure_bar"].values

    # Determine Y-axis limits: Auto-scale to fit fluctuations if limits not set or are 0/160 by default
    # But if the user overrides with specific ones, we respect them.
    # To show fluctuations, we zoom in to data bounds with 5% margins if not using a fixed range.
    if graph_cfg.y_min_bar is not None and graph_cfg.y_max_bar is not None and not (graph_cfg.y_min_bar == 0.0 and graph_cfg.y_max_bar == 160.0):
        ax.set_ylim(graph_cfg.y_min_bar, graph_cfg.y_max_bar)
    else:
        p_min, p_max = np.min(y_press), np.max(y_press)
        p_range = p_max - p_min
        if p_range < 0.1:
            p_range = 1.0  # Avoid division by zero/extreme zoom for flat lines
        ax.set_ylim(max(0, p_min - 0.1 * p_range), p_max + 0.1 * p_range)

    # Highlight hold period if enabled
    if graph_cfg.show_hold_period and analysis.hold_stats and analysis.hold_stats.enabled:
        h_start = analysis.hold_stats.hold_start_min if analysis.hold_stats.hold_start_min is not None else 0.0
        h_end = analysis.hold_stats.hold_end_min if analysis.hold_stats.hold_end_min is not None else float(x_min[-1])
        ax.axvspan(h_start, h_end, color="#e6f2ff", alpha=0.6, label="Hold Period")

    # Main pressure line
    line_press, = ax.plot(x_min, y_press, color="#0055b8", linewidth=2.0, label="Pressure / bar")
    ax.set_ylabel("Pressure, bar", fontsize=11, labelpad=10)
    ax.grid(True, linestyle=":", alpha=0.6)

    # Annotate Min and Max Pressure
    if len(y_press) > 0:
        idx_min = np.argmin(y_press)
        idx_max = np.argmax(y_press)
        
        # Draw Min point and text
        ax.plot(x_min[idx_min], y_press[idx_min], 'ro', markersize=5)
        ax.annotate(
            f"Min: {y_press[idx_min]:.3f} bar",
            xy=(x_min[idx_min], y_press[idx_min]),
            xytext=(10, -10),
            textcoords="offset points",
            fontsize=8,
            color="red",
            weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.6, ec="red")
        )
        
        # Draw Max point and text
        ax.plot(x_min[idx_max], y_press[idx_max], 'go', markersize=5)
        ax.annotate(
            f"Max: {y_press[idx_max]:.3f} bar",
            xy=(x_min[idx_max], y_press[idx_max]),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=8,
            color="green",
            weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.6, ec="green")
        )

    # Secondary Y-axis for Temperature if enabled & data exists
    ax_temp = None
    line_temp = None
    if graph_cfg.plot_temperature and analysis.has_temperature and "temperature_c" in df.columns:
        ax_temp = ax.twinx()
        y_temp = df["temperature_c"].values
        line_temp, = ax_temp.plot(x_min, y_temp, color="#b80055", linewidth=1.5, label="Temperature / °C")
        ax_temp.set_ylabel("Temperature, °C", color="#b80055", fontsize=11, labelpad=10)
        ax_temp.tick_params(axis='y', labelcolor="#b80055")
        
        # Scale temperature with a comfortable margin
        t_min, t_max = np.min(y_temp), np.max(y_temp)
        t_range = t_max - t_min
        if t_range < 0.1:
            t_range = 5.0
        ax_temp.set_ylim(t_min - 0.2 * t_range, t_max + 0.2 * t_range)

    # X-axis configuration: Date & Time ticks
    # We want labels like "13.12.2024 12:47:44" rotated vertically.
    # Select up to ~30 values to avoid clutter
    num_ticks = min(30, len(df))
    tick_indices = np.linspace(0, len(df) - 1, num_ticks, dtype=int)
    
    ax.set_xticks(x_min[tick_indices])
    
    # Tick labels formatting
    if "_time_raw_str" in df.columns:
        tick_labels = df["_time_raw_str"].iloc[tick_indices].values
    else:
        tick_labels = [f"{m:.2f} min" for m in x_min[tick_indices]]
        
    ax.set_xticklabels(tick_labels, rotation=90, fontsize=8)

    # Limit lines
    if graph_cfg.show_limits and analysis.hold_stats and analysis.hold_stats.enabled:
        if analysis.hold_stats.lower_limit_bar is not None:
            ax.axhline(
                analysis.hold_stats.lower_limit_bar,
                color="#f0ad4e",
                linestyle="--",
                linewidth=1.5,
                label=f"Lower Limit ({analysis.hold_stats.lower_limit_bar:.2f} bar)"
            )
        if analysis.hold_stats.upper_limit_bar is not None:
            ax.axhline(
                analysis.hold_stats.upper_limit_bar,
                color="#d9534f",
                linestyle="--",
                linewidth=1.5,
                label=f"Upper Limit ({analysis.hold_stats.upper_limit_bar:.2f} bar)"
            )

    # Legends combined
    lines = [line_press]
    if line_temp:
        lines.append(line_temp)
    labels = [l.get_label() for l in lines]
    ax.legend(lines, labels, loc="center left", bbox_to_anchor=(1.12, 0.5), frameon=True, facecolor="#ffffff", framealpha=0.9)

    # Draw Header Block on the Figure (coordinates in figure fraction)
    # Background for header
    fig.patches.extend([
        plt.Rectangle((0.08, 0.82), 0.84, 0.15, fill=False, edgecolor="black", linewidth=1.5, transform=fig.transFigure)
    ])

    # Left metadata column
    # Calculate duration/time formatted nicely
    start_time_str = ""
    end_time_str = ""
    if analysis.start_time and analysis.end_time:
        start_time_str = analysis.start_time.strftime("%H:%M")
        end_time_str = analysis.end_time.strftime("%H:%M")
    
    test_period = f"{start_time_str} - {end_time_str}" if start_time_str else "N/A"
    
    meta = analysis.custom_meta
    
    col1_text = (
        f"Test period:  {test_period}\n"
        f"Test pressure: {meta.test_pressure or 'N/A'}\n"
        f"System:        {meta.system or 'N/A'}\n"
        f"Log.No:        {meta.log_no or 'N/A'}\n"
        f"Ins.No:        {meta.ins_no or 'N/A'}"
    )
    
    # Auto-extract date if not manually overridden
    date_val = meta.custom_date
    if not date_val:
        if analysis.start_time:
            date_val = analysis.start_time.strftime("%d.%m.%Y")
        else:
            date_val = datetime.now().strftime("%d.%m.%Y")

    col2_text = (
        f"Date:     {date_val}\n"
        f"Project:  {meta.project or 'N/A'}\n"
        f"Note:     {meta.note or 'N/A'}\n"
        f"Wika nr:  {meta.wika_nr or 'N/A'}"
    )

    fig.text(0.09, 0.83, col1_text, fontsize=9.5, family="monospace", verticalalignment="bottom")
    fig.text(0.36, 0.83, col2_text, fontsize=9.5, family="monospace", verticalalignment="bottom")
    
    # Title in the header block
    diagram_title = "PRESSURE TEST DIAGRAM"
    if meta.project and meta.project != "N/A":
        diagram_title = f"{meta.project}\n{diagram_title}"
    fig.text(0.60, 0.93, diagram_title, fontsize=12, fontweight="bold", horizontalalignment="center")



    # Ardor Logo Image on the right
    # Determine logo path depending on whether we run in PyInstaller bundle or dev mode
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        logo_path = Path(sys._MEIPASS) / "resources" / "logo.png"
    else:
        logo_path = Path(__file__).parent.parent.parent / "resources" / "logo.png"

    if logo_path.exists():
        try:
            # We add a small axes to place the logo image inside the header box
            # header box: X=0.08..0.92, Y=0.82..0.97
            # Logo is placed at right: X=0.76..0.91, Y=0.835..0.955
            ax_logo = fig.add_axes([0.76, 0.835, 0.15, 0.12])
            logo_img = plt.imread(str(logo_path))
            ax_logo.imshow(logo_img)
            ax_logo.axis('off')
        except Exception as e:
            # Fallback text if image read fails
            fig.text(0.88, 0.89, "ARDOR", fontsize=16, fontweight="bold", color="#1F4E79", horizontalalignment="right", verticalalignment="center")
            fig.text(0.88, 0.85, "SHIPPING & PIPING", fontsize=8, fontweight="bold", color="#7F7F7F", horizontalalignment="right", verticalalignment="center")
    else:
        fig.text(0.88, 0.89, "ARDOR", fontsize=16, fontweight="bold", color="#1F4E79", horizontalalignment="right", verticalalignment="center")
        fig.text(0.88, 0.85, "SHIPPING & PIPING", fontsize=8, fontweight="bold", color="#7F7F7F", horizontalalignment="right", verticalalignment="center")



    # Pipe Logs Panel (if enabled)
    if graph_cfg.show_pipe_logs and graph_cfg.pipe_logs_text and graph_cfg.pipe_logs_text.strip():
        lines_pipe = [line.strip() for line in graph_cfg.pipe_logs_text.splitlines() if line.strip()]
        if lines_pipe:
            pipes_str = "Pipes:\n" + "\n".join(lines_pipe)
            fig.text(
                1.12, 0.25,
                pipes_str,
                fontsize=10,
                verticalalignment="bottom",
                horizontalalignment="left",
                bbox=dict(boxstyle="round,pad=0.5", fc="#f8f9fa", ec="#ced4da", lw=1)
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=graph_cfg.dpi, format="png", bbox_inches="tight")
    plt.close(fig)

    return output_path
