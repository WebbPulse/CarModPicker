import type { AxiosResponse } from 'axios';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import apiClient, { bugReportsApi } from '../../services/Api';
import type {
  BugReportUpdate,
  BugReportWithDetails,
  PaginatedResponse,
} from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import Dialog from '../../components/common/Dialog';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ADMIN_ITEMS_PER_PAGE } from '../../constants';

const fetchBugReportsRequestFn = (params?: {
  status?: string;
  priority?: string;
  skip?: number;
  limit?: number;
}): Promise<AxiosResponse<PaginatedResponse<BugReportWithDetails>>> =>
  bugReportsApi.getBugReportsWithDetails(params);
const updateBugReportRequestFn = (payload: {
  bugReportId: string;
  data: BugReportUpdate;
}): Promise<AxiosResponse<BugReportWithDetails>> =>
  apiClient.put<BugReportWithDetails>(
    `/bug-reports/${payload.bugReportId}`,
    payload.data
  );
const getPendingBugReportsCountRequestFn = (): Promise<
  AxiosResponse<PaginatedResponse<BugReportWithDetails>>
> =>
  bugReportsApi.getBugReportsWithDetails({
    status: 'pending',
    skip: 0,
    limit: 1,
  });

function BugReportReview() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [selectedStatus, setSelectedStatus] = useState<string>('pending');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [isReviewDialogOpen, setIsReviewDialogOpen] = useState(false);
  const [selectedBugReport, setSelectedBugReport] =
    useState<BugReportWithDetails | null>(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [priority, setPriority] = useState<string>('medium');
  const [pendingCount, setPendingCount] = useState<number>(0);

  const {
    data: bugReportsData,
    isLoading: isLoadingBugReports,
    error: bugReportsError,
    executeRequest: fetchBugReports,
  } = useApiRequest<
    PaginatedResponse<BugReportWithDetails>,
    {
      status?: string;
      priority?: string;
      skip?: number;
      limit?: number;
    }
  >(fetchBugReportsRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateBugReportRequestFn);

  const { data: countData, executeRequest: fetchPendingCount } = useApiRequest<
    PaginatedResponse<BugReportWithDetails>,
    never
  >(getPendingBugReportsCountRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  // Reset to page 1 when status or priority changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedStatus, selectedPriority]);

  useEffect(() => {
    void fetchBugReports({
      ...(selectedStatus !== 'all' && { status: selectedStatus }),
      ...(selectedPriority !== 'all' && { priority: selectedPriority }),
      skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
      limit: ADMIN_ITEMS_PER_PAGE,
    });
    void fetchPendingCount();
  }, [
    fetchBugReports,
    fetchPendingCount,
    selectedStatus,
    selectedPriority,
    currentPage,
  ]);

  useEffect(() => {
    if (
      countData &&
      typeof countData === 'object' &&
      'pagination' in countData &&
      countData.pagination &&
      typeof countData.pagination === 'object' &&
      'total_items' in countData.pagination &&
      typeof countData.pagination.total_items === 'number'
    ) {
      setPendingCount(countData.pagination.total_items);
    }
  }, [countData]);

  if (!user) {
    return (
      <div>
        <PageHeader title="Bug Report Review" />
        <Card>
          <ErrorAlert message="Please log in to access bug report review." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Bug Report Review" />
        <Card>
          <ErrorAlert message="You do not have permission to access bug report review." />
        </Card>
      </div>
    );
  }

  const handleUpdateBugReport = async (
    newStatus: 'resolved' | 'dismissed' | 'in_progress'
  ) => {
    if (!selectedBugReport) return;

    const result = await executeUpdate({
      bugReportId: selectedBugReport.id,
      data: {
        status: newStatus,
        priority: priority as 'low' | 'medium' | 'high' | 'critical',
        admin_notes: adminNotes,
      },
    });

    if (result) {
      setIsReviewDialogOpen(false);
      setSelectedBugReport(null);
      setAdminNotes('');
      void fetchBugReports({
        ...(selectedStatus !== 'all' && { status: selectedStatus }),
        ...(selectedPriority !== 'all' && { priority: selectedPriority }),
        skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
        limit: ADMIN_ITEMS_PER_PAGE,
      });
      void fetchPendingCount();
    }
  };

  const openReviewDialog = (bugReport: BugReportWithDetails) => {
    setUpdateError(null);
    setSelectedBugReport(bugReport);
    setAdminNotes(bugReport.admin_notes || '');
    setPriority(bugReport.priority);
    setIsReviewDialogOpen(true);
  };

  const closeReviewDialog = () => {
    setIsReviewDialogOpen(false);
    setSelectedBugReport(null);
    setAdminNotes('');
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      pending: { color: 'bg-yellow-600 text-yellow-100', text: 'Pending' },
      in_progress: { color: 'bg-blue-600 text-blue-100', text: 'In Progress' },
      resolved: { color: 'bg-green-600 text-green-100', text: 'Resolved' },
      dismissed: { color: 'bg-gray-600 text-gray-100', text: 'Dismissed' },
    };

    const config =
      statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
    return (
      <span className={`px-2 py-1 rounded text-xs ${config.color}`}>
        {config.text}
      </span>
    );
  };

  const getPriorityBadge = (priority: string) => {
    const priorityConfig = {
      low: { color: 'bg-gray-600 text-gray-100', text: 'Low' },
      medium: { color: 'bg-yellow-600 text-yellow-100', text: 'Medium' },
      high: { color: 'bg-orange-600 text-orange-100', text: 'High' },
      critical: { color: 'bg-red-600 text-red-100', text: 'Critical' },
    };

    const config =
      priorityConfig[priority as keyof typeof priorityConfig] ||
      priorityConfig.medium;
    return (
      <span className={`px-2 py-1 rounded text-xs ${config.color}`}>
        {config.text}
      </span>
    );
  };

  // Extract bug reports and pagination info from the response
  const bugReports: BugReportWithDetails[] =
    bugReportsData &&
    typeof bugReportsData === 'object' &&
    'data' in bugReportsData
      ? Array.isArray(bugReportsData.data)
        ? bugReportsData.data
        : []
      : [];
  const pagination =
    bugReportsData &&
    typeof bugReportsData === 'object' &&
    'pagination' in bugReportsData
      ? bugReportsData.pagination
      : undefined;

  if (isLoadingBugReports && !bugReportsData) {
    return (
      <>
        <PageHeader title="Bug Report Review" />
        <LoadingSpinner />
      </>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Bug Report Review"
        subtitle="Review and manage bug reports"
      />

      <div className="flex flex-col sm:flex-row sm:items-start gap-3 mb-4">
        <div className="shrink-0">
          <ActionButton onClick={() => void navigate('/admin')}>
            ← Back to Admin Dashboard
          </ActionButton>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <ActionButton
              onClick={() => setSelectedStatus('pending')}
              className={
                selectedStatus === 'pending' ? 'bg-blue-600' : 'bg-gray-600'
              }
            >
              Pending ({pendingCount})
            </ActionButton>
            <ActionButton
              onClick={() => setSelectedStatus('in_progress')}
              className={
                selectedStatus === 'in_progress' ? 'bg-blue-600' : 'bg-gray-600'
              }
            >
              In Progress
            </ActionButton>
            <ActionButton
              onClick={() => setSelectedStatus('resolved')}
              className={
                selectedStatus === 'resolved' ? 'bg-blue-600' : 'bg-gray-600'
              }
            >
              Resolved
            </ActionButton>
            <ActionButton
              onClick={() => setSelectedStatus('dismissed')}
              className={
                selectedStatus === 'dismissed' ? 'bg-blue-600' : 'bg-gray-600'
              }
            >
              Dismissed
            </ActionButton>
            <ActionButton
              onClick={() => setSelectedStatus('all')}
              className={
                selectedStatus === 'all' ? 'bg-blue-600' : 'bg-gray-600'
              }
            >
              All
            </ActionButton>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-400 shrink-0">
              Priority:
            </span>
            {['all', 'low', 'medium', 'high', 'critical'].map((p) => (
              <ActionButton
                key={p}
                onClick={() => setSelectedPriority(p)}
                className={
                  selectedPriority === p ? 'bg-blue-600' : 'bg-gray-600'
                }
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </ActionButton>
            ))}
          </div>
        </div>
      </div>

      {bugReportsError && (
        <Card>
          <ErrorAlert
            message={`Failed to load bug reports: ${bugReportsError}`}
          />
        </Card>
      )}

      {bugReportsData && (
        <Card>
          <SectionHeader
            title={`${
              selectedStatus === 'all'
                ? 'All'
                : selectedStatus.charAt(0).toUpperCase() +
                  selectedStatus.slice(1)
            } Bug Reports`}
          />
          {bugReports.length === 0 ? (
            <p className="text-gray-400 text-center py-8">
              No bug reports found.
            </p>
          ) : (
            <>
              <div className="space-y-4">
                {bugReports.map((bugReport) => (
                  <div
                    key={bugReport.id}
                    className="border border-gray-700 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-200">
                          #{bugReport.id} - {bugReport.title}
                        </h3>
                        <p className="text-gray-400">
                          Reported by{' '}
                          {bugReport.reporter_username || 'Anonymous'} on{' '}
                          {new Date(bugReport.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        {getStatusBadge(bugReport.status)}
                        {getPriorityBadge(bugReport.priority)}
                        {(bugReport.status === 'pending' ||
                          bugReport.status === 'in_progress') && (
                          <ActionButton
                            onClick={() => openReviewDialog(bugReport)}
                            className="text-sm px-3 py-1"
                          >
                            Review
                          </ActionButton>
                        )}
                      </div>
                    </div>

                    <div className="mb-3">
                      <h4 className="font-medium text-gray-300 mb-1">
                        Description
                      </h4>
                      <p className="text-gray-400">{bugReport.description}</p>
                    </div>

                    {bugReport.steps_to_reproduce && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Steps to Reproduce
                        </h4>
                        <p className="text-gray-400">
                          {bugReport.steps_to_reproduce}
                        </p>
                      </div>
                    )}

                    {bugReport.expected_behavior && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Expected Behavior
                        </h4>
                        <p className="text-gray-400">
                          {bugReport.expected_behavior}
                        </p>
                      </div>
                    )}

                    {bugReport.actual_behavior && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Actual Behavior
                        </h4>
                        <p className="text-gray-400">
                          {bugReport.actual_behavior}
                        </p>
                      </div>
                    )}

                    {(bugReport.browser_info || bugReport.device_info) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                        {bugReport.browser_info && (
                          <div>
                            <h4 className="font-medium text-gray-300 mb-1">
                              Browser Info
                            </h4>
                            <p className="text-gray-400">
                              {bugReport.browser_info}
                            </p>
                          </div>
                        )}
                        {bugReport.device_info && (
                          <div>
                            <h4 className="font-medium text-gray-300 mb-1">
                              Device Info
                            </h4>
                            <p className="text-gray-400">
                              {bugReport.device_info}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {bugReport.screenshot_url && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Screenshot
                        </h4>
                        <img
                          src={bugReport.screenshot_url}
                          alt="Bug screenshot"
                          className="max-w-full h-auto rounded border border-gray-700"
                        />
                      </div>
                    )}

                    {bugReport.admin_notes && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Admin Notes
                        </h4>
                        <p className="text-gray-400">{bugReport.admin_notes}</p>
                      </div>
                    )}

                    {bugReport.assignee_username && (
                      <div className="text-sm text-gray-500">
                        Assigned to {bugReport.assignee_username}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {pagination &&
                typeof pagination === 'object' &&
                'current_page' in pagination &&
                'total_pages' in pagination &&
                'total_items' in pagination && (
                  <Pagination
                    currentPage={
                      typeof pagination.current_page === 'number'
                        ? pagination.current_page
                        : 1
                    }
                    totalPages={
                      typeof pagination.total_pages === 'number'
                        ? pagination.total_pages
                        : 1
                    }
                    onPageChange={setCurrentPage}
                    itemsPerPage={ADMIN_ITEMS_PER_PAGE}
                    totalItems={
                      typeof pagination.total_items === 'number'
                        ? pagination.total_items
                        : 0
                    }
                  />
                )}
            </>
          )}
        </Card>
      )}

      {/* Review Dialog */}
      <Dialog
        isOpen={isReviewDialogOpen}
        onClose={closeReviewDialog}
        title={`Review Bug Report #${selectedBugReport?.id}`}
      >
        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-300 mb-2">
              Bug Report Details
            </h4>
            <div className="bg-gray-800 p-3 rounded">
              <p>
                <strong>Title:</strong> {selectedBugReport?.title}
              </p>
              <p>
                <strong>Description:</strong> {selectedBugReport?.description}
              </p>
              <p>
                <strong>Reporter:</strong>{' '}
                {selectedBugReport?.reporter_username || 'Anonymous'}
              </p>
            </div>
          </div>

          <div>
            <label
              htmlFor="priority"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Priority
            </label>
            <select
              id="priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full p-2 bg-gray-800 border border-gray-600 rounded text-gray-200"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="admin_notes"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Admin Notes
            </label>
            <textarea
              id="admin_notes"
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              className="w-full p-2 bg-gray-800 border border-gray-600 rounded text-gray-200"
              rows={4}
              placeholder="Add notes about your decision..."
            />
          </div>

          {updateError && <ErrorAlert message={updateError} />}

          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeReviewDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateBugReport('in_progress')}
              className="bg-blue-600 hover:bg-blue-700"
              disabled={isUpdating}
            >
              Mark In Progress
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateBugReport('dismissed')}
              className="bg-gray-600 hover:bg-gray-700"
              disabled={isUpdating}
            >
              Dismiss
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateBugReport('resolved')}
              className="bg-green-600 hover:bg-green-700"
              disabled={isUpdating}
            >
              Resolve
            </ActionButton>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

export default BugReportReview;
