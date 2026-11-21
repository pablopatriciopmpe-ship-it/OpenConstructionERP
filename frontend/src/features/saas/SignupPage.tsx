// Cadastro público "Comece grátis": empresa + dono + teste de 14 dias, sem cartão.
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input, LogoWithText } from '@/shared/ui';
import { useAuthStore } from '@/stores/useAuthStore';
import { meetsPasswordPolicy } from '@/features/auth/passwordPolicy';
import { extractErrorMessageFromBody } from '@/shared/lib/api';
import type { SignupBody, SignupResult } from './api';

export function SignupPage() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [form, setForm] = useState({ full_name: '', email: '', password: '', company_name: '', cnpj: '', trade_name: '', phone: '' });
  const [website, setWebsite] = useState(''); // honeypot: campo escondido, humano não preenche
  const [accept, setAccept] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<SignupResult | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (!meetsPasswordPolicy(form.password)) {
      setError('A senha precisa ter ao menos 8 caracteres, com pelo menos uma letra e um número.');
      return;
    }
    if (!accept) {
      setError('Aceite os termos de uso para criar a conta.');
      return;
    }
    setLoading(true);
    try {
      const body: SignupBody = {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        company_name: form.company_name,
        cnpj: form.cnpj.trim() || null,
        trade_name: form.trade_name.trim() || null,
        phone: form.phone.trim() || null,
        accept_terms: true,
        website,
      };
      const res = await fetch('/api/v1/saas/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(
          res.status === 429
            ? 'Muitas tentativas de cadastro. Aguarde um pouco e tente de novo.'
            : extractErrorMessageFromBody(data) || 'Não foi possível criar a conta.',
        );
        return;
      }
      const result = (await res.json()) as SignupResult;
      if (!result.account_active) {
        setDone(result); // SMTP configurado: falta confirmar o e-mail
        return;
      }
      const login = await fetch('/api/v1/users/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.email, password: form.password }),
      });
      if (login.ok) {
        const tokens = await login.json();
        setTokens(tokens.access_token, tokens.refresh_token, false, form.email);
        navigate('/', { replace: true });
      } else {
        navigate('/login', { replace: true });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-secondary flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border border-border-light bg-surface-elevated p-6 shadow-sm">
        <div className="mb-5 flex justify-center">
          <LogoWithText />
        </div>
        {done ? (
          <div data-testid="signup-confirm-pending" className="text-center space-y-3">
            <h1 className="text-xl font-semibold text-content-primary">Confirme seu e-mail</h1>
            <p className="text-sm text-content-secondary">
              Enviamos um link para {form.email}. Clique nele para ativar o teste grátis de 14 dias.
            </p>
            <Link to="/login" className="text-sm font-medium text-oe-blue">
              Ir para o login
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3" data-testid="signup-form">
            <h1 className="text-xl font-semibold text-content-primary text-center">Comece grátis</h1>
            <p className="text-sm text-content-secondary text-center">
              14 dias para testar, sem cartão de crédito e sem cobrança automática.
            </p>
            <Input label="Seu nome" value={form.full_name} onChange={set('full_name')} required minLength={2} autoComplete="name" />
            <Input label="E-mail" type="email" value={form.email} onChange={set('email')} required autoComplete="email" />
            <Input
              label="Senha"
              type="password"
              value={form.password}
              onChange={set('password')}
              required
              autoComplete="new-password"
              hint="Mínimo de 8 caracteres, com letra e número"
            />
            <Input label="Nome da empresa" value={form.company_name} onChange={set('company_name')} required minLength={2} />
            <Input label="Nome fantasia (opcional)" value={form.trade_name} onChange={set('trade_name')} />
            <Input label="CNPJ (opcional)" value={form.cnpj} onChange={set('cnpj')} placeholder="00.000.000/0000-00" />
            <Input label="Telefone ou WhatsApp (opcional)" value={form.phone} onChange={set('phone')} autoComplete="tel" />
            {/* honeypot: fora da tela e fora da ordem de tabulação */}
            <div aria-hidden="true" style={{ position: 'absolute', left: '-10000px', height: 0, overflow: 'hidden' }}>
              <label>
                Site
                <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </label>
            </div>
            <label className="flex items-start gap-2 text-sm text-content-secondary">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={accept}
                onChange={(e) => setAccept(e.target.checked)}
                data-testid="signup-terms"
              />
              <span>Li e aceito os termos de uso e a política de privacidade.</span>
            </label>
            {error && (
              <p role="alert" className="text-sm text-semantic-error" data-testid="signup-error">
                {error}
              </p>
            )}
            <Button type="submit" variant="primary" loading={loading} className="w-full">
              Criar conta e começar o teste
            </Button>
            <p className="text-center text-xs text-content-tertiary">
              Já tem conta?{' '}
              <Link to="/login" className="font-medium text-oe-blue">
                Entrar
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
