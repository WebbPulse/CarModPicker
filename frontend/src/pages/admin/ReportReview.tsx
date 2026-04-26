import type { AxiosResponse } from 'axios';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import apiClient, { reportsApi } from '../../services/Api';
import type {
  PaginatedResponse,
  ReportUpdate,
  ReportWithDetails,
} from '../../types/Api';

import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import Pagination from '../../components/ui/pagination';
import Spinner from '../../components/ui/spinner';
import { ADMIN_ITEMS_PER_PAGE } from '../../constants';

const fetchReportsRequestFn = (params?: {
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<AxiosResponse<PaginatedResponse<ReportWithDetails>>> =>
  reportsApi.getReportsWithDetails(params);
const updateReportRequestFn = (payload: {
  reportId: string;
  data: ReportUpdate;
}): Promise<AxiosResponse<ReportWithDetails>> =>
  apiClient.put<ReportWithDetails>(
    `/reports/${payload.reportId}`,
    payload.data
  );
const getPendingReportsCountRequestFn = (): Promise<
  AxiosResponse<PaginatedResponse<ReportWithDetails>>
> => reportsApi.getReportsWithDetails({ status: 'pending', skip: 0, limit: 1 });

function ReportReview() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [selectedStatus, setSelectedStatus] = useState<string>('pending');
  const [currentPage, setCurrentPage] = useState(1);
  const [isReviewDialogOpen, setIsReviewDialogOpen] = useState(false);
  const [selectedReport, setSelectedReport] =
    useState<ReportWithDetails | null>(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [pendingCount, setPendingCount] = useState<number>(0);

  const {
    data: reportsData,
    isLoading: isLoadingReports,
    error: reportsError,
    executeRequest: fetchReports,
  } = useApiRequest<
    PaginatedResponse<ReportWithDetails>,
    {
      status?: string;
      skip?: number;
      limit?: number;
    }
  >(fetchReportsRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateReportRequestFn);

  const { data: countData, executeRequest: fetchPendingCount } = useApiRequest<
    PaginatedResponse<ReportWithDetails>,
    never
  >(getPendingReportsCountRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      void navigate('/');
    }
  }, [user, navigate]);

  // Reset to page 1 when status changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedStatus]);

  useEffect(() => {
    void fetchReports({
      status: selectedStatus,
      skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
      limit: ADMIN_ITEMS_PER_PAGE,
    });
    void fetchPendingCount();
  }, [fetchReports, fetchPendingCount, selectedStatus, currentPage]);

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
        <PageHeader title="Report Review" />
        <Card>
          <ErrorAlert message="Please log in to access report review." />
        </Card>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div>
        <PageHeader title="Report Review" />
        <Card>
          <ErrorAlert message="You do not have permission to access report review." />
        </Card>
      </div>
    );
  }

  const handleUpdateReport = async (status: 'resolved' | 'dismissed') => {
    if (!selectedReport) return;

    const result = await executeUpdate({
      reportId: selectedReport.id,
      data: {
        status,
        admin_notes: adminNotes,
      },
    });

    if (result) {
      setIsReviewDialogOpen(false);
      setSelectedReport(null);
      setAdminNotes('');
      void fetchReports({
        status: selectedStatus,
        skip: (currentPage - 1) * ADMIN_ITEMS_PER_PAGE,
        limit: ADMIN_ITEMS_PER_PAGE,
      });
      void fetchPendingCount();
    }
  };

  const openReviewDialog = (report: ReportWithDetails) => {
    setUpdateError(null);
    setSelectedReport(report);
    setAdminNotes(report.admin_notes || '');
    setIsReviewDialogOpen(true);
  };

  const closeReviewDialog = () => {
    setIsReviewDialogOpen(false);
    setSelectedReport(null);
    setAdminNotes('');
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      pending: { color: 'bg-yellow-600 text-yellow-100', text: 'Pending' },
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

  // Extract reports and pagination info from the response
  const reports: ReportWithDetails[] =
    reportsData && typeof reportsData === 'object' && 'data' in reportsData
      ? Array.isArray(reportsData.data)
        ? reportsData.data
        : []
      : [];
  const pagination =
    reportsData &&
    typeof reportsData === 'object' &&
    'pagination' in reportsData
      ? reportsData.pagination
      : undefined;

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Report Review"
        subtitle="Review and manage reports for all entities"
      />

      <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
        <Button variant="secondary" onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </Button>
        <div className="flex flex-wrap gap-2">
          <Button
            variant={selectedStatus === 'pending' ? 'default' : 'secondary'}
            onClick={() => setSelectedStatus('pending')}
          >
            Pending ({pendingCount})
          </Button>
          <Button
            variant={selectedStatus === 'resolved' ? 'default' : 'secondary'}
            onClick={() => setSelectedStatus('resolved')}
          >
            Resolved
          </Button>
          <Button
            variant={selectedStatus === 'dismissed' ? 'default' : 'secondary'}
            onClick={() => setSelectedStatus('dismissed')}
          >
            Dismissed
          </Button>
        </div>
      </div>

      {reportsError && (
        <Card>
          <ErrorAlert message={`Failed to load reports: ${reportsError}`} />
        </Card>
      )}

      {isLoadingReports && !reportsData ? (
        <Card>
          <div className="flex justify-center items-center py-16">
            <Spinner />
          </div>
        </Card>
      ) : reportsData ? (
        <Card className="relative">
          {isLoadingReports && (
            <div className="absolute inset-0 bg-gray-900/50 backdrop-blur-sm z-10 flex items-center justify-center rounded-lg">
              <Spinner />
            </div>
          )}
          <SectionHeader
            title={`${selectedStatus.charAt(0).toUpperCase() + selectedStatus.slice(1)} Reports`}
          />
          {reports.length === 0 ? (
            <p className="text-gray-400 text-center py-8">
              No {selectedStatus} reports found.
            </p>
          ) : (
            <>
              <div className="space-y-4">
                {reports.map((report) => (
                  <div
                    key={report.id}
                    className="border border-gray-700 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-200">
                          Report #{report.id} - {report.entity_name}
                        </h3>
                        <p className="text-gray-400">
                          Reported by {report.reporter_username} on{' '}
                          {new Date(report.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        {getStatusBadge(report.status)}
                        {report.status === 'pending' && (
                          <Button
                            size="sm"
                            onClick={() => openReviewDialog(report)}
                          >
                            Review
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                      <div>
                        <h4 className="font-medium text-gray-300 mb-1">
                          Reason
                        </h4>
                        <p className="text-gray-400">{report.reason}</p>
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-300 mb-1">
                          Entity Details
                        </h4>
                        <p className="text-gray-400">
                          {report.entity_name}
                          {report.entity_description &&
                            ` - ${report.entity_description}`}
                        </p>
                        <p className="text-gray-500 text-sm">
                          Type: {report.entity_type}
                        </p>
                      </div>
                    </div>

                    {report.description && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Description
                        </h4>
                        <p className="text-gray-400">{report.description}</p>
                      </div>
                    )}

                    {report.admin_notes && (
                      <div className="mb-3">
                        <h4 className="font-medium text-gray-300 mb-1">
                          Admin Notes
                        </h4>
                        <p className="text-gray-400">{report.admin_notes}</p>
                      </div>
                    )}

                    {report.reviewer_username && (
                      <div className="text-sm text-gray-500">
                        Reviewed by {report.reviewer_username} on{' '}
                        {report.reviewed_at &&
                          new Date(report.reviewed_at).toLocaleDateString()}
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
      ) : null}

      {/* Review Dialog */}
      <Dialog
        open={isReviewDialogOpen}
        onOpenChange={(next) => {
          if (!next) closeReviewDialog();
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{`Review Report #${selectedReport?.id ?? ''}`}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
          <div>
            <h4 className="font-medium text-gray-300 mb-2">Report Details</h4>
            <div className="bg-gray-800 p-3 rounded">
              <p>
                <strong>Entity:</strong> {selectedReport?.entity_name} (
                {selectedReport?.entity_type})
              </p>
              <p>
                <strong>Reason:</strong> {selectedReport?.reason}
              </p>
              <p>
                <strong>Reporter:</strong> {selectedReport?.reporter_username}
              </p>
              {selectedReport?.description && (
                <p>
                  <strong>Description:</strong> {selectedReport.description}
                </p>
              )}
            </div>
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
            <Button variant="secondary" onClick={closeReviewDialog}>
              Cancel
            </Button>
            <Button
              variant="secondary"
              onClick={() => void handleUpdateReport('dismissed')}
              disabled={isUpdating}
            >
              Dismiss Report
            </Button>
            <Button
              onClick={() => void handleUpdateReport('resolved')}
              className="bg-green-600 hover:bg-green-700"
              disabled={isUpdating}
            >
              Resolve Report
            </Button>
          </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ReportReview;
