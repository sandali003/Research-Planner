'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { api, tokenStore } from '@/lib/api';

const FEATURES = [
  {
    title: 'OBD-II + IoT sensors',
    text: 'Engine, vibration, temperature and battery data in one place.',
    icon: (
      <path d="M4 7h16v10H4zM8 7V4m8 3V4M8 20v-3m8 3v-3M9 12h6" />
    ),
  },
  {
    title: 'Hidden fault prediction',
    text: 'AI spots unusual patterns before they become breakdowns.',
    icon: (
      <path d="M3 12h4l2-6 4 12 2-6h6" />
    ),
  },
  {
    title: 'Clear next steps',
    text: 'Plain-language mitigation advice for every result.',
    icon: (
      <path d="M5 12l4 4L19 6" />
    ),
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isLogin = mode === 'login';

  function switchMode(next: 'login' | 'register') {
    setMode(next);
    setError(null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token } = await (isLogin ? api.login : api.register)(email, password);
      tokenStore.set(token);
      router.replace('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-hero" aria-hidden="true">
        <div className="brand auth-hero-brand">Auto<span>Sense</span></div>
        <div>
          <h1>Know your vehicle&apos;s health before it fails.</h1>
          <p>
            Real-time data from the OBD-II port and the AutoSense IoT device,
            turned into fault predictions you can act on.
          </p>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="auth-hero-image" src="/images/login-car.svg" alt="" />
        <ul className="auth-features">
          {FEATURES.map((f) => (
            <li key={f.title}>
              <span className="auth-feature-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round">
                  {f.icon}
                </svg>
              </span>
              <div>
                <strong>{f.title}</strong>
                <span>{f.text}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="auth-panel">
        <form className="auth-form" onSubmit={submit}>
          <div className="brand auth-mobile-brand">Auto<span>Sense</span></div>

          <h2>{isLogin ? 'Welcome back' : 'Create your account'}</h2>
          <p className="muted small">
            {isLogin
              ? 'Log in to check your vehicles and latest assessments.'
              : 'Start monitoring your vehicle in a few seconds.'}
          </p>

          <div className="auth-toggle" role="tablist">
            <button type="button" role="tab" aria-selected={isLogin}
              className={isLogin ? 'active' : ''} onClick={() => switchMode('login')}>
              Log in
            </button>
            <button type="button" role="tab" aria-selected={!isLogin}
              className={!isLogin ? 'active' : ''} onClick={() => switchMode('register')}>
              Register
            </button>
          </div>

          <label htmlFor="email">Email</label>
          <input id="email" type="email" required autoComplete="email" placeholder="you@example.com"
            value={email} onChange={(e) => setEmail(e.target.value)} />

          <label htmlFor="password">Password</label>
          <div className="auth-password">
            <input id="password" type={showPassword ? 'text' : 'password'} required minLength={8}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              placeholder={isLogin ? 'Your password' : 'At least 8 characters'}
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="auth-show" onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>

          {error && <p className="error" role="alert">{error}</p>}

          <button className="primary auth-submit" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : isLogin ? 'Log in' : 'Create account'}
          </button>

          <p className="muted small auth-footnote">
            Research prototype · AI-based vehicle health assessment
          </p>
        </form>
      </section>
    </main>
  );
}
