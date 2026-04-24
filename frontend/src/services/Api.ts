// Phase 6 D-22 / FE-04: services/Api.ts is now a re-export shim over the
// per-domain modules under `frontend/src/api/*.ts`. New code SHOULD import
// directly from `../api/<domain>` to avoid this indirection. This shim is
// temporary — a future cleanup phase may delete it and rewrite all import
// sites. Do NOT add new implementation here; add it to the appropriate
// domain module instead.
export { apiClient as default } from '../api/client';
export * from '../api/client';
export * from '../api/admin';
export * from '../api/app_settings';
export * from '../api/auth';
export * from '../api/bug_reports';
export * from '../api/build_list_parts';
export * from '../api/build_list_phases';
export * from '../api/build_lists';
export * from '../api/build_logs';
export * from '../api/car_generations';
export * from '../api/categories';
export * from '../api/images';
export * from '../api/part_manufacturers';
export * from '../api/parts';
export * from '../api/reports';
export * from '../api/retailers';
export * from '../api/search';
export * from '../api/users';
export * from '../api/utility';
export * from '../api/votes';
