import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListsApi, buildLogsApi } from '../../services/Api';
import type {
  BuildListRead,
  BuildLogPostRead,
  BuildLogReadPaginated,
} from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import ImageUpload from '../../components/common/ImageUpload';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import Pagination from '../../components/common/Pagination';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';
import { BUILD_LOG_POSTS_PER_PAGE } from '../../constants';

const fetchBuildLogRequestFn = (buildListId: string, page: number = 1) => {
  const skip = (page - 1) * BUILD_LOG_POSTS_PER_PAGE;
  return buildLogsApi.getBuildLogByBuildList(
    Number(buildListId),
    skip,
    BUILD_LOG_POSTS_PER_PAGE
  );
};

const fetchBuildListRequestFn = (buildListId: string) =>
  buildListsApi.getBuildList(Number(buildListId));

function ViewBuildLog() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();

  const [buildList, setBuildList] = useState<BuildListRead | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [postToDelete, setPostToDelete] = useState<BuildLogPostRead | null>(
    null
  );
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [postToEdit, setPostToEdit] = useState<BuildLogPostRead | null>(null);
  const [editContent, setEditContent] = useState('');
  const editTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newPostContent, setNewPostContent] = useState('');
  const createTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const fetchBuildLogWithPage = useCallback(
    (buildListId: string) => {
      return fetchBuildLogRequestFn(buildListId, currentPage);
    },
    [currentPage]
  );

  const buildLogResponse = useApiRequest(fetchBuildLogWithPage);
  const buildLog = buildLogResponse.data as BuildLogReadPaginated | undefined;
  const isLoadingBuildLog = buildLogResponse.isLoading;
  const buildLogError = buildLogResponse.error;
  const fetchBuildLog = buildLogResponse.executeRequest;

  const {
    data: buildListData,
    isLoading: isLoadingBuildList,
    executeRequest: fetchBuildList,
  } = useApiRequest(fetchBuildListRequestFn);

  useEffect(() => {
    if (buildListId) {
      void fetchBuildLog(buildListId);
      void fetchBuildList(buildListId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildListId, currentPage]);

  useEffect(() => {
    if (buildListData) {
      setBuildList(buildListData);
    }
  }, [buildListData]);

  const handleCreatePost = async () => {
    if (!buildListId || !newPostContent.trim()) return;

    try {
      await buildLogsApi.createBuildLogPost(Number(buildListId), {
        content: newPostContent.trim(),
      });
      setNewPostContent('');
      setIsCreateDialogOpen(false);
      // Reset to first page after creating a post - this will trigger useEffect to refetch
      if (currentPage !== 1) {
        setCurrentPage(1);
      } else if (buildListId) {
        // If already on page 1, manually refetch
        void fetchBuildLog(buildListId);
      }
    } catch (error) {
      console.error('Failed to create post:', error);
    }
  };

  const handleEditPost = async () => {
    if (!buildListId || !postToEdit || !editContent.trim()) return;

    try {
      await buildLogsApi.updateBuildLogPost(postToEdit.id, {
        content: editContent.trim(),
      });
      setIsEditDialogOpen(false);
      setPostToEdit(null);
      setEditContent('');
      void fetchBuildLog(buildListId);
    } catch (error) {
      console.error('Failed to update post:', error);
    }
  };

  const handleDeletePost = async () => {
    if (!buildListId || !postToDelete) return;

    try {
      await buildLogsApi.deleteBuildLogPost(postToDelete.id);
      setIsDeleteConfirmOpen(false);
      setPostToDelete(null);
      // If we deleted the last post on the page and it's not page 1, go to previous page
      // This will trigger useEffect to refetch
      if (buildLog && buildLog.posts.length === 1 && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else if (buildListId) {
        // Otherwise just refetch current page
        void fetchBuildLog(buildListId);
      }
    } catch (error) {
      console.error('Failed to delete post:', error);
    }
  };

  const openEditDialog = (post: BuildLogPostRead) => {
    setPostToEdit(post);
    setEditContent(post.content);
    setIsEditDialogOpen(true);
  };

  const openDeleteDialog = (post: BuildLogPostRead) => {
    setPostToDelete(post);
    setIsDeleteConfirmOpen(true);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const insertImageMarkdown = (
    imageUrl: string,
    textareaRef: React.RefObject<HTMLTextAreaElement | null>,
    contentSetter: (value: string) => void,
    currentContent: string
  ) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      // If no textarea ref, just append to the end
      contentSetter(currentContent + `\n\n![Image](${imageUrl})\n`);
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const textBefore = currentContent.substring(0, start);
    const textAfter = currentContent.substring(end);
    const imageMarkdown = `![Image](${imageUrl})`;

    // Insert image markdown at cursor position, or at end if no selection
    const newContent = textBefore + imageMarkdown + textAfter;
    contentSetter(newContent);

    // Set cursor position after the inserted image markdown
    setTimeout(() => {
      const newCursorPos = start + imageMarkdown.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
      textarea.focus();
    }, 0);
  };

  const handleImageUploaded = (_fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the create post textarea
    insertImageMarkdown(
      presignedUrl,
      createTextareaRef,
      setNewPostContent,
      newPostContent
    );
  };

  const handleEditImageUploaded = (_fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the edit post textarea
    insertImageMarkdown(
      presignedUrl,
      editTextareaRef,
      setEditContent,
      editContent
    );
  };

  if (isLoadingBuildLog || isLoadingBuildList) {
    return (
      <>
        <PageHeader title="Build Log" />
        <LoadingSpinner />
      </>
    );
  }

  if (buildLogError) {
    return (
      <div>
        <PageHeader title="Build Log" />
        <Card>
          <ErrorAlert message={`Failed to load build log. ${buildLogError}`} />
        </Card>
      </div>
    );
  }

  if (!buildLog) {
    return (
      <div>
        <PageHeader title="Build Log" />
        <Card>
          <ErrorAlert
            message={`Build log for build list "${buildListId}" not found.`}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title={
          buildList
            ? buildList.name
            : (buildLog?.title || '').replace('Build Log: ', '')
        }
      />
      {buildList && (
        <div className="mb-4">
          <ParentNavigationLink
            linkTo={`/build-lists/${buildList.id}`}
            linkText="← Back to Build List"
          />
        </div>
      )}

      <Card className="mb-6">
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Build Log Thread" />
          {currentUser && (
            <ActionButton
              onClick={() => setIsCreateDialogOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              New Post
            </ActionButton>
          )}
        </div>

        {buildLog && buildLog.posts.length === 0 ? (
          <div className="text-center py-12 text-gray-200">
            <p className="text-lg mb-2">No posts yet.</p>
            <p className="text-sm text-gray-300">
              {currentUser
                ? 'Be the first to post in this build log!'
                : 'Log in to post in this build log.'}
            </p>
          </div>
        ) : buildLog ? (
          <>
            {/* Pagination at top */}
            {'pagination' in buildLog &&
              buildLog.pagination &&
              buildLog.pagination.total_pages > 1 && (
                <div className="mb-6">
                  <Pagination
                    currentPage={buildLog.pagination.current_page}
                    totalPages={buildLog.pagination.total_pages}
                    onPageChange={(page) => {
                      setCurrentPage(page);
                      // Scroll to top when page changes
                      window.scrollTo({ top: 0, behavior: 'smooth' });
                    }}
                    itemsPerPage={buildLog.pagination.items_per_page}
                    totalItems={buildLog.pagination.total_items}
                  />
                </div>
              )}

            <div className="space-y-4">
              {buildLog.posts.map((post: BuildLogPostRead) => {
                const canEdit = currentUser && currentUser.id === post.user_id;
                const canDelete =
                  currentUser &&
                  (currentUser.id === post.user_id ||
                    (buildList && currentUser.id === buildList.user_id));
                const isEdited = post.created_at !== post.updated_at;

                return (
                  <Card key={post.id} className="bg-gray-800/50">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          {post.author_image_url ? (
                            <img
                              src={post.author_image_url}
                              alt={post.author_username || 'User'}
                              className="w-10 h-10 rounded object-cover flex-shrink-0"
                            />
                          ) : (
                            <div className="w-10 h-10 rounded bg-gray-700 flex items-center justify-center flex-shrink-0">
                              <span className="text-lg text-gray-200">
                                {(post.author_username || 'U')
                                  .charAt(0)
                                  .toUpperCase()}
                              </span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-indigo-400">
                              {post.author_username || 'Unknown User'}
                            </span>
                            <span className="text-gray-300 text-sm">
                              {formatDate(post.created_at)}
                            </span>
                            {isEdited && (
                              <span className="text-gray-300 text-xs italic">
                                (edited)
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-gray-200 prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown
                            components={{
                              p: ({ children }) => (
                                <p className="mb-2 last:mb-0 text-gray-200">
                                  {children}
                                </p>
                              ),
                              h1: ({ children }) => (
                                <h1 className="text-2xl font-bold mb-2 mt-4 first:mt-0 text-gray-100">
                                  {children}
                                </h1>
                              ),
                              h2: ({ children }) => (
                                <h2 className="text-xl font-bold mb-2 mt-4 first:mt-0 text-gray-100">
                                  {children}
                                </h2>
                              ),
                              h3: ({ children }) => (
                                <h3 className="text-lg font-bold mb-2 mt-4 first:mt-0 text-gray-200">
                                  {children}
                                </h3>
                              ),
                              ul: ({ children }) => (
                                <ul className="list-disc list-inside mb-2 space-y-1 text-gray-200">
                                  {children}
                                </ul>
                              ),
                              ol: ({ children }) => (
                                <ol className="list-decimal list-inside mb-2 space-y-1 text-gray-200">
                                  {children}
                                </ol>
                              ),
                              li: ({ children }) => (
                                <li className="ml-4 text-gray-200">
                                  {children}
                                </li>
                              ),
                              code: ({ children, className }) => {
                                const isInline = !className;
                                return isInline ? (
                                  <code className="bg-gray-700 px-1 py-0.5 rounded text-sm font-mono text-gray-100">
                                    {children}
                                  </code>
                                ) : (
                                  <code className="block bg-gray-700 p-2 rounded text-sm font-mono overflow-x-auto text-gray-100">
                                    {children}
                                  </code>
                                );
                              },
                              pre: ({ children }) => (
                                <pre className="bg-gray-700 p-2 rounded mb-2 overflow-x-auto text-gray-100">
                                  {children}
                                </pre>
                              ),
                              blockquote: ({ children }) => (
                                <blockquote className="border-l-4 border-indigo-500 pl-4 italic my-2 text-gray-200">
                                  {children}
                                </blockquote>
                              ),
                              a: ({ href, children }) => (
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-indigo-400 hover:text-indigo-300 underline"
                                >
                                  {children}
                                </a>
                              ),
                              img: ({ src, alt }) => (
                                <img
                                  src={src}
                                  alt={alt || 'Image'}
                                  className="max-w-full h-auto rounded-lg my-2"
                                />
                              ),
                              strong: ({ children }) => (
                                <strong className="font-bold text-gray-100">
                                  {children}
                                </strong>
                              ),
                              em: ({ children }) => (
                                <em className="italic text-gray-200">
                                  {children}
                                </em>
                              ),
                            }}
                          >
                            {post.content}
                          </ReactMarkdown>
                        </div>
                      </div>
                      {(canEdit || canDelete) && (
                        <div className="flex gap-2 ml-4">
                          {canEdit && (
                            <button
                              type="button"
                              onClick={() => openEditDialog(post)}
                              className="text-indigo-400 hover:text-indigo-300 text-sm"
                            >
                              Edit
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              onClick={() => openDeleteDialog(post)}
                              className="text-red-400 hover:text-red-300 text-sm"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
            {'pagination' in buildLog &&
              buildLog.pagination &&
              buildLog.pagination.total_pages > 1 && (
                <Pagination
                  currentPage={buildLog.pagination.current_page}
                  totalPages={buildLog.pagination.total_pages}
                  onPageChange={(page) => {
                    setCurrentPage(page);
                    // Scroll to top when page changes
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  itemsPerPage={buildLog.pagination.items_per_page}
                  totalItems={buildLog.pagination.total_items}
                />
              )}
          </>
        ) : null}
      </Card>

      {/* Create Post Dialog */}
      {currentUser && (
        <Dialog
          isOpen={isCreateDialogOpen}
          onClose={() => {
            setIsCreateDialogOpen(false);
            setNewPostContent('');
          }}
          title="New Post"
          maxWidth="4xl"
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="post-content"
                className="block text-sm font-medium text-gray-200 mb-2"
              >
                Post Content (Markdown supported)
              </label>
              <textarea
                id="post-content"
                ref={createTextareaRef}
                value={newPostContent}
                onChange={(e) => setNewPostContent(e.target.value)}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                rows={12}
                placeholder="Share your build progress, ask questions, or provide updates...

Markdown examples:
**bold text**
*italic text*
# Heading
- List item
[Link text](https://example.com)
![Image](image-url)
`code`"
              />
              <p className="text-xs text-gray-300 mt-1">
                Markdown formatting is supported. Use **bold**, *italic*, #
                headings, - lists, and more.
              </p>
            </div>
            <div>
              <ImageUpload
                entityType="build_log_post"
                entityId={buildListId ? Number(buildListId) : 0}
                onImageUploaded={handleImageUploaded}
                label="Upload Image"
                maxSizeMB={10}
                showPreview={false}
                className="mb-2"
              />
              <p className="text-xs text-gray-400">
                Upload an image and it will be inserted into your post as
                markdown.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <ActionButton
                onClick={() => {
                  setIsCreateDialogOpen(false);
                  setNewPostContent('');
                }}
                className="bg-gray-600 hover:bg-gray-700 text-white"
              >
                Cancel
              </ActionButton>
              <ActionButton
                onClick={() => void handleCreatePost()}
                disabled={!newPostContent.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                Post
              </ActionButton>
            </div>
          </div>
        </Dialog>
      )}

      {/* Edit Post Dialog */}
      {postToEdit && (
        <Dialog
          isOpen={isEditDialogOpen}
          onClose={() => {
            setIsEditDialogOpen(false);
            setPostToEdit(null);
            setEditContent('');
          }}
          title="Edit Post"
          maxWidth="4xl"
        >
          <div className="space-y-4">
            <div>
              <label
                htmlFor="edit-content"
                className="block text-sm font-medium text-gray-200 mb-2"
              >
                Post Content (Markdown supported)
              </label>
              <textarea
                id="edit-content"
                ref={editTextareaRef}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                rows={12}
              />
              <p className="text-xs text-gray-300 mt-1">
                Markdown formatting is supported. Use **bold**, *italic*, #
                headings, - lists, and more.
              </p>
            </div>
            <div>
              <ImageUpload
                entityType="build_log_post"
                entityId={buildListId ? Number(buildListId) : 0}
                onImageUploaded={handleEditImageUploaded}
                label="Upload Image"
                maxSizeMB={10}
                showPreview={false}
                className="mb-2"
              />
              <p className="text-xs text-gray-400">
                Upload an image and it will be inserted into your post as
                markdown.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <ActionButton
                onClick={() => {
                  setIsEditDialogOpen(false);
                  setPostToEdit(null);
                  setEditContent('');
                }}
                className="bg-gray-600 hover:bg-gray-700 text-white"
              >
                Cancel
              </ActionButton>
              <ActionButton
                onClick={() => void handleEditPost()}
                disabled={!editContent.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                Save
              </ActionButton>
            </div>
          </div>
        </Dialog>
      )}

      {/* Delete Confirmation Dialog */}
      {postToDelete && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={() => {
            setIsDeleteConfirmOpen(false);
            setPostToDelete(null);
          }}
          onConfirm={() => void handleDeletePost()}
          itemName="this post"
          itemType="build log post"
          isProcessing={false}
          error={null}
        />
      )}
    </div>
  );
}

export default ViewBuildLog;
