import { ApiError } from '@/shared/lib/api';

/** User-facing copy; never expose upstream English or internal error details. */
export function passwordErrorMessage(error: Error): string {
  const detail = error.message.toLowerCase();
  if (/current password|incorrect password|invalid password|senha atual/.test(detail)) return 'Senha atual incorreta.';
  if (/common|comum/.test(detail)) return 'A nova senha é muito comum. Escolha outra.';
  if (/letter|digit|character|weak|strength|differ/.test(detail)) return 'Use pelo menos 8 caracteres, uma letra e um número, e uma senha diferente da atual.';
  if (error instanceof ApiError && error.status === 422) return 'Confira os dados da senha e tente novamente.';
  return 'Não foi possível alterar a senha. Tente novamente.';
}
