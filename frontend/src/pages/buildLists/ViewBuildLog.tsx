import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { buildListsApi, buildLogsApi } from '../../services/Api';
import type {
  BuildListRead,
  BuildLogPostRead
} from '../../types/Api';

import ActionButton from '../../components/buttons/ActionButton';
import { ErrorAlert } from '../../components/common/Alerts';
import Card from '../../components/common/Card';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import Dialog from '../../components/common/Dialog';
import ImageUpload from '../../components/common/ImageUpload';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import PageHeader from '../../components/layout/PageHeader';
import SectionHeader from '../../components/layout/SectionHeader';

const fetchBuildLogRequestFn = (buildListId: string) =>
  buildLogsApi.getBuildLogByBuildList(Number(buildListId));

const fetchBuildListRequestFn = (buildListId: string) =>
  buildListsApi.getBuildList(Number(buildListId));

function ViewBuildLog() {
  const { buildListId } = useParams<{ buildListId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [buildList, setBuildList] = useState<BuildListRead | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [postToDelete, setPostToDelete] = useState<BuildLogPostRead | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [postToEdit, setPostToEdit] = useState<BuildLogPostRead | null>(null);
  const [editContent, setEditContent] = useState('');
  const editTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newPostContent, setNewPostContent] = useState('');
  const createTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const {
    data: buildLog,
    isLoading: isLoadingBuildLog,
    error: buildLogError,
    executeRequest: fetchBuildLog,
  } = useApiRequest(fetchBuildLogRequestFn);

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
  }, [buildListId, fetchBuildLog, fetchBuildList]);

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
      void fetchBuildLog(buildListId);
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
      void fetchBuildLog(buildListId);
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
    textareaRef: React.RefObject<HTMLTextAreaElement>,
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

  const handleImageUploaded = (fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the create post textarea
    insertImageMarkdown(presignedUrl, createTextareaRef, setNewPostContent, newPostContent);
  };

  const handleEditImageUploaded = (fileKey: string, presignedUrl: string) => {
    // Insert image markdown into the edit post textarea
    insertImageMarkdown(presignedUrl, editTextareaRef, setEditContent, editContent);
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
          <ErrorAlert
            message={`Failed to load build log. ${buildLogError}`}
          />
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
        title={buildList ? buildList.name : buildLog.title.replace('Build Log: ', '')}
        subtitle={
          buildList ? (
            <>
              <ParentNavigationLink
                linkTo={`/build-lists/${buildList.id}`}
                linkText="← Back to Build List"
              />
            </>
          ) : (
            'Loading build list...'
          )
        }
      />

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

        {buildLog.posts.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">No posts yet.</p>
            <p className="text-sm">
              {currentUser
                ? 'Be the first to post in this build log!'
                : 'Log in to post in this build log.'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {buildLog.posts.map((post) => {
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
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-semibold text-indigo-400">
                          {post.author_username || 'Unknown User'}
                        </span>
                        <span className="text-gray-500 text-sm">
                          {formatDate(post.created_at)}
                        </span>
                        {isEdited && (
                          <span className="text-gray-500 text-xs italic">
                            (edited)
                          </span>
                        )}
                      </div>
                      <div className="text-gray-300 prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => (
                              <p className="mb-2 last:mb-0">{children}</p>
                            ),
                            h1: ({ children }) => (
                              <h1 className="text-2xl font-bold mb-2 mt-4 first:mt-0">
                                {children}
                              </h1>
                            ),
                            h2: ({ children }) => (
                              <h2 className="text-xl font-bold mb-2 mt-4 first:mt-0">
                                {children}
                              </h2>
                            ),
                            h3: ({ children }) => (
                              <h3 className="text-lg font-bold mb-2 mt-4 first:mt-0">
                                {children}
                              </h3>
                            ),
                            ul: ({ children }) => (
                              <ul className="list-disc list-inside mb-2 space-y-1">
                                {children}
                              </ul>
                            ),
                            ol: ({ children }) => (
                              <ol className="list-decimal list-inside mb-2 space-y-1">
                                {children}
                              </ol>
                            ),
                            li: ({ children }) => (
                              <li className="ml-4">{children}</li>
                            ),
                            code: ({ children, className }) => {
                              const isInline = !className;
                              return isInline ? (
                                <code className="bg-gray-700 px-1 py-0.5 rounded text-sm font-mono">
                                  {children}
                                </code>
                              ) : (
                                <code className="block bg-gray-700 p-2 rounded text-sm font-mono overflow-x-auto">
                                  {children}
                                </code>
                              );
                            },
                            pre: ({ children }) => (
                              <pre className="bg-gray-700 p-2 rounded mb-2 overflow-x-auto">
                                {children}
                              </pre>
                            ),
                            blockquote: ({ children }) => (
                              <blockquote className="border-l-4 border-indigo-500 pl-4 italic my-2">
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
                              <strong className="font-bold">{children}</strong>
                            ),
                            em: ({ children }) => (
                              <em className="italic">{children}</em>
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
        )}
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
                className="block text-sm font-medium text-gray-300 mb-2"
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
              <p className="text-xs text-gray-400 mt-1">
                Markdown formatting is supported. Use **bold**, *italic*, # headings, - lists, and more.
              </p>
            </div>
            <div>
              <ImageUpload
                entityType="build_log_post"
                entityId={buildListId ? Number(buildListId) : undefined}
                onImageUploaded={handleImageUploaded}
                label="Upload Image"
                maxSizeMB={10}
                showPreview={false}
                className="mb-2"
              />
              <p className="text-xs text-gray-400">
                Upload an image and it will be inserted into your post as markdown.
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
                className="block text-sm font-medium text-gray-300 mb-2"
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
              <p className="text-xs text-gray-400 mt-1">
                Markdown formatting is supported. Use **bold**, *italic*, # headings, - lists, and more.
              </p>
            </div>
            <div>
              <ImageUpload
                entityType="build_log_post"
                entityId={buildListId ? Number(buildListId) : undefined}
                onImageUploaded={handleEditImageUploaded}
                label="Upload Image"
                maxSizeMB={10}
                showPreview={false}
                className="mb-2"
              />
              <p className="text-xs text-gray-400">
                Upload an image and it will be inserted into your post as markdown.
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
