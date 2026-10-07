import type { AuthUser } from './auth-context';

/** Friendly role name for the account menu. Display only; access is enforced by the API. */
export function roleLabel(user: AuthUser | null): string {
  if (!user) return '';
  const groups = user.groups ?? [];
  if (user.is_superuser) return 'Administrator';
  if (groups.includes('Student')) return 'Student';
  if (groups.some((g) => /Registrar|Admissions/.test(g))) return 'Registrar';
  if (groups.some((g) => /Coordinator|Planner|Publisher/.test(g))) return 'Department head';
  if (groups.includes('Teacher')) return 'Faculty';
  if (groups.some((g) => /Result cell|Support Administrator/.test(g))) return 'Staff';
  return groups.length ? 'Staff' : 'Member';
}
