import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export interface Filters {
  products: string[];
  deployment: string;
  year: string;
  month: string;
  day: string;
  preset: string;
  user: string;
  group: string;
  operation: string;
  category: string;
  q: string;
}

const defaults: Filters = {
  products: ['jira', 'confluence', 'bitbucket', 'jsm'],
  deployment: '',
  year: '',
  month: '',
  day: '',
  preset: '',
  user: '',
  group: '',
  operation: '',
  category: '',
  q: '',
};

interface FilterState {
  filters: Filters;
  setFilter: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
  resetFilters: () => void;
  toParams: () => Record<string, string | string[]>;
}

const FilterContext = createContext<FilterState>({
  filters: defaults,
  setFilter: () => {},
  resetFilters: () => {},
  toParams: () => ({}),
});

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>({ ...defaults });

  const setFilter = useCallback(<K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters({ ...defaults });
  }, []);

  const toParams = useCallback((): Record<string, string | string[]> => {
    const p: Record<string, string | string[]> = {};
    if (filters.products.length < 4) p.product = filters.products;
    if (filters.deployment) p.deployment = [filters.deployment];
    if (filters.user) p.actor = filters.user;
    if (filters.group) p.group = filters.group;
    if (filters.operation) p.operation = filters.operation;
    if (filters.category) p.category = filters.category;
    if (filters.q) p.q = filters.q;

    if (filters.preset) {
      const days = parseInt(filters.preset);
      if (!isNaN(days)) {
        const from = new Date(Date.now() - days * 86400000);
        p.from = from.toISOString();
      }
    } else {
      if (filters.year) p.year = filters.year;
      if (filters.month) p.month = filters.month;
      if (filters.day) p.day = filters.day;
    }

    return p;
  }, [filters]);

  return (
    <FilterContext.Provider value={{ filters, setFilter, resetFilters, toParams }}>
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  return useContext(FilterContext);
}
