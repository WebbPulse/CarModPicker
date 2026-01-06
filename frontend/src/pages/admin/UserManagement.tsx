import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { usersApi } from '../../services/Api';
import type { AdminUserUpdate, UserRead } from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import Input from '../../components/common/Input';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const ITEMS_PER_PAGE = 20;

const fetchUsersRequestFn = (params?: { skip?: number; limit?: number }) =>
  usersApi.getAllUsers(params);

const updateUserRequestFn = (payload: {
  userId: number;
  data: AdminUserUpdate;
}) => usersApi.adminUpdateUser(payload.userId, payload.data);

const deleteUserRequestFn = (userId: number) =>
  usersApi.adminDeleteUser(userId);

function UserManagement() {
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserRead | null>(null);
  const [formData, setFormData] = useState<AdminUserUpdate>({
    username: null,
    email: null,
    disabled: null,
    password: null,
    image_url: null,
    is_superuser: null,
    is_admin: null,
    email_verified: null,
    subscription_tier: null,
    subscription_status: null,
    subscription_expires_at: null,
  });

  const {
    data: users,
    isLoading: isLoadingUsers,
    error: usersError,
    executeRequest: fetchUsers,
  } = useApiRequest(fetchUsersRequestFn);

  const {
    isLoading: isUpdating,
    error: updateError,
    executeRequest: executeUpdate,
    setError: setUpdateError,
  } = useApiRequest(updateUserRequestFn);

  const {
    isLoading: isDeleting,
    error: deleteError,
    executeRequest: executeDelete,
    setError: setDeleteError,
  } = useApiRequest(deleteUserRequestFn);

  // Redirect non-admin users
  useEffect(() => {
    if (currentUser && !currentUser.is_admin) {
      void navigate('/');
    }
  }, [currentUser, navigate]);

  useEffect(() => {
    void fetchUsers({
      skip: (currentPage - 1) * ITEMS_PER_PAGE,
      limit: ITEMS_PER_PAGE,
    });
  }, [fetchUsers, currentPage]);

  // Filter users by search term on the frontend
  const filteredUsers = users?.filter(
    (u) =>
      !searchTerm ||
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.id.toString().includes(searchTerm)
  );

  if (!currentUser) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="User Management" />
        <Card>
          <ErrorAlert message="Please log in to access user management." />
        </Card>
      </div>
    );
  }

  if (!currentUser.is_admin) {
    return (
      <div>
        <PageHeader title="User Management" />
        <Card>
          <ErrorAlert message="You do not have permission to access user management." />
        </Card>
      </div>
    );
  }

  const handleUpdateUser = async () => {
    if (!selectedUser) return;

    // Build update data - send all fields, backend will handle partial updates
    const updateData: AdminUserUpdate = {
      username: formData.username || null,
      email: formData.email || null,
      disabled: formData.disabled ?? null,
      is_admin: formData.is_admin ?? null,
      is_superuser: formData.is_superuser ?? null,
      email_verified: formData.email_verified ?? null,
      image_url: formData.image_url || null,
      subscription_tier: formData.subscription_tier || null,
      subscription_status: formData.subscription_status || null,
      subscription_expires_at: formData.subscription_expires_at || null,
    };

    // Only include password if it was changed
    if (formData.password) {
      updateData.password = formData.password;
    }

    const result = await executeUpdate({
      userId: selectedUser.id,
      data: updateData,
    });
    if (result) {
      setIsEditDialogOpen(false);
      setSelectedUser(null);
      setFormData({
        username: null,
        email: null,
        disabled: null,
        password: null,
        image_url: null,
        is_superuser: null,
        is_admin: null,
        email_verified: null,
        subscription_tier: null,
        subscription_status: null,
        subscription_expires_at: null,
      });
      void fetchUsers({
        skip: (currentPage - 1) * ITEMS_PER_PAGE,
        limit: ITEMS_PER_PAGE,
      });
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    const result = await executeDelete(selectedUser.id);
    if (result) {
      setIsDeleteDialogOpen(false);
      setSelectedUser(null);
      void fetchUsers({
        skip: (currentPage - 1) * ITEMS_PER_PAGE,
        limit: ITEMS_PER_PAGE,
      });
    }
  };

  const openEditDialog = (user: UserRead) => {
    setUpdateError(null);
    setSelectedUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      disabled: user.disabled,
      password: null, // Don't populate password
      image_url: user.image_url || null,
      is_superuser: user.is_superuser,
      is_admin: user.is_admin,
      email_verified: user.email_verified,
      subscription_tier: user.subscription_tier,
      subscription_status: user.subscription_status,
      subscription_expires_at: user.subscription_expires_at || null,
    });
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (user: UserRead) => {
    setDeleteError(null);
    setSelectedUser(user);
    setIsDeleteDialogOpen(true);
  };

  const closeEditDialog = () => {
    setIsEditDialogOpen(false);
    setSelectedUser(null);
    setFormData({
      username: null,
      email: null,
      disabled: null,
      password: null,
      image_url: null,
      is_superuser: null,
      is_admin: null,
      email_verified: null,
      subscription_tier: null,
      subscription_status: null,
      subscription_expires_at: null,
    });
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSelectedUser(null);
  };

  const canEditUser = () => {
    // Prevent editing yourself in a way that would lock you out
    return true; // Admin can edit all users, backend will prevent removing own admin
  };

  const canDeleteUser = (user: UserRead) => {
    // Prevent deleting yourself
    return user.id !== currentUser.id;
  };

  if (isLoadingUsers && !users) {
    return (
      <>
        <PageHeader title="User Management" />
        <LoadingSpinner />
      </>
    );
  }

  // Determine if there are more pages (if we got a full page, there might be more)
  const hasMorePages = users && users.length === ITEMS_PER_PAGE;
  const displayUsers = filteredUsers || [];

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="User Management"
        subtitle="View and manage user accounts"
      />

      <div className="flex justify-between items-center mb-4">
        <ActionButton onClick={() => void navigate('/admin')}>
          ← Back to Admin Dashboard
        </ActionButton>
      </div>

      {/* Search */}
      <Card className="mb-4">
        <Input
          id="user-search"
          label="Search Users"
          placeholder="Search by username, email, or ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </Card>

      {usersError && (
        <Card>
          <ErrorAlert message={`Failed to load users: ${usersError}`} />
        </Card>
      )}

      {displayUsers && displayUsers.length > 0 && (
        <Card>
          <SectionHeader title="Users" />
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-gray-700">
                <tr>
                  <th className="p-2 text-gray-300">ID</th>
                  <th className="p-2 text-gray-300">Username</th>
                  <th className="p-2 text-gray-300">Email</th>
                  <th className="p-2 text-gray-300">Status</th>
                  <th className="p-2 text-gray-300">Email Verified</th>
                  <th className="p-2 text-gray-300">Subscription</th>
                  <th className="p-2 text-gray-300">Admin</th>
                  <th className="p-2 text-gray-300">Superuser</th>
                  <th className="p-2 text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayUsers.map((user) => (
                  <tr key={user.id} className="border-b border-gray-800">
                    <td className="p-2 text-gray-200">{user.id}</td>
                    <td className="p-2 text-gray-200">{user.username}</td>
                    <td className="p-2 text-gray-200">{user.email}</td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.disabled
                            ? 'bg-red-600 text-red-100'
                            : 'bg-green-600 text-green-100'
                        }`}
                      >
                        {user.disabled ? 'Disabled' : 'Active'}
                      </span>
                    </td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.email_verified
                            ? 'bg-green-600 text-green-100'
                            : 'bg-yellow-600 text-yellow-100'
                        }`}
                      >
                        {user.email_verified ? 'Verified' : 'Unverified'}
                      </span>
                    </td>
                    <td className="p-2">
                      <div className="flex flex-col gap-1">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            user.subscription_tier === 'premium'
                              ? 'bg-purple-600 text-purple-100'
                              : 'bg-gray-600 text-gray-100'
                          }`}
                        >
                          {user.subscription_tier === 'premium'
                            ? 'Premium'
                            : 'Free'}
                        </span>
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            user.subscription_status === 'active'
                              ? 'bg-green-600 text-green-100'
                              : user.subscription_status === 'cancelled'
                                ? 'bg-yellow-600 text-yellow-100'
                                : 'bg-red-600 text-red-100'
                          }`}
                        >
                          {user.subscription_status}
                        </span>
                      </div>
                    </td>
                    <td className="p-2">
                      {user.is_admin ? (
                        <span className="px-2 py-1 rounded text-xs bg-blue-600 text-blue-100">
                          Admin
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="p-2">
                      {user.is_superuser ? (
                        <span className="px-2 py-1 rounded text-xs bg-purple-600 text-purple-100">
                          Superuser
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="p-2">
                      <div className="flex space-x-2">
                        <ActionButton
                          onClick={() => openEditDialog(user)}
                          className="text-sm px-2 py-1"
                          disabled={!canEditUser()}
                        >
                          Edit
                        </ActionButton>
                        <ActionButton
                          onClick={() => openDeleteDialog(user)}
                          className="text-sm px-2 py-1 bg-red-600 hover:bg-red-700"
                          disabled={!canDeleteUser(user)}
                        >
                          Delete
                        </ActionButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!searchTerm && (
            <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-700">
              <ActionButton
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="text-sm"
              >
                Previous
              </ActionButton>
              <span className="text-gray-400">
                Page {currentPage}
                {hasMorePages && ' (more pages available)'}
              </span>
              <ActionButton
                onClick={() => setCurrentPage((p) => p + 1)}
                disabled={!hasMorePages}
                className="text-sm"
              >
                Next
              </ActionButton>
            </div>
          )}
        </Card>
      )}

      {displayUsers && displayUsers.length === 0 && (
        <Card>
          <SectionHeader title="Users" />
          <p className="text-gray-400 text-center py-8">
            {searchTerm
              ? 'No users found matching your search.'
              : 'No users found.'}
          </p>
        </Card>
      )}

      {/* Edit User Dialog */}
      <Dialog
        isOpen={isEditDialogOpen}
        onClose={closeEditDialog}
        title={`Edit User: ${selectedUser?.username}`}
      >
        <div className="space-y-4">
          <Input
            id="edit-username"
            label="Username"
            value={formData.username || ''}
            onChange={(e) =>
              setFormData({ ...formData, username: e.target.value || null })
            }
            placeholder="Username"
            required
          />
          <Input
            id="edit-email"
            label="Email"
            type="email"
            value={formData.email || ''}
            onChange={(e) =>
              setFormData({ ...formData, email: e.target.value || null })
            }
            placeholder="Email address"
            required
          />
          <Input
            id="edit-password"
            label="New Password (leave empty to keep current)"
            type="password"
            value={formData.password || ''}
            onChange={(e) =>
              setFormData({
                ...formData,
                password: e.target.value || null,
              })
            }
            placeholder="New password"
          />
          <Input
            id="edit-image-url"
            label="Image URL"
            value={formData.image_url || ''}
            onChange={(e) =>
              setFormData({ ...formData, image_url: e.target.value || null })
            }
            placeholder="https://example.com/image.jpg"
          />
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit-disabled"
                checked={formData.disabled ?? false}
                onChange={(e) =>
                  setFormData({ ...formData, disabled: e.target.checked })
                }
                className="rounded"
              />
              <label htmlFor="edit-disabled" className="text-gray-300">
                Disabled
              </label>
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit-email-verified"
                checked={formData.email_verified ?? false}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    email_verified: e.target.checked,
                  })
                }
                className="rounded"
              />
              <label htmlFor="edit-email-verified" className="text-gray-300">
                Email Verified
              </label>
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit-is-admin"
                checked={formData.is_admin ?? false}
                onChange={(e) =>
                  setFormData({ ...formData, is_admin: e.target.checked })
                }
                className="rounded"
                disabled={
                  selectedUser?.id === currentUser.id &&
                  formData.is_admin === true
                }
              />
              <label htmlFor="edit-is-admin" className="text-gray-300">
                Admin
              </label>
              {selectedUser?.id === currentUser.id && (
                <span className="text-xs text-gray-400">
                  (Cannot remove your own admin status)
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="edit-is-superuser"
                checked={formData.is_superuser ?? false}
                onChange={(e) =>
                  setFormData({ ...formData, is_superuser: e.target.checked })
                }
                className="rounded"
                disabled={
                  selectedUser?.id === currentUser.id &&
                  formData.is_superuser === true
                }
              />
              <label htmlFor="edit-is-superuser" className="text-gray-300">
                Superuser
              </label>
              {selectedUser?.id === currentUser.id && (
                <span className="text-xs text-gray-400">
                  (Cannot remove your own superuser status)
                </span>
              )}
            </div>
          </div>
          <div className="space-y-4 pt-4 border-t border-gray-700">
            <SectionHeader title="Subscription Management" />
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="edit-subscription-tier"
                  className="block text-gray-300 mb-2"
                >
                  Subscription Tier
                </label>
                <select
                  id="edit-subscription-tier"
                  value={formData.subscription_tier || 'free'}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      subscription_tier: e.target.value || null,
                    })
                  }
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="free">Free</option>
                  <option value="premium">Premium</option>
                </select>
              </div>
              <div>
                <label
                  htmlFor="edit-subscription-status"
                  className="block text-gray-300 mb-2"
                >
                  Subscription Status
                </label>
                <select
                  id="edit-subscription-status"
                  value={formData.subscription_status || 'active'}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      subscription_status: e.target.value || null,
                    })
                  }
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="active">Active</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="expired">Expired</option>
                </select>
              </div>
              <div>
                <label
                  htmlFor="edit-subscription-expires-at"
                  className="block text-gray-300 mb-2"
                >
                  Expiration Date (optional)
                </label>
                <Input
                  id="edit-subscription-expires-at"
                  type="datetime-local"
                  value={
                    formData.subscription_expires_at
                      ? (() => {
                          // Convert UTC datetime to local datetime for input
                          const date = new Date(
                            formData.subscription_expires_at
                          );
                          const year = date.getFullYear();
                          const month = String(date.getMonth() + 1).padStart(
                            2,
                            '0'
                          );
                          const day = String(date.getDate()).padStart(2, '0');
                          const hours = String(date.getHours()).padStart(
                            2,
                            '0'
                          );
                          const minutes = String(date.getMinutes()).padStart(
                            2,
                            '0'
                          );
                          return `${year}-${month}-${day}T${hours}:${minutes}`;
                        })()
                      : ''
                  }
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      subscription_expires_at: e.target.value
                        ? new Date(e.target.value).toISOString()
                        : null,
                    })
                  }
                  placeholder="Select expiration date"
                />
              </div>
            </div>
          </div>
          {updateError && <ErrorAlert message={updateError} />}
          <div className="flex justify-end space-x-2">
            <ActionButton onClick={closeEditDialog} className="bg-gray-600">
              Cancel
            </ActionButton>
            <ActionButton
              onClick={() => void handleUpdateUser()}
              disabled={isUpdating || !formData.username || !formData.email}
            >
              {isUpdating ? 'Updating...' : 'Update User'}
            </ActionButton>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmationDialog
        isOpen={isDeleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={() => void handleDeleteUser()}
        itemName={selectedUser?.username || 'user'}
        itemType="user"
        isProcessing={isDeleting}
        error={deleteError}
      />
    </div>
  );
}

export default UserManagement;
