export interface Artifact {
  id?: string;
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
  pipecloud_added: boolean;
  pipecloud_updated_at?: string | null;
  pipecloud_updated_by_name?: string | null;
  is_archived?: boolean;
  created_at: string;
  updated_at: string;
  revisions: TestRevision[];
}

export interface RecordItem {
  id?: string;
  item_no: number;
  pipe_number: string;
  drawing_no?: string | null;
  spool_no?: string | null;
  log_no?: string | null;
  hold_start_bar?: string | null;
  hold_end_bar?: string | null;
  result: 'PASS' | 'FAIL' | 'PENDING';
  notes?: string | null;
}

export interface RecordLogArtifact {
  id?: string;
  artifact_id?: string | null;
  source: 'log_artifact' | 'ptr_upload' | 'generated_from_csv';
  category: 'gauge' | 'pipe' | 'installation' | 'measurement_table' | 'other';
  name: string;
  storage_key?: string;
  sha256?: string;
  position: number;
  is_included_in_pdf: boolean;
  created_at?: string;
}

export interface RecordLog {
  id?: string;
  pressure_test_id: string;
  test_revision_id: string;
  log_no?: string;
  position: number;
  include_measurement_table: boolean;
  selected_pipe_numbers: string[];
  metadata_snapshot?: Record<string, any>;
  artifacts?: RecordLogArtifact[];
  created_at?: string;
}

export interface PressureTestRecord {
  id: string;
  record_number: string;
  project: string;
  system: string;
  ins_no?: string | null;
  test_date?: string | null;
  test_medium: string;
  design_pressure?: string | null;
  test_pressure?: string | null;
  duration_min: string;
  status: 'draft' | 'complete' | 'confirmed' | 'signed';
  foreman_name?: string | null;
  qc_inspector?: string | null;
  client_surveyor?: string | null;
  notes?: string | null;
  
  // Verification & Signatures
  verification_code?: string | null;
  confirmed_by_name?: string | null;
  confirmed_by_role?: string | null;
  confirmed_at?: string | null;
  signature_image_path?: string | null;
  signed_copy_path?: string | null;
  sha256_hash?: string | null;
  official_pdf_sha256?: string | null;
  full_pdf_sha256?: string | null;
  snapshot_json?: Record<string, any>;

  created_at: string;
  updated_at: string;
  items: RecordItem[];
  logs?: RecordLog[];
}
