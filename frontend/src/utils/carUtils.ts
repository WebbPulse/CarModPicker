import type { CarGenerationRead } from '../types/Api';

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

export function normalizeCarRead(
  car: CarGenerationRead | null | undefined
): CarGenerationRead | null {
  if (car == null) return null;
  return {
    ...car,
    car_make_name: car.car_make_name ?? '',
    car_model_name: car.car_model_name ?? '',
    generation_name: car.generation_name ?? '',
  };
}

export function normalizeCarReadList(
  cars: CarGenerationRead[] | null | undefined
): CarGenerationRead[] {
  if (cars == null || !Array.isArray(cars)) return [];
  return cars
    .map(normalizeCarRead)
    .filter((c): c is CarGenerationRead => c != null);
}
