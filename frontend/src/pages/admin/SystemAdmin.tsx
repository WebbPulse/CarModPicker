import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSettings } from '../../hooks/useAppSettings';
import { useAuth } from '../../hooks/useAuth';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import { adminApi, appSettingsApi, imageApi } from '../../services/Api';

function SystemAdmin() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { settings: appSettings, setSettings: setAppSettings } =
    useAppSettings();

  // Global app settings (e.g. premium-system kill switch)
  const [isSavingAppSettings, setIsSavingAppSettings] = useState(false);
  const [appSettingsError, setAppSettingsError] = useState<string | null>(null);

  // Migrations
  const [isRunningMigrations, setIsRunningMigrations] = useState(false);
  const [migrationResult, setMigrationResult] = useState<{
    success: boolean;
    output: string;
    error: string | null;
    current_revision: string | null;
  } | null>(null);
  const [currentRevision, setCurrentRevision] = useState<string | null>(null);
  const [isLoadingRevision, setIsLoadingRevision] = useState(false);

  // Data initialization
  const [isInitCarGenerations, setIsInitCarGenerations] = useState(false);
  const [initCarGenerationsResult, setInitCarGenerationsResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isInitPartCategories, setIsInitPartCategories] = useState(false);
  const [initPartCategoriesResult, setInitPartCategoriesResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // Deletions
  const [isDeleteAllCarsConfirmOpen, setIsDeleteAllCarsConfirmOpen] =
    useState(false);
  const [isDeletingAllCars, setIsDeletingAllCars] = useState(false);
  const [deleteAllCarsError, setDeleteAllCarsError] = useState<string | null>(
    null
  );
  const [deleteAllCarsResult, setDeleteAllCarsResult] = useState<{
    deleted_count: number;
    deleted_car_models_count: number;
    deleted_makes_count: number;
  } | null>(null);

  const [isDeleteAllPartsConfirmOpen, setIsDeleteAllPartsConfirmOpen] =
    useState(false);
  const [isDeletingAllParts, setIsDeletingAllParts] = useState(false);
  const [deleteAllPartsError, setDeleteAllPartsError] = useState<string | null>(
    null
  );
  const [deleteAllPartsResult, setDeleteAllPartsResult] = useState<{
    deleted_count: number;
  } | null>(null);

  const [
    isDeleteAllPartManufacturersConfirmOpen,
    setIsDeleteAllPartManufacturersConfirmOpen,
  ] = useState(false);
  const [isDeletingAllPartManufacturers, setIsDeletingAllPartManufacturers] =
    useState(false);
  const [deleteAllPartManufacturersError, setDeleteAllPartManufacturersError] =
    useState<string | null>(null);
  const [
    deleteAllPartManufacturersResult,
    setDeleteAllPartManufacturersResult,
  ] = useState<{
    deleted_count: number;
  } | null>(null);

  // Bucket orphan cleanup
  const [orphanedResult, setOrphanedResult] = useState<{
    count: number;
    total_bucket: number;
    total_referenced: number;
    orphaned_keys: string[];
  } | null>(null);
  const [isListingOrphaned, setIsListingOrphaned] = useState(false);
  const [isPurgingOrphaned, setIsPurgingOrphaned] = useState(false);
  const [isPurgeOrphanConfirmOpen, setIsPurgeOrphanConfirmOpen] =
    useState(false);
  const [purgeOrphanError, setPurgeOrphanError] = useState<string | null>(null);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  useEffect(() => {
    void fetchCurrentRevision();
  }, []);

  const handleTogglePremiumDisabled = async (nextValue: boolean) => {
    setIsSavingAppSettings(true);
    setAppSettingsError(null);
    try {
      const response = await appSettingsApi.update({
        premium_disabled: nextValue,
      });
      setAppSettings(response.data);
    } catch (error) {
      setAppSettingsError(
        error instanceof Error
          ? error.message
          : 'Failed to update premium-system setting.'
      );
    } finally {
      setIsSavingAppSettings(false);
    }
  };

  const fetchCurrentRevision = async () => {
    setIsLoadingRevision(true);
    try {
      const response = await adminApi.getCurrentRevision();
      setCurrentRevision(response.data.current_revision);
    } catch (error) {
      console.error('Failed to fetch current revision:', error);
    } finally {
      setIsLoadingRevision(false);
    }
  };

  const handleRunMigrations = async () => {
    setIsRunningMigrations(true);
    setMigrationResult(null);
    try {
      const response = await adminApi.runMigrations();
      setMigrationResult(response.data);
      await fetchCurrentRevision();
    } catch (error) {
      setMigrationResult({
        success: false,
        output: '',
        error:
          error instanceof Error ? error.message : 'Failed to run migrations',
        current_revision: null,
      });
    } finally {
      setIsRunningMigrations(false);
    }
  };

  const handleInitCarGenerations = async () => {
    setIsInitCarGenerations(true);
    setInitCarGenerationsResult(null);
    try {
      const response = await adminApi.initCarGenerations();
      setInitCarGenerationsResult(response.data);
    } catch (error) {
      setInitCarGenerationsResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize car generations',
      });
    } finally {
      setIsInitCarGenerations(false);
    }
  };

  const handleInitPartCategories = async () => {
    setIsInitPartCategories(true);
    setInitPartCategoriesResult(null);
    try {
      const response = await adminApi.initPartCategories();
      setInitPartCategoriesResult(response.data);
    } catch (error) {
      setInitPartCategoriesResult({
        success: false,
        message:
          error instanceof Error
            ? error.message
            : 'Failed to initialize part categories',
      });
    } finally {
      setIsInitPartCategories(false);
    }
  };

  const handleConfirmDeleteAllCars = async () => {
    setIsDeletingAllCars(true);
    setDeleteAllCarsError(null);
    try {
      const response = await adminApi.deleteAllCars();
      setDeleteAllCarsResult(response.data);
      setIsDeleteAllCarsConfirmOpen(false);
    } catch (error) {
      setDeleteAllCarsError(
        error instanceof Error ? error.message : 'Failed to delete all cars.'
      );
    } finally {
      setIsDeletingAllCars(false);
    }
  };

  const handleConfirmDeleteAllParts = async () => {
    setIsDeletingAllParts(true);
    setDeleteAllPartsError(null);
    try {
      const response = await adminApi.deleteAllParts();
      setDeleteAllPartsResult(response.data);
      setIsDeleteAllPartsConfirmOpen(false);
    } catch (error) {
      setDeleteAllPartsError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all global parts.'
      );
    } finally {
      setIsDeletingAllParts(false);
    }
  };

  const handleConfirmDeleteAllPartManufacturers = async () => {
    setIsDeletingAllPartManufacturers(true);
    setDeleteAllPartManufacturersError(null);
    try {
      const response = await adminApi.deleteAllPartManufacturers();
      setDeleteAllPartManufacturersResult(response.data);
      setIsDeleteAllPartManufacturersConfirmOpen(false);
    } catch (error) {
      setDeleteAllPartManufacturersError(
        error instanceof Error
          ? error.message
          : 'Failed to delete all part manufacturers.'
      );
    } finally {
      setIsDeletingAllPartManufacturers(false);
    }
  };

  const handleListOrphaned = async () => {
    setIsListingOrphaned(true);
    setOrphanedResult(null);
    try {
      const response = await imageApi.getOrphanedBucketObjects();
      setOrphanedResult(response.data);
    } catch {
      setOrphanedResult(null);
    } finally {
      setIsListingOrphaned(false);
    }
  };

  const handleConfirmPurgeOrphaned = async () => {
    setIsPurgingOrphaned(true);
    setPurgeOrphanError(null);
    try {
      await imageApi.purgeOrphanedBucketObjects();
      setIsPurgeOrphanConfirmOpen(false);
      setOrphanedResult(null);
    } catch (error) {
      setPurgeOrphanError(
        error instanceof Error
          ? error.message
          : 'Failed to purge orphaned bucket objects.'
      );
    } finally {
      setIsPurgingOrphaned(false);
    }
  };

  if (!user) {
    return (
      <div>
        <PageHeader title="System & Database" />
        <Card>
          <ErrorAlert message="Please log in to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="System & Database" />
        <Card>
          <ErrorAlert message="You do not have permission to access the admin dashboard." />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="System & Database"
        subtitle="Manage migrations, initialize seed data, and perform destructive operations"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
      </div>

      {/* Global app settings */}
      <div className="mb-4">
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-white mb-1">
            Global App Settings
          </h2>
          <p className="text-sm text-neutral-400 mb-3">
            Site-wide toggles that apply to every user regardless of
            subscription tier.
          </p>
          <div className="p-3 bg-neutral-900/40 border border-neutral-700 rounded-lg">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-neutral-600 bg-neutral-800 text-blue-500 focus:ring-blue-500 cursor-pointer"
                checked={appSettings?.premium_disabled ?? false}
                disabled={isSavingAppSettings || appSettings == null}
                onChange={(e) =>
                  void handleTogglePremiumDisabled(e.target.checked)
                }
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">
                    Disconnect premium system
                  </span>
                  {isSavingAppSettings && <LoadingSpinner size="sm" inline />}
                </div>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Hard kill switch for everything paid. When on: ads are
                  suppressed for every visitor, all subscription-tier gates are
                  bypassed (everyone gets the premium experience), and all
                  pricing, checkout, and upgrade prompts are hidden from the UI.
                  Admin subscription editing still works so values persist for
                  when you turn it back on. Ad columns remain as layout spacers.
                </p>
              </div>
            </label>
            {appSettingsError && (
              <div className="mt-2">
                <ErrorAlert message={appSettingsError} />
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Database Migrations */}
        <Card padding="sm">
          <div className="mb-2">
            <h2 className="text-lg font-semibold text-white mb-1">
              Database Migrations
            </h2>
            <p className="text-sm text-neutral-400">
              Run migrations to update the database schema on-demand.
              {currentRevision && (
                <>
                  {' '}
                  Current:{' '}
                  <span className="font-mono text-white">
                    {currentRevision}
                  </span>
                </>
              )}
            </p>
          </div>
          <div className="p-3 bg-blue-900/20 border border-blue-700 rounded-lg">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <ActionButton
                onClick={() => void handleRunMigrations()}
                disabled={isRunningMigrations}
                className="bg-linear-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
              >
                {isRunningMigrations ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Running Migrations...
                  </span>
                ) : (
                  '🔄 Run Migrations'
                )}
              </ActionButton>
              <ActionButton
                onClick={() => void fetchCurrentRevision()}
                disabled={isLoadingRevision}
                className="text-sm"
              >
                {isLoadingRevision ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Loading...
                  </span>
                ) : (
                  '🔄 Refresh Revision'
                )}
              </ActionButton>
            </div>
            {migrationResult && (
              <div
                className={`p-3 rounded-lg border text-sm ${
                  migrationResult.success
                    ? 'bg-green-900/20 border-green-700'
                    : 'bg-red-900/20 border-red-700'
                }`}
              >
                <div className="mb-1">
                  <span
                    className={`font-semibold ${
                      migrationResult.success
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {migrationResult.success
                      ? '✓ Migrations completed successfully'
                      : '✗ Migration failed'}
                  </span>
                </div>
                {migrationResult.current_revision && (
                  <div className="text-neutral-300 mb-1">
                    <span className="font-semibold">New revision:</span>{' '}
                    <span className="font-mono">
                      {migrationResult.current_revision}
                    </span>
                  </div>
                )}
                {migrationResult.output && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-300">
                      View output
                    </summary>
                    <pre className="mt-2 p-2 bg-gray-900 rounded text-xs text-neutral-300 overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.output}
                    </pre>
                  </details>
                )}
                {migrationResult.error && (
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-red-400 mb-1">
                      Error:
                    </p>
                    <pre className="p-2 bg-gray-900 rounded text-xs text-red-300 overflow-x-auto max-h-60 overflow-y-auto">
                      {migrationResult.error}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Data Initialization */}
        <Card padding="sm">
          <h2 className="text-lg font-semibold text-white mb-1">
            Data Initialization
          </h2>
          <p className="text-sm text-neutral-400 mb-3">
            Sync car generations and part categories from source of truth.
          </p>
          <div className="p-3 bg-amber-900/20 border border-amber-700 rounded-lg">
            <div className="flex flex-wrap gap-3 mb-2">
              <ActionButton
                onClick={() => void handleInitCarGenerations()}
                disabled={isInitCarGenerations}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isInitCarGenerations ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Initializing...
                  </span>
                ) : (
                  '🚗 Init Car Generations'
                )}
              </ActionButton>
              <ActionButton
                onClick={() => void handleInitPartCategories()}
                disabled={isInitPartCategories}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isInitPartCategories ? (
                  <span className="flex items-center">
                    <span className="mr-2">
                      <LoadingSpinner size="sm" inline />
                    </span>
                    Initializing...
                  </span>
                ) : (
                  '📦 Init Part Categories'
                )}
              </ActionButton>
            </div>
            {(initCarGenerationsResult || initPartCategoriesResult) && (
              <div className="space-y-2 mt-2">
                {initCarGenerationsResult && (
                  <div
                    className={`p-2 rounded border text-sm ${
                      initCarGenerationsResult.success
                        ? 'bg-green-900/20 border-green-700 text-green-400'
                        : 'bg-red-900/20 border-red-700 text-red-400'
                    }`}
                  >
                    Car generations: {initCarGenerationsResult.message}
                  </div>
                )}
                {initPartCategoriesResult && (
                  <div
                    className={`p-2 rounded border text-sm ${
                      initPartCategoriesResult.success
                        ? 'bg-green-900/20 border-green-700 text-green-400'
                        : 'bg-red-900/20 border-red-700 text-red-400'
                    }`}
                  >
                    Part categories: {initPartCategoriesResult.message}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>
      {/* end grid */}

      {/* Destructive operations */}
      <div className="mt-4">
        <Card padding="sm">
          <details className="group border border-red-800/50 rounded-lg overflow-hidden">
            <summary className="cursor-pointer list-none px-3 py-2 bg-red-900/20 hover:bg-red-900/30 transition-colors flex items-center justify-between text-sm">
              <span className="font-semibold text-red-400">
                Deletion options (cars, global parts, part manufacturers,
                bucket)
              </span>
              <span className="text-red-400/80 group-open:rotate-180 transition-transform inline-block">
                ▼
              </span>
            </summary>
            <div className="divide-y divide-gray-700">
              {/* Delete all cars */}
              <div className="p-3 bg-orange-900/20 border-t border-orange-700/50">
                <h3 className="text-base font-semibold text-orange-400 mb-1">
                  Delete all cars (generations)
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Permanently remove every car generation, car model, and make
                  from the catalog. Build lists are unlinked from cars (not
                  deleted). Run &quot;Init Car Generations&quot; afterward to
                  repopulate from a clean slate. This action cannot be undone.
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => {
                      setDeleteAllCarsError(null);
                      setDeleteAllCarsResult(null);
                      setIsDeleteAllCarsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllCars}
                    className="bg-orange-600 hover:bg-orange-700 text-white text-sm py-1.5 px-3"
                  >
                    {isDeletingAllCars ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Deleting...
                      </span>
                    ) : (
                      'Delete all cars'
                    )}
                  </ActionButton>
                </div>
                {deleteAllCarsResult && (
                  <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                    <p className="font-semibold">
                      Deleted{' '}
                      {deleteAllCarsResult.deleted_count.toLocaleString()}{' '}
                      car(s),{' '}
                      {deleteAllCarsResult.deleted_car_models_count.toLocaleString()}{' '}
                      car model(s), and{' '}
                      {deleteAllCarsResult.deleted_makes_count.toLocaleString()}{' '}
                      make(s). Run Init Car Generations to repopulate.
                    </p>
                  </div>
                )}
              </div>

              {/* Delete all global parts / part manufacturers */}
              <div className="p-3 bg-red-900/20 border-t border-red-700/50">
                <h3 className="text-base font-semibold text-red-400 mb-1">
                  Delete all global parts / part manufacturers
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Permanently remove every global part from the catalog (also
                  removes their part listings, votes, reports, and build list
                  part associations). Or remove only part manufacturers (parts
                  keep their data; part manufacturer references are cleared).
                  These actions cannot be undone.
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => {
                      setDeleteAllPartsError(null);
                      setDeleteAllPartsResult(null);
                      setIsDeleteAllPartsConfirmOpen(true);
                    }}
                    disabled={isDeletingAllParts}
                    className="bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
                  >
                    {isDeletingAllParts ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Deleting...
                      </span>
                    ) : (
                      'Delete all global parts'
                    )}
                  </ActionButton>
                  <ActionButton
                    onClick={() => {
                      setDeleteAllPartManufacturersError(null);
                      setDeleteAllPartManufacturersResult(null);
                      setIsDeleteAllPartManufacturersConfirmOpen(true);
                    }}
                    disabled={isDeletingAllPartManufacturers}
                    className="bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
                  >
                    {isDeletingAllPartManufacturers ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Deleting...
                      </span>
                    ) : (
                      'Delete all part manufacturers'
                    )}
                  </ActionButton>
                </div>
                {(deleteAllPartsResult || deleteAllPartManufacturersResult) && (
                  <div className="space-y-1 mt-2">
                    {deleteAllPartsResult && (
                      <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllPartsResult.deleted_count.toLocaleString()}{' '}
                          global part(s).
                        </p>
                      </div>
                    )}
                    {deleteAllPartManufacturersResult && (
                      <div className="p-2 rounded border border-green-700 bg-green-900/20 text-sm text-green-400">
                        <p className="font-semibold">
                          Deleted{' '}
                          {deleteAllPartManufacturersResult.deleted_count.toLocaleString()}{' '}
                          part manufacturer(s). Parts keep their data; part
                          manufacturer references were cleared.
                        </p>
                      </div>
                    )}
                    {deleteAllPartsError && (
                      <ErrorAlert message={deleteAllPartsError} />
                    )}
                    {deleteAllPartManufacturersError && (
                      <ErrorAlert message={deleteAllPartManufacturersError} />
                    )}
                  </div>
                )}
              </div>

              {/* Bucket orphan cleanup */}
              <div className="p-3 bg-cyan-900/20 border-t border-cyan-700/50">
                <h3 className="text-base font-semibold text-cyan-400 mb-1">
                  Bucket orphan cleanup
                </h3>
                <p className="text-neutral-400 mb-2 text-xs">
                  Bucket objects that are not referenced by any entity (global
                  parts, users, cars, build lists, image cache) can be safely
                  removed to free space. Only orphaned objects are deleted; no
                  entity loses its images.
                </p>
                <div className="flex flex-wrap gap-2 mb-2">
                  <ActionButton
                    onClick={() => void handleListOrphaned()}
                    disabled={isListingOrphaned}
                    className="bg-cyan-600 hover:bg-cyan-700 text-white text-sm py-1.5 px-3"
                  >
                    {isListingOrphaned ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Listing...
                      </span>
                    ) : (
                      'List orphaned (dry run)'
                    )}
                  </ActionButton>
                  <ActionButton
                    onClick={() => {
                      setPurgeOrphanError(null);
                      setIsPurgeOrphanConfirmOpen(true);
                    }}
                    disabled={isPurgingOrphaned}
                    className="bg-amber-600 hover:bg-amber-700 text-white text-sm py-1.5 px-3"
                  >
                    {isPurgingOrphaned ? (
                      <span className="flex items-center">
                        <span className="mr-2">
                          <LoadingSpinner size="sm" inline />
                        </span>
                        Purging...
                      </span>
                    ) : (
                      'Purge orphaned objects'
                    )}
                  </ActionButton>
                </div>
                {orphanedResult && (
                  <div className="p-2 rounded border border-cyan-700 bg-gray-900/50 text-sm text-neutral-300">
                    <p className="mb-1">
                      <span className="font-semibold text-cyan-400">
                        {orphanedResult.count.toLocaleString()}
                      </span>{' '}
                      orphaned object(s) of{' '}
                      <span className="font-semibold">
                        {orphanedResult.total_bucket.toLocaleString()}
                      </span>{' '}
                      total in bucket (
                      {orphanedResult.total_referenced.toLocaleString()}{' '}
                      referenced by entities).
                    </p>
                    {orphanedResult.orphaned_keys.length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-xs text-neutral-400 hover:text-neutral-300">
                          Show key list (first 50)
                        </summary>
                        <pre className="mt-2 p-2 bg-gray-800 rounded text-xs text-neutral-300 overflow-x-auto max-h-48 overflow-y-auto">
                          {orphanedResult.orphaned_keys.slice(0, 50).join('\n')}
                          {orphanedResult.orphaned_keys.length > 50 &&
                            `\n... and ${orphanedResult.orphaned_keys.length - 50} more`}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
            </div>
          </details>
        </Card>
      </div>

      {/* Confirmation dialogs */}
      <DeleteConfirmationDialog
        isOpen={isPurgeOrphanConfirmOpen}
        onClose={() => {
          setIsPurgeOrphanConfirmOpen(false);
          setPurgeOrphanError(null);
        }}
        onConfirm={() => void handleConfirmPurgeOrphaned()}
        itemName="orphaned bucket objects (only unreferenced images)"
        itemType="storage"
        isProcessing={isPurgingOrphaned}
        error={purgeOrphanError}
      />
      <DeleteConfirmationDialog
        isOpen={isDeleteAllPartsConfirmOpen}
        onClose={() => {
          setIsDeleteAllPartsConfirmOpen(false);
          setDeleteAllPartsError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllParts()}
        itemName="all global parts"
        itemType="catalog"
        isProcessing={isDeletingAllParts}
        error={deleteAllPartsError}
      />
      <DeleteConfirmationDialog
        isOpen={isDeleteAllPartManufacturersConfirmOpen}
        onClose={() => {
          setIsDeleteAllPartManufacturersConfirmOpen(false);
          setDeleteAllPartManufacturersError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllPartManufacturers()}
        itemName="all part manufacturers"
        itemType="catalog"
        isProcessing={isDeletingAllPartManufacturers}
        error={deleteAllPartManufacturersError}
      />
      <DeleteConfirmationDialog
        isOpen={isDeleteAllCarsConfirmOpen}
        onClose={() => {
          setIsDeleteAllCarsConfirmOpen(false);
          setDeleteAllCarsError(null);
        }}
        onConfirm={() => void handleConfirmDeleteAllCars()}
        itemName="all cars (generations)"
        itemType="catalog"
        isProcessing={isDeletingAllCars}
        error={deleteAllCarsError}
      />
    </div>
  );
}

export default SystemAdmin;
