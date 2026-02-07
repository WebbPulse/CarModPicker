import type { CarRead } from '../types/Api';

/**
 * Format year range for display; handles null end_year (current/ongoing generation).
 */
export function formatCarYearRange(
  startYear: number,
  endYear: number | null | undefined
): string {
  if (endYear == null) return `${startYear}–present`;
  return `${startYear}–${endYear}`;
}

/**
 * Normalize a car from the API so make/model/generation_name are always strings.
 * Handles backend refactor where make/model come from related Make/CarModel entities.
 */
export function normalizeCarRead(car: CarRead | null | undefined): CarRead | null {
  if (car == null) return null;
  return {
    ...car,
    make: car.make ?? '',
    model: car.model ?? '',
    generation_name: car.generation_name ?? '',
  };
}

/**
 * Normalize a list of cars from the API; returns empty array if input is null/undefined.
 */
export function normalizeCarReadList(
  cars: CarRead[] | null | undefined
): CarRead[] {
  if (cars == null || !Array.isArray(cars)) return [];
  return cars.map(normalizeCarRead).filter((c): c is CarRead => c != null);
}
