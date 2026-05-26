import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { FilterProvider, useFilters } from '../context/FilterContext';

function wrapper({ children }: { children: React.ReactNode }) {
  return <FilterProvider>{children}</FilterProvider>;
}

describe('FilterContext', () => {
  it('provides default filter values', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    expect(result.current.filters.products).toEqual(['jira', 'confluence', 'bitbucket', 'jsm']);
    expect(result.current.filters.deployment).toBe('');
    expect(result.current.filters.q).toBe('');
  });

  it('setFilter updates a single filter', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => result.current.setFilter('deployment', 'cloud'));
    expect(result.current.filters.deployment).toBe('cloud');
  });

  it('setFilter updates products array', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => result.current.setFilter('products', ['jira']));
    expect(result.current.filters.products).toEqual(['jira']);
  });

  it('resetFilters restores defaults', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter('deployment', 'cloud');
      result.current.setFilter('q', 'test');
    });
    act(() => result.current.resetFilters());
    expect(result.current.filters.deployment).toBe('');
    expect(result.current.filters.q).toBe('');
  });

  it('toParams omits empty values', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    const params = result.current.toParams();
    expect(params).not.toHaveProperty('deployment');
    expect(params).not.toHaveProperty('actor');
    expect(params).not.toHaveProperty('q');
  });

  it('toParams includes selected products when fewer than 4', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => result.current.setFilter('products', ['jira', 'confluence']));
    const params = result.current.toParams();
    expect(params.product).toEqual(['jira', 'confluence']);
  });

  it('toParams omits products when all 4 selected', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    const params = result.current.toParams();
    expect(params).not.toHaveProperty('product');
  });

  it('toParams converts preset to from date', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => result.current.setFilter('preset', '7'));
    const params = result.current.toParams();
    expect(params.from).toBeDefined();
    expect(typeof params.from).toBe('string');
  });

  it('toParams uses year/month/day when no preset', () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter('year', '2026');
      result.current.setFilter('month', '5');
    });
    const params = result.current.toParams();
    expect(params.year).toBe('2026');
    expect(params.month).toBe('5');
    expect(params).not.toHaveProperty('from');
  });
});
