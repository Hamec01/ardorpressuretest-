import React, { useRef, useState, useEffect } from 'react';
import { X, Check, RotateCcw, PenTool, Upload, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { PressureTestRecord } from '../types';

interface SignatureModalProps {
  record: PressureTestRecord;
  onClose: () => void;
  onSuccess: (updated: PressureTestRecord) => void;
}

export const SignatureModal: React.FC<SignatureModalProps> = ({ record, onClose, onSuccess }) => {
  const { token } = useAuth();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [hasDrawn, setHasDrawn] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0F172A'; // dark ink
  }, []);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    setIsDrawing(true);
    setHasDrawn(true);
    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawn(false);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        setHasDrawn(true);
      };
      img.src = event.target?.result as string;
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    if (!hasDrawn) {
      setErrorMsg('Please draw or upload your signature before saving.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);
      const canvas = canvasRef.current;
      if (!canvas) return;
      const dataUrl = canvas.toDataURL('image/png');

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/v1/records/${record.id}/signature`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ image_base64: dataUrl })
      });

      if (!res.ok) {
        throw new Error('Failed to save signature.');
      }

      const updated = await res.json();
      onSuccess(updated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Error uploading signature.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '520px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <PenTool size={20} color="var(--accent-cyan)" />
            <span style={{ fontSize: '1.2rem', fontWeight: 700 }}>Foreman Digital Signature</span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ gap: '1rem' }}>
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: 'var(--error-text)', padding: '0.75rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <AlertCircle size={16} color="var(--accent-rose)" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Sign below using your stylus or mouse. Your signature will be embedded into the official ARDOR Pressure Test Record: <strong>{record.record_number}</strong>.
          </div>

          {/* Canvas Box */}
          <div style={{ background: '#FFFFFF', borderRadius: 'var(--radius-md)', padding: '0.5rem', border: '2px dashed #94A3B8', display: 'flex', justifyContent: 'center' }}>
            <canvas
              ref={canvasRef}
              width={460}
              height={180}
              style={{ width: '100%', height: '180px', touchAction: 'none', cursor: 'crosshair' }}
              onMouseDown={startDrawing}
              onMouseMove={draw}
              onMouseUp={stopDrawing}
              onMouseLeave={stopDrawing}
              onTouchStart={startDrawing}
              onTouchMove={draw}
              onTouchEnd={stopDrawing}
            />
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={clearCanvas}
                className="filter-pill"
                style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}
              >
                <RotateCcw size={13} />
                <span>Clear</span>
              </button>

              <label className="filter-pill" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                <Upload size={13} />
                <span>Upload PNG</span>
                <input type="file" accept="image/png,image/jpeg" onChange={handleFileUpload} style={{ display: 'none' }} />
              </label>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.5rem 1rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: '0.85rem' }}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={handleSave} disabled={isSubmitting} style={{ fontSize: '0.85rem' }}>
                <Check size={15} />
                <span>{isSubmitting ? 'Saving...' : 'Apply Signature'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
