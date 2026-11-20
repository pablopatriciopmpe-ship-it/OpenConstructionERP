// DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
// Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
import { useEffect, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Input, LogoWithText } from '@/shared/ui';
import { readRememberChoice, saveRememberChoice, useAuthStore } from '@/stores/useAuthStore';
import { extractErrorMessageFromBody } from '@/shared/lib/api';
import { BRAND } from '@/brand';
import { safeNextPath } from './nextPath';
import { beginOidcLogin } from './oidcPkce';

export function LoginPage() {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(readRememberChoice);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [oidc, setOidc] = useState<{ client_id: string; scopes: string; authorization_endpoint?: string; issuer_url: string } | null>(null);
  useEffect(() => {
    document.title = BRAND.name;
    let active = true;
    fetch('/api/v1/users/auth/oidc/config/').then((r) => r.ok ? r.json() : null)
      .then((config) => { if (active && config?.enabled) setOidc(config); }).catch(() => {});
    return () => { active = false; };
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/v1/users/auth/login/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        setError(response.status >= 500 ? 'Servidor indisponível. Tente novamente em instantes.'
          : extractErrorMessageFromBody(data) || 'Confira seu e-mail e sua senha.');
        return;
      }
      if (!data?.access_token || !data?.refresh_token) {
        setError('Não foi possível iniciar a sessão. Tente novamente.');
        return;
      }
      saveRememberChoice(remember);
      setTokens(data.access_token, data.refresh_token, remember, email);
      navigate(safeNextPath(location.search), { replace: true });
    } catch {
      setError('Não foi possível conectar ao servidor.');
    } finally { setLoading(false); }
  };
  return <main className="min-h-screen flex items-center justify-center p-6 bg-surface-secondary">
    <section className="w-full max-w-md rounded-xl border border-border-light bg-surface-elevated p-8 space-y-6">
      <LogoWithText size="lg" />
      <div><h1 className="text-2xl font-semibold">Acesse sua conta</h1>
        <p className="text-content-secondary mt-2">Orçamento e acompanhamento da sua obra.</p></div>
      <label className="block text-sm">Idioma
        <select aria-label="Idioma" className="oe-select mt-1 w-full" value={i18n.language} onChange={(e) => void i18n.changeLanguage(e.target.value)}>
          <option value="pt-BR">Português (Brasil)</option><option value="en">English</option>
        </select>
      </label>
      <form onSubmit={submit} className="space-y-4">
        <Input label="E-mail" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Input label="Senha" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />Manter conectado</label>
        {error && <p role="alert" className="text-semantic-error">{error}</p>}
        <Button type="submit" disabled={loading} className="w-full">{loading ? 'Entrando…' : 'Entrar'}</Button>
      </form>
      {oidc && <Button onClick={async () => {
        try {
          const { state, nonce, codeChallenge } = await beginOidcLogin();
          const params = new URLSearchParams({ client_id: oidc.client_id, response_type: 'code',
            scope: oidc.scopes, redirect_uri: `${window.location.origin}/auth/oidc/callback`,
            state, nonce, code_challenge: codeChallenge, code_challenge_method: 'S256' });
          const authorize = oidc.authorization_endpoint ?? `${oidc.issuer_url.replace(/\/$/, '')}/protocol/openid-connect/auth`;
          window.location.href = `${authorize}?${params}`;
        } catch { setError('Não foi possível iniciar o acesso da empresa.'); }
      }}>Entrar com a conta da empresa</Button>}
      <Link className="block underline text-sm" to="/forgot-password">Esqueci minha senha</Link>
      <footer className="text-xs text-content-secondary"><a href="/api/source" target="_blank" rel="noopener noreferrer">{BRAND.sourceLabel}</a></footer>
    </section>
  </main>;
}
