import React, { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import type { ScrapedProductData, Category, Car, GlobalPartCreate, ApiResponse } from '../../types';
import SearchableSelect from '../common/SearchableSelect';

interface PartDialogProps {
  scrapedData: ScrapedProductData;
  onClose: () => void;
  onPartCreated: () => void;
  sendMessage: (message: {
    action: string;
    partData?: GlobalPartCreate;
    imageUrl?: string;
    limit?: number;
    searchTerm?: string;
  }) => Promise<unknown>;
}

const PartDialog: React.FC<PartDialogProps> = ({
  scrapedData,
  onClose,
  onPartCreated,
  sendMessage,
}) => {
  const [formData, setFormData] = useState({
    name: scrapedData.name || '',
    brand: scrapedData.brand || '',
    partNumber: scrapedData.part_number || '',
    description: scrapedData.description || '',
    price: scrapedData.price ? (scrapedData.price / 100).toFixed(2) : '',
    url: scrapedData.product_url || '',
    imageUrl: scrapedData.image_url || '',
    categoryId: null as number | string | null,
    carId: null as number | string | null,
  });

  const [categories, setCategories] = useState<Category[]>([]);
  const [cars, setCars] = useState<Car[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [imagePreview, setImagePreview] = useState(scrapedData.image_url || '');

  useEffect(() => {
    loadCategories();
    loadCars();
  }, []);

  useEffect(() => {
    if (formData.imageUrl) {
      setImagePreview(formData.imageUrl);
    }
  }, [formData.imageUrl]);

  const loadCategories = async () => {
    try {
      const response = (await sendMessage({
        action: 'getCategories',
      })) as ApiResponse<Category[]>;
      
      if (response.success && Array.isArray(response.data)) {
        setCategories(response.data.filter((cat) => cat.is_active));
      }
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  const loadCars = async () => {
    try {
      const response = (await sendMessage({
        action: 'getCars',
        limit: 1000,
      })) as ApiResponse<Car[]>;
      
      if (response.success && Array.isArray(response.data)) {
        setCars(response.data);
      }
    } catch (error) {
      console.error('Failed to load cars:', error);
    }
  };

  const searchCars = async (searchTerm: string): Promise<Car[]> => {
    if (!searchTerm || searchTerm.length <= 2) {
      return cars;
    }

    try {
      const response = (await sendMessage({
        action: 'searchCars',
        searchTerm,
      })) as ApiResponse<Car[]>;
      
      if (response.success && Array.isArray(response.data)) {
        return response.data;
      }
    } catch (error) {
      console.error('Failed to search cars:', error);
    }
    
    return [];
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (!formData.name.trim()) {
        setError('Part name is required');
        setIsLoading(false);
        return;
      }

      if (!formData.categoryId) {
        setError('Category is required');
        setIsLoading(false);
        return;
      }

      const partData: GlobalPartCreate = {
        name: formData.name.trim(),
        description: formData.description.trim() || null,
        price: formData.price ? Math.round(parseFloat(formData.price) * 100) : null,
        product_url: formData.url.trim() || null,
        category_id: parseInt(formData.categoryId.toString()),
        car_id: formData.carId ? parseInt(formData.carId.toString()) : null,
        brand: formData.brand.trim() || null,
        part_number: formData.partNumber.trim() || null,
        image_url: null,
      };

      // Upload image if provided
      if (formData.imageUrl.trim()) {
        const imageResult = (await sendMessage({
          action: 'uploadImage',
          imageUrl: formData.imageUrl.trim(),
        })) as ApiResponse<{ fileKey: string }>;

        if (imageResult.success && imageResult.data) {
          partData.image_url = imageResult.data.fileKey;
        } else {
          console.warn('Image upload failed:', imageResult.error);
        }
      }

      // Create part
      const response = (await sendMessage({
        action: 'createGlobalPart',
        partData,
      })) as ApiResponse<unknown>;

      if (response.success) {
        onPartCreated();
      } else {
        setError(response.error || 'Failed to create part');
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create part');
    } finally {
      setIsLoading(false);
    }
  };

  const categoryOptions = categories.map((cat) => ({
    id: cat.id,
    label: cat.display_name || cat.name,
    value: cat.id,
  }));

  const carOptions = cars.map((car) => ({
    id: car.id,
    label: `${car.make} ${car.model} ${car.generation_name} (${car.start_year}${car.end_year ? `-${car.end_year}` : ''})`,
    value: car.id,
  }));

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-neutral-900/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="shrink-0 p-6 border-b border-white/10">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-gradient">Create Part</h2>
            <button
              type="button"
              onClick={onClose}
              className="text-neutral-400 hover:text-white text-2xl leading-none p-2 hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-110"
              aria-label="Close dialog"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {error && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-xl text-red-200 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Part Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Brand
              </label>
              <input
                type="text"
                value={formData.brand}
                onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Part Number
              </label>
              <input
                type="text"
                value={formData.partNumber}
                onChange={(e) => setFormData({ ...formData, partNumber: e.target.value })}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed resize-y"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Price ($)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Product URL
              </label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
            </div>

            <div>
              <SearchableSelect
                options={categoryOptions}
                value={formData.categoryId}
                onChange={(value) => setFormData({ ...formData, categoryId: value })}
                placeholder="Select a category..."
                label="Category *"
                disabled={isLoading}
                emptyMessage="No categories found"
              />
            </div>

            <div>
              <SearchableSelect
                options={carOptions}
                value={formData.carId}
                onChange={(value) => setFormData({ ...formData, carId: value })}
                placeholder="None"
                label="Car Model (Optional)"
                disabled={isLoading}
                emptyMessage="No cars found"
                filterOptions={async (options, searchText) => {
                  if (!searchText || searchText.length <= 2) {
                    return options;
                  }
                  const searchResults = await searchCars(searchText);
                  return searchResults.map((car) => ({
                    id: car.id,
                    label: `${car.make} ${car.model} ${car.generation_name} (${car.start_year}${car.end_year ? `-${car.end_year}` : ''})`,
                    value: car.id,
                  }));
                }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Image URL
              </label>
              <input
                type="url"
                value={formData.imageUrl}
                onChange={(e) => setFormData({ ...formData, imageUrl: e.target.value })}
                className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px placeholder:text-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading}
              />
              {imagePreview && (
                <div className="mt-3 text-center">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="max-w-full max-h-48 rounded-lg border border-white/20 mx-auto"
                    onError={() => setImagePreview('')}
                  />
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white transition-all duration-300 backdrop-blur-[15px] hover:bg-linear-to-br hover:from-white/20 hover:to-white/10 hover:border-white/30 hover:-translate-y-[3px] hover:shadow-[0_10px_25px_rgba(0,0,0,0.2)] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                disabled={isLoading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 py-3 px-6 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                disabled={isLoading}
              >
                {isLoading ? 'Creating...' : 'Create Part'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PartDialog;
