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

  created_at: string;
  updated_at: string;
  items: RecordItem[];
}
