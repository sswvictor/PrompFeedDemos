import { useEffect, useRef, useState } from 'react';

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const SCAN_ENDPOINT = '/api/v1/onboarding/scan-price-list';

let scanItemId = 0;
function nextScanItemId() {
  scanItemId += 1;
  return scanItemId;
}

function mergeServicesFromItems(items) {
  const byName = new Map();
  for (const item of items) {
    if (item.status !== 'done') continue;
    for (const service of item.services || []) {
      const key = String(service?.name || '').trim().toLowerCase();
      if (!key) continue;
      byName.set(key, service);
    }
  }
  return Array.from(byName.values());
}

function parseErrorText(raw, fallback) {
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    return parsed?.detail || fallback;
  } catch {
    return raw.slice(0, 200) || fallback;
  }
}

async function fileToDataUrl(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (event) => resolve(String(event.target?.result || ''));
    reader.readAsDataURL(file);
  });
}

async function scanPriceListFile(file, authToken) {
  const body = new FormData();
  body.append('file', file);

  const res = await fetch(SCAN_ENDPOINT, {
    method: 'POST',
    headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    body,
  });

  if (res.status === 401 || res.status === 403) {
    return {
      ok: false,
      error: 'Auth error - try logging in again.',
      services: [],
    };
  }

  if (!res.ok) {
    const raw = await res.text();
    return {
      ok: false,
      error: parseErrorText(raw, 'Could not read this image. Try a clearer photo.'),
      services: [],
    };
  }

  const data = await res.json().catch(() => ({}));
  return {
    ok: true,
    error: '',
    services: Array.isArray(data.services) ? data.services : [],
  };
}

export default function PricelistUpload({
  authToken,
  onServicesChange,
  onScanError,
  onBusyChange,
  multiple = true,
  ui = 'full',
  title = 'Scan your price list',
  description = 'Upload one or more photos - our AI reads all your services and prices automatically.',
  helperText = 'Got multiple pages or menus? Add them all at once. Optional - skip to add services manually later.',
  scanButtonLabel = 'Upload screenshot',
  scanButtonBusyLabel = 'Scanning...',
}) {
  const [items, setItems] = useState([]);
  const [buttonBusy, setButtonBusy] = useState(false);
  const fileRef = useRef(null);

  const anyScanning = items.some((item) => item.status === 'scanning');

  useEffect(() => {
    const isBusy = ui === 'button' ? buttonBusy : anyScanning;
    onBusyChange?.(isBusy);
  }, [buttonBusy, anyScanning, onBusyChange, ui]);

  useEffect(() => {
    if (ui !== 'full') return;
    const merged = mergeServicesFromItems(items);
    onServicesChange?.(merged);
  }, [items, onServicesChange, ui]);

  const addFilesFull = async (fileList) => {
    const validFiles = Array.from(fileList || []).filter((file) => file.size <= MAX_FILE_BYTES);
    if (validFiles.length === 0) return;

    const newItems = await Promise.all(
      validFiles.map(async (file) => ({
        id: nextScanItemId(),
        file,
        previewUrl: await fileToDataUrl(file),
        status: 'idle',
        services: [],
        errorMsg: '',
      })),
    );

    setItems((prev) => [...prev, ...newItems]);

    for (const item of newItems) {
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: 'scanning', errorMsg: '' } : it)));
      const result = await scanPriceListFile(item.file, authToken);
      if (result.ok) {
        setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: 'done', services: result.services } : it)));
      } else {
        setItems((prev) => prev.map((it) => (
          it.id === item.id
            ? { ...it, status: 'error', services: [], errorMsg: result.error || 'Could not read this image. Try a clearer photo.' }
            : it
        )));
      }
    }
  };

  const retryItem = async (item) => {
    setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: 'scanning', errorMsg: '' } : it)));
    const result = await scanPriceListFile(item.file, authToken);
    if (result.ok) {
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: 'done', services: result.services } : it)));
      return;
    }
    setItems((prev) => prev.map((it) => (
      it.id === item.id
        ? { ...it, status: 'error', services: [], errorMsg: result.error || 'Could not read this image. Try a clearer photo.' }
        : it
    )));
  };

  const addFilesButton = async (fileList) => {
    const validFiles = Array.from(fileList || []).filter((file) => file.size <= MAX_FILE_BYTES);
    if (validFiles.length === 0) {
      onScanError?.('No valid file selected (max 10 MB).');
      return;
    }

    setButtonBusy(true);
    const scanResults = [];
    let firstError = '';

    for (const file of validFiles) {
      const result = await scanPriceListFile(file, authToken);
      if (result.ok) {
        scanResults.push({ status: 'done', services: result.services });
      } else {
        if (!firstError) firstError = result.error;
        scanResults.push({ status: 'error', services: [] });
      }
    }

    const merged = mergeServicesFromItems(scanResults);
    if (merged.length > 0) {
      onServicesChange?.(merged);
    } else {
      onScanError?.(firstError || 'No services found in screenshot.');
    }

    setButtonBusy(false);
  };

  if (ui === 'button') {
    return (
      <>
        <input
          ref={fileRef}
          type="file"
          accept="image/*,.heic,.heif,.png,.jpg,.jpeg,.webp"
          className="hidden"
          multiple={multiple}
          onChange={(event) => {
            addFilesButton(event.target.files);
            event.target.value = '';
          }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={buttonBusy}
          className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary text-xs font-semibold hover:text-fixme-text-primary hover:border-fixme-accent/40 transition-colors disabled:opacity-50"
        >
          {buttonBusy ? scanButtonBusyLabel : scanButtonLabel}
        </button>
      </>
    );
  }

  const allDone = items.length > 0 && items.every((item) => item.status === 'done' || item.status === 'error');
  const mergedServices = mergeServicesFromItems(items);

  return (
    <div>
      <h2 className="text-fixme-text-primary text-2xl font-bold mb-2">{title}</h2>
      <p className="text-fixme-text-secondary text-sm mb-1 leading-relaxed">{description}</p>
      <p className="text-fixme-text-muted text-xs mb-5">{helperText}</p>

      <button
        onClick={() => fileRef.current?.click()}
        className="w-full border-2 border-dashed border-fixme-border rounded-2xl p-6 flex flex-col items-center gap-2 hover:border-fixme-accent transition-colors group mb-4"
      >
        <span className="text-fixme-text-primary font-semibold text-sm group-hover:text-fixme-accent transition-colors">
          {items.length === 0 ? 'Upload price list photos' : 'Add more photos'}
        </span>
        <span className="text-fixme-text-muted text-xs">JPG, PNG or HEIC - up to 10 MB each - select multiple at once</span>
      </button>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple={multiple}
        className="hidden"
        onChange={(event) => {
          addFilesFull(event.target.files);
          event.target.value = '';
        }}
      />

      {items.length > 0 && (
        <div className="flex flex-col gap-2 mb-4">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-3 bg-fixme-card border border-fixme-border rounded-xl px-3 py-2">
              <div className="w-14 h-14 rounded-lg overflow-hidden bg-fixme-bg flex-shrink-0 relative">
                <img src={item.previewUrl} alt="" className="w-full h-full object-cover" />
                {item.status === 'scanning' && (
                  <div className="absolute inset-0 bg-fixme-bg/70 flex items-center justify-center">
                    <div className="w-5 h-5 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
                {item.status === 'done' && (
                  <div className="absolute bottom-0.5 right-0.5 w-5 h-5 bg-fixme-accent rounded-full flex items-center justify-center">
                    <svg className="w-3 h-3" viewBox="0 0 10 8" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="1,4 3.5,6.5 9,1" />
                    </svg>
                  </div>
                )}
                {item.status === 'error' && (
                  <div className="absolute bottom-0.5 right-0.5 w-5 h-5 bg-fixme-error rounded-full flex items-center justify-center">
                    <span className="text-white text-xs font-bold leading-none">!</span>
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                {item.status === 'scanning' && <p className="text-fixme-text-muted text-xs">Reading...</p>}
                {item.status === 'done' && (
                  <p className="text-fixme-text-secondary text-xs">
                    Found <span className="text-fixme-text-primary font-semibold">{item.services.length}</span> service{item.services.length !== 1 ? 's' : ''}
                  </p>
                )}
                {item.status === 'error' && (
                  <>
                    <p className="text-fixme-error text-xs">{item.errorMsg}</p>
                    <button onClick={() => retryItem(item)} className="text-fixme-accent text-xs underline mt-0.5">Retry</button>
                  </>
                )}
              </div>

              <button
                onClick={() => setItems((prev) => prev.filter((it) => it.id !== item.id))}
                className="text-fixme-text-muted text-lg leading-none hover:text-fixme-text-secondary px-1 flex-shrink-0"
                aria-label="Remove image"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      {allDone && mergedServices.length > 0 && (
        <div className="mt-2">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-fixme-success text-base">ok</span>
            <span className="text-fixme-text-primary font-semibold text-sm">
              {mergedServices.length} unique service{mergedServices.length !== 1 ? 's' : ''} found across {items.filter((i) => i.status === 'done').length} image{items.filter((i) => i.status === 'done').length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {mergedServices.map((service, index) => (
              <div key={index} className="bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 flex justify-between items-center">
                <div>
                  <p className="text-fixme-text-primary font-semibold text-sm">{service.name}</p>
                  <p className="text-fixme-text-muted text-xs mt-0.5">{service.duration_minutes} min</p>
                </div>
                <span className="text-fixme-accent font-bold text-sm">{service.price_inc_vat} kr</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {anyScanning && items.length > 0 && (
        <p className="text-fixme-text-muted text-xs text-center mt-3">
          Scanning {items.filter((i) => i.status === 'scanning').length} image{items.filter((i) => i.status === 'scanning').length !== 1 ? 's' : ''}...
        </p>
      )}
    </div>
  );
}
