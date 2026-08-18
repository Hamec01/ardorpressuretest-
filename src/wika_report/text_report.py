from datetime import datetime
from pathlib import Path
from typing import List, Optional

from wika_report import __version__
from wika_report.models import AnalysisResult, ColumnMapping, FileMetadata, CleaningStats


def generate_text_report(
    meta: FileMetadata,
    mapping: ColumnMapping,
    stats: CleaningStats,
    analysis: AnalysisResult,
    warnings: List[str],
    output_path: Path
) -> Path:
    """
    Generates a concise summary text report (.txt) in English.
    """
    lines = []
    lines.append("=" * 65)
    lines.append(" WIKA CPG1500 CSV PRESSURE ANALYSIS REPORT")
    lines.append("=" * 65)
    lines.append(f"File Name:             {meta.input_path.name}")
    lines.append(f"Report Date:           {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Program Version:       wika-cpg1500-graph v{__version__}")
    lines.append("-" * 65)

    lines.append("\n[1] FILE METADATA AND PARAMETERS")
    lines.append(f"Encoding:               {meta.encoding}")
    lines.append(f"Column Delimiter:       '{meta.delimiter}'")
    lines.append(f"Decimal Separator:      '{meta.decimal_sep}'")
    lines.append(f"Detected Input Unit:    {meta.detected_unit or 'Undetermined'} ({meta.detected_unit_source or 'N/A'})")
    lines.append(f"Target Unit:            bar")

    lines.append("\n[2] DETECTED COLUMNS")
    lines.append(f"Time Column:            {mapping.time_col or 'Not found'}")
    if mapping.date_col:
        lines.append(f"Date Column:            {mapping.date_col}")
    lines.append(f"Pressure Column:        {mapping.pressure_col or 'Not found'}")

    lines.append("\n[3] CLEANING AND MEASUREMENT SUMMARY")
    lines.append(f"Start Time:             {analysis.start_time.strftime('%Y-%m-%d %H:%M:%S') if analysis.start_time else 'N/A'}")
    lines.append(f"End Time:               {analysis.end_time.strftime('%Y-%m-%d %H:%M:%S') if analysis.end_time else 'N/A'}")
    lines.append(f"Total Duration:         {analysis.duration_formatted}")
    
    meta_ref = analysis.custom_meta
    lines.append(f"Test Pressure:          {meta_ref.test_pressure or 'N/A'}")
    lines.append(f"System:                 {meta_ref.system or 'N/A'}")
    lines.append(f"Log No:                 {meta_ref.log_no or 'N/A'}")
    lines.append(f"Ins No:                 {meta_ref.ins_no or 'N/A'}")
    lines.append(f"Project:                {meta_ref.project or 'N/A'}")
    lines.append(f"Note:                   {meta_ref.note or 'N/A'}")
    lines.append(f"Wika Nr:                {meta_ref.wika_nr or 'N/A'}")
    
    pipe_text = getattr(meta_ref, "pipe_logs_text", "").strip()
    if pipe_text:
        pipe_items = [p.strip() for p in pipe_text.splitlines() if p.strip()]
        if pipe_items:
            lines.append("Pipe Logs (Pipe Numbers):")
            for pipe_item in pipe_items:
                lines.append(f"  - {pipe_item}")
    
    lines.append(f"Total CSV Rows:         {analysis.total_raw_rows}")
    lines.append(f"Valid Points:           {analysis.valid_points_count}")
    lines.append(f"Excluded Rows:          {analysis.excluded_rows_count}")

    if stats.exclusion_reasons:
        lines.append("  Exclusion Reasons:")
        for reason, count in stats.exclusion_reasons.items():
            lines.append(f"    - {reason}: {count}")


    lines.append("\n[4] PRESSURE METRICS (bar)")
    lines.append(f"Start Pressure:         {analysis.start_pressure_bar:.5f} bar")
    lines.append(f"End Pressure:           {analysis.end_pressure_bar:.5f} bar")
    lines.append(f"Min Pressure:           {analysis.min_pressure_bar:.5f} bar")
    lines.append(f"Max Pressure:           {analysis.max_pressure_bar:.5f} bar (at: {analysis.max_pressure_time_str})")
    lines.append(f"Mean Pressure:          {analysis.mean_pressure_bar:.5f} bar")
    lines.append(f"Median Pressure:        {analysis.median_pressure_bar:.5f} bar")
    lines.append(f"Std Deviation:          {analysis.std_pressure_bar:.5f} bar")
    lines.append(f"Total Delta (end-start):{analysis.total_delta_bar:.5f} bar")
    lines.append(f"Pressure Range (max-min):{analysis.range_bar:.5f} bar")
    lines.append(f"Max Rise Rate:          {analysis.max_rise_rate_bar_per_min:.4f} bar/min")
    lines.append(f"Max Drop Rate:          {analysis.max_drop_rate_bar_per_min:.4f} bar/min")

    lines.append("\n[5] TEST EVALUATION (PASS / FAIL)")
    if analysis.hold_stats and analysis.hold_stats.enabled:
        lines.append(f"Evaluation Status:      {analysis.hold_stats.status}")
        if analysis.hold_stats.fail_reasons:
            lines.append("  FAIL Reasons:")
            for fr in analysis.hold_stats.fail_reasons:
                lines.append(f"    - {fr}")
    else:
        lines.append("Evaluation Status:      Not Evaluated (criteria not specified in config.json)")

    if warnings:
        lines.append("\n[6] WARNINGS AND REMARKS")
        for w in warnings:
            lines.append(f"  - {w}")

    lines.append("\n" + "=" * 65)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path
