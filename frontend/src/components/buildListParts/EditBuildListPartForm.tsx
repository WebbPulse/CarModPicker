import React, { useEffect, useState } from 'react';
import type {
  BuildListPartReadWithGlobalPart,
  BuildListPartUpdate,
  BuildListPhaseRead,
} from '../../types/Api';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';
import Dialog from '../common/Dialog';

interface EditBuildListPartFormProps {
  buildListPart: BuildListPartReadWithGlobalPart;
  phases: BuildListPhaseRead[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (
    buildListPartId: string,
    data: BuildListPartUpdate
  ) => Promise<void>;
  loading?: boolean;
}

const EditBuildListPartForm: React.FC<EditBuildListPartFormProps> = ({
  buildListPart,
  phases,
  isOpen,
  onClose,
  onSubmit,
  loading = false,
}) => {
  const [notes, setNotes] = useState(buildListPart.notes || '');
  const [quantity, setQuantity] = useState(buildListPart.quantity ?? 1);
  const [phaseId, setPhaseId] = useState<string | null>(
    buildListPart.build_list_phase_id ?? null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNotes(buildListPart.notes || '');
      setQuantity(buildListPart.quantity ?? 1);
      setPhaseId(buildListPart.build_list_phase_id ?? null);
      setError(null);
    }
  }, [
    isOpen,
    buildListPart.notes,
    buildListPart.quantity,
    buildListPart.build_list_phase_id,
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    void onSubmit(buildListPart.id, {
      notes: notes || null,
      quantity: Math.max(1, quantity),
      build_list_phase_id: phaseId,
    })
      .then(() => onClose())
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to update part');
      });
  };

  const handleClose = () => {
    setNotes(buildListPart.notes || '');
    setQuantity(buildListPart.quantity ?? 1);
    setPhaseId(buildListPart.build_list_phase_id ?? null);
    setError(null);
    onClose();
  };

  return (
    <Dialog isOpen={isOpen} onClose={handleClose} title="Edit Part">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">
            {buildListPart.global_part.name}
          </h3>
          <p className="text-gray-400 text-sm mb-4">
            Update quantity and notes for this part in your build list.
          </p>
        </div>

        <div>
          <label
            htmlFor="edit-part-quantity"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Quantity
          </label>
          <input
            id="edit-part-quantity"
            type="number"
            min={1}
            max={999}
            value={quantity}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!Number.isNaN(v) && v >= 1) setQuantity(v);
            }}
            className="mt-1 block w-24 px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
        </div>

        {phases.length > 0 && (
          <div>
            <label
              htmlFor="edit-part-phase"
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Phase
            </label>
            <select
              id="edit-part-phase"
              value={phaseId ?? ''}
              onChange={(e) => {
                const v = e.target.value;
                setPhaseId(v === '' ? null : v);
              }}
              className="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            >
              <option value="">None</option>
              {phases
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((phase) => (
                  <option key={phase.id} value={phase.id}>
                    {phase.name}
                  </option>
                ))}
            </select>
          </div>
        )}

        <div>
          <label
            htmlFor="notes"
            className="block text-sm font-medium text-gray-300 mb-2"
          >
            Notes
          </label>
          <textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add your notes about this part..."
            rows={4}
            className="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-white"
          />
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded p-2">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-4">
          <SecondaryButton
            type="button"
            onClick={handleClose}
            disabled={loading}
          >
            Cancel
          </SecondaryButton>
          <ActionButton type="submit" disabled={loading}>
            {loading ? 'Saving...' : 'Save'}
          </ActionButton>
        </div>
      </form>
    </Dialog>
  );
};

export default EditBuildListPartForm;
