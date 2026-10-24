export type FieldErrors<T extends string> = Partial<Record<T, string>>;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

export function validateName(value: string, label = 'El nombre'): string | undefined {
  const v = value.trim();
  if (!v) return `${label} es obligatorio.`;
  if (v.length < 2) return `${label} es demasiado corto.`;
  if (v.length > 80) return `${label} es demasiado largo.`;
  return undefined;
}

export function validateEmail(value: string): string | undefined {
  const v = value.trim();
  if (!v) return 'El correo es obligatorio.';
  if (!isValidEmail(v)) return 'Escribe un correo válido (nombre@dominio.com).';
  return undefined;
}

export function validatePassword(value: string): string | undefined {
  if (!value) return 'La contraseña es obligatoria.';
  if (value.length < 8) return 'Usa al menos 8 caracteres.';
  return undefined;
}

export function validateRequired(value: string, message: string): string | undefined {
  return value.trim() ? undefined : message;
}

export function hasErrors(errors: object): boolean {
  return Object.values(errors).some(Boolean);
}
