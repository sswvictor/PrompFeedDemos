/**
 * CalendarCallbackPage — /provider/calendar/callback
 *
 * Google OAuth redirects the browser here after the provider approves access.
 * URL will contain ?code=...&state=...  (or ?error=access_denied on cancel).
 *
 * This page:
 *   1. Reads ?code & ?state from the URL
 *   2. POSTs to /api/v1/provider/calendar/google/callback to exchange the code
 *   3. Shows success / error state
 *   4. Redirects to /provider/settings#calendar after a short delay
 */

import { useEffect, useState } from 'react';

const API_BASE = '/api/v1';
const SETTINGS_URL = '/provider/settings';

function getToken() {
  return localStorage.getItem('fixme_provider_token');
}

export default function CalendarCallbackPage() {
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state');
    const oauthError = params.get('error');

    // Provider cancelled the Google consent screen
    if (oauthError) {
      setErrorMsg(
        oauthError === 'access_denied'
          ? 'You cancelled the Google Calendar connection.'
          : `Google returned an error: ${oauthError}`,
      );
      setStatus('error');
      return;
    }

    if (!code) {
      setErrorMsg('No authorisation code received from Google. Please try again.');
      setStatus('error');
      return;
    }

    const token = getToken();
    if (!token) {
      setErrorMsg('Your session has expired. Please log in again.');
      setStatus('error');
      return;
    }

    // Exchange the code for tokens via our backend
    fetch(`${API_BASE}/provider/calendar/google/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ code, state: state || '', external_calendar_id: 'primary' }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `Server error ${res.status}`);
        }
        return res.json();
      })
      .then(() => {
        setStatus('success');
        // Redirect to settings calendar section after 1.8 s
        setTimeout(() => {
          window.location.replace(SETTINGS_URL);
        }, 1800);
      })
      .catch((err) => {
        setErrorMsg(err.message || 'Failed to connect Google Calendar.');
        setStatus('error');
      });
  }, []);

  return (
    <div className="min-h-screen bg-fixme-bg flex items-center justify-center px-6">
      <div className="w-full max-w-sm text-center space-y-4">
        {status === 'loading' && (
          <>
            <div className="w-12 h-12 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-fixme-text-primary font-semibold text-base">Connecting Google Calendar&hellip;</p>
            <p className="text-fixme-text-muted text-sm">Exchanging credentials with Google</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-14 h-14 rounded-full bg-fixme-accent/15 flex items-center justify-center mx-auto text-3xl">
              {'\u2705'}
            </div>
            <p className="text-fixme-text-primary font-bold text-lg">Google Calendar connected!</p>
            <p className="text-fixme-text-muted text-sm">
              Your bookings will now sync automatically. Redirecting to settings&hellip;
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-14 h-14 rounded-full bg-fixme-error/15 flex items-center justify-center mx-auto text-3xl">
              {'\u274C'}
            </div>
            <p className="text-fixme-text-primary font-bold text-lg">Connection failed</p>
            <p className="text-fixme-text-muted text-sm leading-relaxed">{errorMsg}</p>
            <button
              onClick={() => window.location.replace(SETTINGS_URL)}
              className="mt-4 w-full py-3 rounded-xl bg-fixme-accent text-fixme-bg font-semibold text-sm"
            >
              Back to settings
            </button>
          </>
        )}
      </div>
    </div>
  );
}
