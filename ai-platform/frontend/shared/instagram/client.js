const API_BASE = '/api/v1';

async function parseJsonSafe(response) {
  const raw = await response.text();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return { detail: raw.slice(0, 220) };
  }
}

export async function startInstagramConnect({ token, returnTo }) {
  const res = await fetch(`${API_BASE}/instagram/connect/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ return_to: returnTo || window.location.origin }),
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) throw new Error(data.detail || `Instagram connect failed (${res.status})`);
  return data;
}

export async function getInstagramConnectStatus({ token }) {
  const res = await fetch(`${API_BASE}/instagram/connect/status`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) throw new Error(data.detail || `Instagram status failed (${res.status})`);
  return data;
}

export async function disconnectInstagramConnect({ token }) {
  const res = await fetch(`${API_BASE}/instagram/connect/disconnect`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) throw new Error(data.detail || `Instagram disconnect failed (${res.status})`);
  return data;
}

export async function openInstagramConnectPopup({ token, returnTo, timeoutMs = 120000 }) {
  const start = await startInstagramConnect({ token, returnTo });

  const width = 520;
  const height = 700;
  const left = Math.max(0, window.screenX + (window.outerWidth - width) / 2);
  const top = Math.max(0, window.screenY + (window.outerHeight - height) / 2);
  const popup = window.open(
    start.auth_url,
    'fixme_instagram_connect',
    `width=${width},height=${height},left=${Math.round(left)},top=${Math.round(top)},resizable=yes,scrollbars=yes`
  );

  if (!popup) {
    throw new Error('Popup blocked. Please allow popups and try again.');
  }

  return await new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      try { popup.close(); } catch {}
      reject(new Error('Instagram connect timed out. Please try again.'));
    }, timeoutMs);

    const poll = window.setInterval(() => {
      if (popup.closed) {
        cleanup();
        reject(new Error('Instagram connect window was closed before completion.'));
      }
    }, 500);

    function cleanup() {
      window.clearTimeout(timer);
      window.clearInterval(poll);
      window.removeEventListener('message', onMessage);
    }

    function onMessage(event) {
      const data = event?.data;
      if (!data || data.source !== 'fixmeapp-instagram-connect') return;
      cleanup();
      try { popup.close(); } catch {}

      if (!data.ok) {
        reject(new Error(data.error || 'Instagram connection failed.'));
        return;
      }

      resolve(data.payload || {});
    }

    window.addEventListener('message', onMessage);
  });
}
