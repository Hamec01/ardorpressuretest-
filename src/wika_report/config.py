import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GraphConfig:
    dpi: int = 180
    width_inches: float = 14.0
    height_inches: float = 7.0
    show_minimum: bool = True
    show_maximum: bool = True
    show_limits: bool = True
    show_hold_period: bool = True
    y_min_bar: Optional[float] = 0.0
    y_max_bar: Optional[float] = 160.0
    show_datetime: bool = False
    show_pipe_logs: bool = False
    pipe_logs_text: str = ""
    plot_temperature: bool = True
    wika_nr_list: List[str] = field(default_factory=lambda: ["S# 1A01JFDQ12E"])
    wika_nr_active: str = "S# 1A01JFDQ12E"
    
    # Defaults for GUI metadata inputs
    default_test_pressure: str = "24bar"
    default_system: str = "64700"
    default_log_no: str = "044-1"
    default_ins_no: str = "NB1402PM-13388"
    default_project: str = "NB402"
    default_note: str = ""



@dataclass
class AnalysisConfig:
    test_pressure_bar: Optional[float] = None
    lower_limit_bar: Optional[float] = None
    upper_limit_bar: Optional[float] = None
    hold_start_time_minutes: Optional[float] = None
    hold_end_time_minutes: Optional[float] = None
    allowed_drop_bar: Optional[float] = None
    create_pass_fail_result: bool = False


@dataclass
class AppConfig:
    target_unit: str = "bar"
    default_input_unit: Optional[str] = None
    move_processed_files: bool = False
    open_output_folder_after_finish: bool = True
    graph: GraphConfig = field(default_factory=GraphConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)


def load_config(config_path: Path) -> AppConfig:
    """Loads and validates configuration from JSON file."""
    if not config_path.exists():
        return AppConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Error reading configuration file {config_path}: {e}")

    return parse_config_dict(data)


def parse_config_dict(data: Dict[str, Any]) -> AppConfig:
    """Parses and validates configuration dictionary."""
    cfg = AppConfig()

    if "target_unit" in data:
        unit = str(data["target_unit"]).strip().lower()
        if unit != "bar":
            raise ValueError(f"Unsupported target unit 'target_unit': {data['target_unit']}. Only 'bar' is supported.")
        cfg.target_unit = unit

    if "default_input_unit" in data and data["default_input_unit"] is not None:
        cfg.default_input_unit = str(data["default_input_unit"]).strip()

    if "move_processed_files" in data:
        if not isinstance(data["move_processed_files"], bool):
            raise ValueError("Parameter 'move_processed_files' must be a boolean (true/false).")
        cfg.move_processed_files = data["move_processed_files"]

    if "open_output_folder_after_finish" in data:
        if not isinstance(data["open_output_folder_after_finish"], bool):
            raise ValueError("Parameter 'open_output_folder_after_finish' must be a boolean (true/false).")
        cfg.open_output_folder_after_finish = data["open_output_folder_after_finish"]

    # Graph settings
    if "graph" in data and isinstance(data["graph"], dict):
        g_data = data["graph"]
        if "dpi" in g_data:
            dpi = int(g_data["dpi"])
            if dpi < 72 or dpi > 600:
                raise ValueError(f"Invalid 'graph.dpi' value: {dpi}. Valid range: 72..600.")
            cfg.graph.dpi = dpi

        if "width_inches" in g_data:
            cfg.graph.width_inches = float(g_data["width_inches"])
        if "height_inches" in g_data:
            cfg.graph.height_inches = float(g_data["height_inches"])
        if "show_minimum" in g_data:
            cfg.graph.show_minimum = bool(g_data["show_minimum"])
        if "show_maximum" in g_data:
            cfg.graph.show_maximum = bool(g_data["show_maximum"])
        if "show_limits" in g_data:
            cfg.graph.show_limits = bool(g_data["show_limits"])
        if "show_hold_period" in g_data:
            cfg.graph.show_hold_period = bool(g_data["show_hold_period"])
        if "y_min_bar" in g_data:
            cfg.graph.y_min_bar = float(g_data["y_min_bar"]) if g_data["y_min_bar"] is not None else None
        if "y_max_bar" in g_data:
            cfg.graph.y_max_bar = float(g_data["y_max_bar"]) if g_data["y_max_bar"] is not None else None
        if "show_datetime" in g_data:
            cfg.graph.show_datetime = bool(g_data["show_datetime"])
        # Support both old 'tube' keys and new 'pipe' keys
        if "show_pipe_logs" in g_data:
            cfg.graph.show_pipe_logs = bool(g_data["show_pipe_logs"])
        elif "show_tube_logs" in g_data:
            cfg.graph.show_pipe_logs = bool(g_data["show_tube_logs"])

        if "pipe_logs_text" in g_data:
            cfg.graph.pipe_logs_text = str(g_data["pipe_logs_text"])
        elif "tube_logs_text" in g_data:
            cfg.graph.pipe_logs_text = str(g_data["tube_logs_text"])
        if "plot_temperature" in g_data:
            cfg.graph.plot_temperature = bool(g_data["plot_temperature"])
        if "wika_nr_list" in g_data and isinstance(g_data["wika_nr_list"], list):
            cfg.graph.wika_nr_list = [str(x) for x in g_data["wika_nr_list"]]
        if "wika_nr_active" in g_data:
            cfg.graph.wika_nr_active = str(g_data["wika_nr_active"])
            
        if "default_test_pressure" in g_data:
            cfg.graph.default_test_pressure = str(g_data["default_test_pressure"])
        if "default_system" in g_data:
            cfg.graph.default_system = str(g_data["default_system"])
        if "default_log_no" in g_data:
            cfg.graph.default_log_no = str(g_data["default_log_no"])
        if "default_ins_no" in g_data:
            cfg.graph.default_ins_no = str(g_data["default_ins_no"])
        if "default_project" in g_data:
            cfg.graph.default_project = str(g_data["default_project"])
        if "default_note" in g_data:
            cfg.graph.default_note = str(g_data["default_note"])


    # Analysis settings
    if "analysis" in data and isinstance(data["analysis"], dict):
        a_data = data["analysis"]
        if a_data.get("test_pressure_bar") is not None:
            cfg.analysis.test_pressure_bar = float(a_data["test_pressure_bar"])
        if a_data.get("lower_limit_bar") is not None:
            cfg.analysis.lower_limit_bar = float(a_data["lower_limit_bar"])
        if a_data.get("upper_limit_bar") is not None:
            cfg.analysis.upper_limit_bar = float(a_data["upper_limit_bar"])
        if a_data.get("hold_start_time_minutes") is not None:
            cfg.analysis.hold_start_time_minutes = float(a_data["hold_start_time_minutes"])
        if a_data.get("hold_end_time_minutes") is not None:
            cfg.analysis.hold_end_time_minutes = float(a_data["hold_end_time_minutes"])
        if a_data.get("allowed_drop_bar") is not None:
            cfg.analysis.allowed_drop_bar = float(a_data["allowed_drop_bar"])
        if "create_pass_fail_result" in a_data:
            cfg.analysis.create_pass_fail_result = bool(a_data["create_pass_fail_result"])

    return cfg
