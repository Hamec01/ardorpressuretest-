import React, { useState } from 'react';
import { X, Upload, Check, AlertCircle, FolderArchive, FileSpreadsheet, FolderUp } from 'lucide-react';
import { PressureTest } from '../types';

interface NewTestModalProps {
  onClose: () => void;
  onSuccess: (createdTest: PressureTest) => void;
}

export const NewTestModal: React.FC<NewTestModalProps> = ({ onClose, onSuccess }) => {
  const [uploadMode, setUploadMode] = useState<'package' | 'form'>('package');

  // Package Mode State
  const [packageFile, setPackageFile] = useState<File | null>(null);
  const [folderFiles, setFolderFiles] = useState<File[]>([]);

  // Form Mode State
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [logNo, setLogNo] = useState<string>('');
  const [testPressure, setTestPressure] = useState<string>('15 bar');
  const [system, setSystem] = useState<string>('');
  const [insNo, setInsNo] = useState<string>('');
  const [project, setProject] = useState<string>('ARDOR');
  const [operator, setOperator] = useState<string>('');
  const [wikaNr, setWikaNr] = useState<string>('BG516-GDTZ-13-D');
  const [note, setNote] = useState<string>('');
  const [pipeRaw, setPipeRaw] = useState<string>('');
  const [pipePhotos, setPipePhotos] = useState<File[]>([]);
  const [gaugePhotos, setGaugePhotos] = useState<File[]>([]);
  
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handlePackageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setPackageFile(e.target.files[0]);
      setFolderFiles([]);
    }
  };

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFolderFiles(Array.from(e.target.files));
      setPackageFile(null);
    }
  };

  const handlePackageSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!packageFile && folderFiles.length === 0) {
      setErrorMsg('Пожалуйста, выберите ZIP-архив или папку с файлами лога.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const formData = new FormData();
      if (packageFile) {
        formData.append('package_file', packageFile);
      }
      for (const f of folderFiles) {
        formData.append('files', f, (f as any).webkitRelativePath || f.name);
      }

      const res = await fetch('/api/v1/process/package', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Ошибка обработки пакета (${res.status})`);
      }

      const createdList: PressureTest[] = await res.json();
      if (createdList && createdList.length > 0) {
        onSuccess(createdList[0]);
      } else {
        onClose();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Произошла ошибка при загрузке архива / папки.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCsvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setCsvFile(file);
      if (!logNo) {
        setLogNo(file.name.replace(/\.csv$/i, ''));
      }
    }
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      setErrorMsg('Пожалуйста, выберите CSV-файл с измерениями.');
      return;
    }
    if (!logNo.trim()) {
      setErrorMsg('Log Number обязателен для заполнения.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const formData = new FormData();
      formData.append('csv_file', csvFile);
      formData.append('log_no', logNo.trim());
      formData.append('test_pressure', testPressure.trim());
      formData.append('system', system.trim());
      formData.append('ins_no', insNo.trim());
      formData.append('project', project.trim());
      formData.append('operator', operator.trim());
      formData.append('wika_nr', wikaNr.trim());
      formData.append('note', note.trim());
      // Extract bundle numbers from pipe lines formatted as "Bundle/Pipe" (e.g. 122153/41)
      const extractedBundles = pipeRaw
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.includes('/'))
        .map(line => line.split('/')[0].trim())
        .filter(Boolean);
      const autoBundles = Array.from(new Set(extractedBundles)).join('\n');

      formData.append('pipe_numbers_raw', pipeRaw);
      formData.append('bundle_numbers_raw', autoBundles);
      formData.append('create_pdf', 'true');

      for (const pf of pipePhotos) {
        formData.append('pipe_photos', pf);
      }
      for (const gf of gaugePhotos) {
        formData.append('gauge_photos', gf);
      }

      const res = await fetch('/api/v1/process', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Processing failed with status ${res.status}`);
      }

      const created: PressureTest = await res.json();
      onSuccess(created);
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during CSV processing.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '800px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div className="brand-logo-icon" style={{ width: '32px', height: '32px', fontSize: '1rem' }}>+</div>
            <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>Upload & Process Test Log (Загрузка лога)</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} disabled={isSubmitting}>
            <X size={20} />
          </button>
        </div>

        {/* Mode Selector Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', padding: '0 1.5rem', background: 'rgba(15, 23, 42, 0.4)' }}>
          <button
            type="button"
            onClick={() => setUploadMode('package')}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: uploadMode === 'package' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              color: uploadMode === 'package' ? 'var(--text-primary)' : 'var(--text-muted)',
              padding: '0.75rem 1rem',
              fontWeight: 600,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <FolderArchive size={16} color={uploadMode === 'package' ? 'var(--accent-cyan)' : 'inherit'} />
            <span>📦 Upload ZIP or Folder (Архив / Папка)</span>
          </button>

          <button
            type="button"
            onClick={() => setUploadMode('form')}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: uploadMode === 'form' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              color: uploadMode === 'form' ? 'var(--text-primary)' : 'var(--text-muted)',
              padding: '0.75rem 1rem',
              fontWeight: 600,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <FileSpreadsheet size={16} color={uploadMode === 'form' ? 'var(--accent-cyan)' : 'inherit'} />
            <span>📄 Single CSV + Metadata Form</span>
          </button>
        </div>

        {/* Error message */}
        {errorMsg && (
          <div style={{ margin: '1rem 1.5rem 0', background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
            <AlertCircle size={18} color="var(--accent-rose)" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Mode 1: Package / ZIP / Folder Upload */}
        {uploadMode === 'package' ? (
          <form onSubmit={handlePackageSubmit} className="modal-body" style={{ gap: '1.25rem' }}>
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-color)', textAlign: 'center' }}>
              <FolderUp size={44} color="var(--accent-cyan)" style={{ marginBottom: '0.75rem', opacity: 0.8 }} />
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.4rem' }}>
                Загрузите ZIP-архив с логом или выберите целую папку
              </h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto 1.25rem', lineHeight: 1.5 }}>
                Сервер автоматически извлечёт <strong>CSV-файл</strong>, прикреплённые фото и манифест, построит графики давления 0–160 bar, рассчитает выдержку и зарегистрирует ревизию в базе данных.
              </p>

              <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                {/* ZIP Picker */}
                <label className="btn-primary" style={{ cursor: 'pointer', fontSize: '0.9rem', padding: '0.6rem 1.2rem' }}>
                  <FolderArchive size={16} />
                  <span>Выбрать ZIP-архив (.zip)</span>
                  <input type="file" accept=".zip" onChange={handlePackageFileChange} style={{ display: 'none' }} />
                </label>

                {/* Folder Picker */}
                <label className="filter-pill" style={{ cursor: 'pointer', fontSize: '0.9rem', padding: '0.6rem 1.2rem', display: 'flex', alignItems: 'center', gap: '0.4rem', border: '1px solid var(--border-color)' }}>
                  <FolderUp size={16} />
                  <span>Выбрать папку целиком</span>
                  {/* @ts-ignore */}
                  <input type="file" webkitdirectory="" directory="" multiple onChange={handleFolderChange} style={{ display: 'none' }} />
                </label>
              </div>

              {/* Selection Status */}
              <div style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
                {packageFile && (
                  <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>
                    Выбран ZIP: {packageFile.name} ({(packageFile.size / 1024).toFixed(1)} KB)
                  </span>
                )}
                {folderFiles.length > 0 && (
                  <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    Выбрана папка: {folderFiles.length} файлов подготовлено к отправке
                  </span>
                )}
                {!packageFile && folderFiles.length === 0 && (
                  <span style={{ color: 'var(--text-muted)' }}>Файл или папка ещё не выбраны</span>
                )}
              </div>
            </div>

            {/* Footer */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }} disabled={isSubmitting}>
                Отмена
              </button>
              <button type="submit" className="btn-primary" disabled={isSubmitting || (!packageFile && folderFiles.length === 0)}>
                {isSubmitting ? (
                  <>
                    <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    <span>Распаковка и обработка пакета...</span>
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    <span>Загрузить и обработать пакет</span>
                  </>
                )}
              </button>
            </div>
          </form>
        ) : (
          /* Mode 2: Standard CSV Form */
          <form onSubmit={handleFormSubmit} className="modal-body" style={{ gap: '1.25rem' }}>
            {/* Section 1: CSV Upload */}
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
                1. WIKA CPG1500 CSV File *
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <label className="btn-primary" style={{ cursor: 'pointer', fontSize: '0.85rem', padding: '0.5rem 1rem' }}>
                  <Upload size={16} />
                  <span>Choose CSV File...</span>
                  <input type="file" accept=".csv" onChange={handleCsvChange} style={{ display: 'none' }} />
                </label>
                <span style={{ fontSize: '0.85rem', color: csvFile ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                  {csvFile ? `Selected: ${csvFile.name} (${(csvFile.size / 1024).toFixed(1)} KB)` : 'No file selected yet'}
                </span>
              </div>
            </div>

            {/* Section 2: Metadata */}
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--accent-cyan)' }}>
                2. Test Metadata
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Log No. *</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. 014FED"
                    value={logNo}
                    onChange={(e) => setLogNo(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Test Pressure</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. 15 bar"
                    value={testPressure}
                    onChange={(e) => setTestPressure(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>System / Line</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. Fuel Gas System"
                    value={system}
                    onChange={(e) => setSystem(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Operator Name</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. Matti Meikäläinen"
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Inspection No.</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. INS-2026-001"
                    value={insNo}
                    onChange={(e) => setInsNo(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Project</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. ARDOR Pipeline"
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>WIKA Gauge Serial</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    value={wikaNr}
                    onChange={(e) => setWikaNr(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Notes / Remarks</label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                    placeholder="e.g. Ambient 21C"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Section 3: Pipe Logs & Bundles */}
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                  3. Pipe Logs (Номера связок и труб)
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 500 }}>
                  Формат: Сначала Bundle, затем Pipe (Bundle/Pipe)
                </span>
              </div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Вводите по одному номеру на строку. В начале пишется номер бандла (Bundle), затем через слеш номер трубы (Pipe):
              </label>
              <textarea
                className="search-input"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.75rem', fontSize: '0.9rem', height: '95px', resize: 'vertical', fontFamily: 'Consolas, monospace', lineHeight: 1.4 }}
                placeholder="122153/41&#10;122153/21&#10;122153/25"
                value={pipeRaw}
                onChange={(e) => setPipeRaw(e.target.value)}
              />
            </div>

            {/* Section 4: Photo Attachments */}
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
                4. Evidence Photos
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Pipe Photos ({pipePhotos.length} selected)
                  </label>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={(e) => e.target.files && setPipePhotos(Array.from(e.target.files))}
                    style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Gauge Photos ({gaugePhotos.length} selected)
                  </label>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={(e) => e.target.files && setGaugePhotos(Array.from(e.target.files))}
                    style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
                  />
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={onClose}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
                disabled={isSubmitting}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    <span>Processing CSV & Generating Artifacts...</span>
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    <span>Process Test & Create Revision</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
