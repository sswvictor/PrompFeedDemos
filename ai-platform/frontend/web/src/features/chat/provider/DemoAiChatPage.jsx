import { useEffect, useState } from 'react';
import { getDemoProviderLock, sendProviderChatMessage } from '../../../api/bookingApi';
import ProviderTabBar from '../../../personas/provider/navigation/ProviderTabBar';

function MessageBubble({ role, text }) {
  const mine = role === 'user';
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          mine
            ? 'bg-fixme-accent text-fixme-bg'
            : 'bg-fixme-card border border-fixme-border text-fixme-text-primary'
        }`}
      >
        {text}
      </div>
    </div>
  );
}

export default function DemoAiChat() {
  const [providerId, setProviderId] = useState('');
  const [providerName, setProviderName] = useState('');
  const [providerEmail, setProviderEmail] = useState('');
  const [resolvingProvider, setResolvingProvider] = useState(true);
  const [providerError, setProviderError] = useState('');

  const [threadId] = useState(() => {
    const existing = sessionStorage.getItem('fixme_demo_session_id');
    if (existing) return existing;
    const newId = `demo_${Date.now()}`;
    sessionStorage.setItem('fixme_demo_session_id', newId);
    return newId;
  });
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function resolveProvider() {
      setResolvingProvider(true);
      setProviderError('');

      try {
        const params = new URLSearchParams(window.location.search);
        const queryProviderId = params.get('provider_id') || params.get('provider');
        const storedProviderId = localStorage.getItem('fixme_provider_id');
        const fallbackProviderId = queryProviderId || storedProviderId;

        if (fallbackProviderId) {
          const fallbackProviderName =
            params.get('provider_name') ||
            localStorage.getItem('fixme_provider_name') ||
            'Provider';
          const fallbackProviderEmail = localStorage.getItem('fixme_provider_email') || '';

          setProviderId(fallbackProviderId);
          setProviderName(fallbackProviderName);
          setProviderEmail(fallbackProviderEmail);
          localStorage.setItem('fixme_provider_id', fallbackProviderId);

          setMessages([
            {
              role: 'assistant',
              text:
                `Hi! I'm the booking assistant for ${fallbackProviderName}. ` +
                'Tell me what service you want and when you would like to come in.',
            },
          ]);
          return;
        }

        const lock = await getDemoProviderLock();
        setProviderId(lock.provider_id);
        setProviderName(lock.provider_name || 'Provider');
        setProviderEmail(lock.provider_email || '');

        localStorage.setItem('fixme_provider_id', lock.provider_id);
        if (lock.provider_name) localStorage.setItem('fixme_provider_name', lock.provider_name);
        if (lock.slug) localStorage.setItem('fixme_provider_slug', lock.slug);
        if (lock.provider_email) localStorage.setItem('fixme_provider_email', lock.provider_email);

        setMessages([
          {
            role: 'assistant',
            text:
              `Hi! I'm the booking assistant for ${lock.provider_name || 'your salon'}. ` +
              'Tell me what service you want and when you would like to come in.',
          },
        ]);
      } catch (e) {
        setProviderError(e.message || 'Could not load the booking assistant. Please try again.');
      } finally {
        setResolvingProvider(false);
      }
    }

    resolveProvider();
  }, []);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;

    if (!providerId) {
      setError('Booking assistant not available yet. Please try again shortly.');
      return;
    }

    setError('');
    setSending(true);
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setInput('');

    try {
      const result = await sendProviderChatMessage({
        providerId,
        threadId,
        message: text,
      });
      setMessages((prev) => [...prev, { role: 'assistant', text: result.reply || "Got it! I'll take care of that for you." }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', text: "Sorry, I'm having a small technical issue. Please try again in a moment." }]);
      setError(err.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  }

  function handleInputKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sending) {
        handleSend(e);
      }
    }
  }

  return (
    <div className="min-h-screen bg-fixme-bg text-fixme-text-primary px-4 py-6 pb-24">
      <div className="max-w-2xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-fixme-text-primary">
              {resolvingProvider ? 'Fixmeapp' : providerId ? providerName : 'Fixmeapp'}
            </h1>
            <p className="text-xs text-fixme-text-muted">
              {resolvingProvider
                ? 'Loading...'
                : providerId
                  ? 'AI booking assistant'
                  : 'Booking assistant unavailable'}
            </p>
          </div>
          <div className="w-8 h-8 rounded-full bg-fixme-accent flex items-center justify-center text-fixme-bg text-xs font-bold">
            AI
          </div>
        </div>

        {providerError && (
          <div className="bg-fixme-card border border-fixme-border rounded-2xl p-4 text-sm text-fixme-text-secondary">
            <p>The booking assistant is being set up. Please check back in a moment.</p>
          </div>
        )}

        <div className="bg-fixme-bg border border-fixme-border rounded-2xl p-4 min-h-[60vh] max-h-[70vh] overflow-y-auto space-y-3">
          {messages.length === 0 && (
            <p className="text-sm text-fixme-text-secondary">
              Message us to book an appointment.
            </p>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={`${m.role}-${i}`} role={m.role} text={m.text} />
          ))}
        </div>

        <form onSubmit={handleSend} className="space-y-2">
          <textarea
            className="w-full bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3 text-sm min-h-[92px]"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Type a message..."
          />
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-red-400">{error}</span>
            <button
              type="submit"
              disabled={sending || resolvingProvider || !providerId}
              className="rounded-xl px-5 py-2.5 text-sm font-medium bg-fixme-accent text-fixme-bg disabled:opacity-60"
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>
      <ProviderTabBar active="home" />
    </div>
  );
}

