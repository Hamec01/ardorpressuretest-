import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Download, X, ZoomIn, ZoomOut } from 'lucide-react';
import { useI18n } from '../context/LanguageContext';

interface ImageViewerProps {
  url: string;
  title: string;
  onClose: () => void;
}

/**
 * Full-screen image viewer for graphs and photos.
 * Rendered into document.body so it sits above modals and the mobile navigation
 * (a modal's backdrop-filter creates its own stacking context).
 * Tap the image or the zoom button to switch between "fit" and a scrollable 250% view;
 * pinch-zoom stays available on touch devices.
 */
export const ImageViewer: React.FC<ImageViewerProps> = ({ url, title, onClose }) => {
  const { t } = useI18n();
  const [zoomed, setZoomed] = useState<boolean>(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        // Close only the viewer, not the modal underneath.
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [onClose]);

  return createPortal(
    <div className="image-viewer" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="image-viewer-bar" onClick={(event) => event.stopPropagation()}>
        <span className="image-viewer-title">{title}</span>
        <button
          type="button"
          onClick={() => setZoomed((value) => !value)}
          title={zoomed ? t('viewer_fit') : t('viewer_zoom')}
          aria-label={zoomed ? t('viewer_fit') : t('viewer_zoom')}
        >
          {zoomed ? <ZoomOut size={20} /> : <ZoomIn size={20} />}
        </button>
        <a href={url} download title={t('file_download')} aria-label={t('file_download')}>
          <Download size={20} />
        </a>
        <button type="button" onClick={onClose} title={t('modal_close')} aria-label={t('modal_close')}>
          <X size={22} />
        </button>
      </div>
      <div className={`image-viewer-stage${zoomed ? ' zoomed' : ''}`} onClick={(event) => event.stopPropagation()}>
        <img src={url} alt={title} onClick={() => setZoomed((value) => !value)} />
      </div>
    </div>,
    document.body
  );
};
