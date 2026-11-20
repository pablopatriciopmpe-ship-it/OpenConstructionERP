import { describe, expect, it } from 'vitest';
import { ApiError } from '@/shared/lib/api';
import { passwordErrorMessage } from './passwordError';

describe('password API messages', () => {
  it('explains an incorrect current password in Portuguese', () => {
    expect(passwordErrorMessage(new ApiError(400, 'Bad Request', { detail: 'Current password is incorrect' }))).toBe('Senha atual incorreta.');
  });
  it('explains a weak password', () => {
    expect(passwordErrorMessage(new Error('Password too common'))).toContain('muito comum');
  });
  it('handles validation errors and hides internal errors', () => {
    expect(passwordErrorMessage(new ApiError(422, 'Validation', {}))).toContain('Confira');
    expect(passwordErrorMessage(new Error('Internal SQL failure'))).toBe('Não foi possível alterar a senha. Tente novamente.');
  });
});
