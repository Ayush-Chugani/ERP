import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

export type AcademicYear = { id: number; code: string; start: string; end: string; status: string };

type Ctx = { year: AcademicYear | null; choose: (year: AcademicYear | null) => void };

const KEY = 'sims.academic-year';
const AcademicYearContext = createContext<Ctx>({ year: null, choose: () => {} });

function stored(): AcademicYear | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as AcademicYear) : null;
  } catch {
    return null;
  }
}

/** Remembers the academic year the person is working in (per browser). */
export function AcademicYearProvider({ children }: { children: ReactNode }) {
  const [year, setYear] = useState<AcademicYear | null>(stored);
  const choose = useCallback((next: AcademicYear | null) => {
    setYear(next);
    try {
      if (next) window.localStorage.setItem(KEY, JSON.stringify(next));
      else window.localStorage.removeItem(KEY);
    } catch {
      /* storage unavailable: the choice still applies for this tab */
    }
  }, []);
  const value = useMemo(() => ({ year, choose }), [year, choose]);
  return <AcademicYearContext.Provider value={value}>{children}</AcademicYearContext.Provider>;
}

export function useAcademicYear(): Ctx {
  return useContext(AcademicYearContext);
}
