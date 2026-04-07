import { useEffect, useRef, useState } from 'react';
import { ROUTES } from '../../../app/routeCatalog';

const API = '/api/v1/auth/customer';
const TOTAL_STEPS = 2;

function ProgressBar({ current }) {
  return (
    <div className="flex gap-2 mb-8 max-w-sm mx-auto w-full">
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full transition-all duration-300 ${
            i < current ? 'bg-fixme-accent' : 'bg-fixme-border'
          }`}
        />
      ))}
    </div>
  );
}

function EmailStep({ email, setEmail, setStep, setError, error, setDevCode, isLoginFlow }) {
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    const normalized = email.trim().toLowerCase();
    if (!normalized || !normalized.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalized }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Failed to send code');
      if (data.dev_code) setDevCode(data.dev_code);
      setStep(2);
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg px-4 py-12">
      <div className="flex items-center gap-3 mb-10">
        <button
          onClick={() => {
            window.location.href = ROUTES.customer.welcome;
          }}
          className="text-fixme-text-secondary hover:text-fixme-text-primary transition-colors text-lg"
        >
          {'<-'}
        </button>
        <span className="text-fixme-text-primary font-bold text-xl tracking-tight">Fixmeapp</span>
      </div>

      <ProgressBar current={1} />

      <div className="max-w-sm mx-auto w-full flex-1 flex flex-col">
        <h1 className="text-fixme-text-primary text-2xl font-bold mb-2">
          {isLoginFlow ? 'Log in to your account' : "What's your email?"}
        </h1>
        <p className="text-fixme-text-secondary text-sm mb-8 leading-relaxed">
          {isLoginFlow
            ? 'Enter your email to log in with a 6-digit code.'
            : "We'll send you a 6-digit code to sign in. No password needed."}
        </p>

        <input
          type="email"
          placeholder="sofia@email.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setError('');
          }}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          autoFocus
          className="w-full bg-fixme-card border border-fixme-border rounded-xl px-4 py-3.5 text-fixme-text-primary placeholder-fixme-text-muted text-base focus:outline-none focus:border-fixme-accent transition-colors"
        />

        {error && <p className="text-fixme-error text-sm mt-3">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="mt-6 w-full bg-fixme-accent hover:bg-fixme-accent-light disabled:opacity-50 text-fixme-bg font-bold text-base rounded-xl py-4 transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-fixme-bg border-t-transparent rounded-full animate-spin" />
              Sending code...
            </span>
          ) : isLoginFlow ? (
            'Continue ->'
          ) : (
            'Send code ->'
          )}
        </button>

        <p className="text-fixme-text-muted text-xs text-center mt-4">
          We will never share your email or send spam.
        </p>
      </div>
    </div>
  );
}

function CodeStep({ email, setStep, setError, error, devCode, setDevCode, isLoginFlow }) {
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const inputRefs = useRef([]);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  function handleDigit(index, value) {
    if (!/^\d?$/.test(value)) return;

    const next = [...code];
    next[index] = value;
    setCode(next);
    setError('');

    if (value && index < 5) inputRefs.current[index + 1]?.focus();
    if (value && index === 5) {
      const full = next.join('');
      if (full.length === 6) handleVerify(full);
    }
  }

  function handleKeyDown(index, e) {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handlePaste(e) {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted.length !== 6) return;
    const digits = pasted.split('');
    setCode(digits);
    inputRefs.current[5]?.focus();
    setTimeout(() => handleVerify(pasted), 50);
  }

  async function handleVerify(fullCode) {
    const codeToVerify = fullCode || code.join('');
    if (codeToVerify.length !== 6) {
      setError('Please enter the full 6-digit code');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const normalizedEmail = email.trim().toLowerCase();
      const res = await fetch(`${API}/verify-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, code: codeToVerify }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Invalid code');

      localStorage.setItem('fixme_token', data.access_token);
      localStorage.setItem('fixme_user_id', data.user_id);
      localStorage.setItem('fixme_customer_email', normalizedEmail);
      localStorage.setItem('fixme_customer_show_preference_prompt', '1');

      if (isLoginFlow && data.is_new_user) {
        localStorage.setItem('fixme_customer_show_preference_prompt', '1');
      }

      window.location.href = ROUTES.customer.home;
    } catch (e) {
      setError(e.message || 'Invalid code. Please try again.');
      setCode(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResending(true);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      const res = await fetch(`${API}/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.dev_code) setDevCode(data.dev_code);
      setResent(true);
      setCode(['', '', '', '', '', '']);
      setError('');
      inputRefs.current[0]?.focus();
      setTimeout(() => setResent(false), 3000);
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-fixme-bg px-4 py-12">
      <div className="flex items-center gap-3 mb-10">
        <button
          onClick={() => setStep(1)}
          className="text-fixme-text-secondary hover:text-fixme-text-primary transition-colors text-lg"
        >
          {'<-'}
        </button>
        <span className="text-fixme-text-primary font-bold text-xl tracking-tight">Fixmeapp</span>
      </div>

      <ProgressBar current={2} />

      <div className="max-w-sm mx-auto w-full flex-1 flex flex-col">
        <h1 className="text-fixme-text-primary text-2xl font-bold mb-2">Check your inbox</h1>
        <p className="text-fixme-text-secondary text-sm mb-1 leading-relaxed">We sent a 6-digit code to</p>
        <p className="text-fixme-accent font-semibold text-sm mb-8">{email}</p>

        {devCode && (
          <div className="mb-5 flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-xl px-4 py-2.5">
            <span className="text-yellow-400 text-xs">Dev code:</span>
            <span className="text-yellow-300 font-mono font-bold text-base tracking-widest">{devCode}</span>
          </div>
        )}

        <div className="flex gap-3 justify-center mb-6" onPaste={handlePaste}>
          {code.map((digit, i) => (
            <input
              key={i}
              ref={(el) => {
                inputRefs.current[i] = el;
              }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleDigit(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              className={`w-12 h-14 text-center text-xl font-bold rounded-xl border-2 bg-fixme-card text-fixme-text-primary focus:outline-none transition-all ${
                digit ? 'border-fixme-accent' : 'border-fixme-border focus:border-fixme-accent'
              }`}
            />
          ))}
        </div>

        {error && <p className="text-fixme-error text-sm text-center mb-4">{error}</p>}

        <button
          onClick={() => handleVerify()}
          disabled={loading || code.join('').length !== 6}
          className="w-full bg-fixme-accent hover:bg-fixme-accent-light disabled:opacity-40 text-fixme-bg font-bold text-base rounded-xl py-4 transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-fixme-bg border-t-transparent rounded-full animate-spin" />
              Verifying...
            </span>
          ) : isLoginFlow ? (
            'Log in ->'
          ) : (
            'Verify code ->'
          )}
        </button>

        <div className="text-center mt-6">
          {resent ? (
            <p className="text-fixme-success text-sm">New code sent.</p>
          ) : (
            <button
              onClick={handleResend}
              disabled={resending}
              className="text-fixme-text-muted text-sm hover:text-fixme-text-secondary transition-colors disabled:opacity-50"
            >
              {resending ? 'Sending...' : "Didn't get it? Resend code"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CustomerFlow({ mode = 'onboarding' }) {
  const prefilledEmail = new URLSearchParams(window.location.search).get('email') || '';
  const isLoginFlow = mode === 'login';

  const [step, setStep] = useState(1);
  const [email, setEmail] = useState(prefilledEmail);
  const [autoSending, setAutoSending] = useState(Boolean(prefilledEmail));
  const [error, setError] = useState('');
  const [devCode, setDevCode] = useState('');

  useEffect(() => {
    if (!prefilledEmail) return;

    fetch(`${API}/send-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: prefilledEmail.trim().toLowerCase() }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.dev_code) setDevCode(data.dev_code);
        setAutoSending(false);
        setStep(2);
      })
      .catch(() => {
        setAutoSending(false);
      });
  }, [prefilledEmail]);

  if (autoSending) {
    return (
      <div className="flex flex-col min-h-screen bg-fixme-bg items-center justify-center gap-4">
        <div className="w-10 h-10 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
        <p className="text-fixme-text-secondary text-sm">Sending your code to</p>
        <p className="text-fixme-accent font-semibold text-sm">{prefilledEmail}</p>
      </div>
    );
  }

  if (step === 1) {
    return (
      <EmailStep
        email={email}
        setEmail={setEmail}
        setStep={setStep}
        setError={setError}
        error={error}
        setDevCode={setDevCode}
        isLoginFlow={isLoginFlow}
      />
    );
  }

  return (
    <CodeStep
      email={email}
      setStep={setStep}
      setError={setError}
      error={error}
      devCode={devCode}
      setDevCode={setDevCode}
      isLoginFlow={isLoginFlow}
    />
  );
}
