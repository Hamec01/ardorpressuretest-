export interface Artifact {
  name: string;
  relative_path: string;
  file_type: 'source_csv' | 'graph_png' | 'excel_xlsx' | 'text_txt' | 'report_pdf' | 'photo';
  category?: 'pipe' | 'gauge' | 'installation' | 'other' | null;
  size_bytes: number;
  sha256: string;
}

export interface TestRevision {
  id: string;
  revision_id: string;
  status: 'draft' | 'complete' | 'confirmed' | 'archived';
  is_primary: boolean;
  operator: string;
  metadata_json: {
    test_pressure?: string;
    system?: string;
    ins_no?: string;
    project?: string;
    note?: string;
    wika_nr?: string;
    bundle_numbers?: string[];
    pipe_numbers?: string[];
    custom_date?: string;
  };
  metrics_json: {
    start_time?: string | null;
    end_time?: string | null;
    duration_formatted?: string;
    min_pressure_bar?: number;
    max_pressure_bar?: number;
    mean_pressure_bar?: number;
    total_delta_bar?: number;
    evaluation_status?: string;
  };
  artifacts: Artifact[];
  created_at: string;
}

export interface PressureTest {
  id: string;
  log_no: string;
  created_at: string;
  updated_at: string;
  revisions: TestRevision[];
}
