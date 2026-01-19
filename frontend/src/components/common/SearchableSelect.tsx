import { useCallback, useEffect, useRef, useState } from 'react';

export interface SearchableSelectOption {
  id: number | string;
  label: string;
  value: number | string | null;
}

interface SearchableSelectProps {
  options: SearchableSelectOption[];
  value: number | string | null;
  onChange: (value: number | string | null) => void;
  placeholder?: string;
  label?: string;
  id?: string;
  name?: string;
  disabled?: boolean;
  isLoading?: boolean;
  emptyMessage?: string;
  filterOptions?: (
    options: SearchableSelectOption[],
    searchText: string
  ) => SearchableSelectOption[];
}

function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = 'Type to search...',
  label,
  id,
  name,
  disabled = false,
  isLoading = false,
  emptyMessage = 'No options found',
  filterOptions: customFilterOptions,
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Find selected option
  const selectedOption = options.find((opt) => opt.value === value) || null;

  // Default filter function - searches in label
  const defaultFilterOptions = (
    opts: SearchableSelectOption[],
    text: string
  ): SearchableSelectOption[] => {
    if (!text.trim()) return opts;
    const lowerText = text.toLowerCase();
    return opts.filter((opt) => opt.label.toLowerCase().includes(lowerText));
  };

  const filterOptionsFn = customFilterOptions || defaultFilterOptions;

  // Filter options based on search text
  const filteredOptions = filterOptionsFn(options, searchText);

  // Handle selection
  const handleSelect = useCallback(
    (selectedValue: number | string | null) => {
      onChange(selectedValue);
      setIsOpen(false);
      setHighlightedIndex(-1);
      // Update search text to show selected option
      const option = options.find((opt) => opt.value === selectedValue);
      if (option) {
        setSearchText(option.label);
      } else {
        setSearchText('');
      }
      inputRef.current?.blur();
    },
    [onChange, options]
  );

  // Update search text when value changes externally
  useEffect(() => {
    if (value === null || value === '') {
      setSearchText('');
    } else if (selectedOption && searchText !== selectedOption.label) {
      // Only update if the search text doesn't match the selected option
      // This prevents clearing user input while typing
      if (!isOpen) {
        setSearchText(selectedOption.label);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, selectedOption, isOpen]); // searchText intentionally excluded to prevent loops

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setHighlightedIndex(-1);
        // Reset search text to selected option when closing
        if (selectedOption) {
          setSearchText(selectedOption.label);
        } else {
          setSearchText('');
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [selectedOption]);

  // Handle keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < filteredOptions.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
      } else if (
        e.key === 'Enter' &&
        highlightedIndex >= 0 &&
        filteredOptions[highlightedIndex]
      ) {
        e.preventDefault();
        handleSelect(filteredOptions[highlightedIndex].value);
      } else if (e.key === 'Escape') {
        setIsOpen(false);
        setHighlightedIndex(-1);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, filteredOptions, highlightedIndex, handleSelect]);

  // Scroll highlighted option into view
  useEffect(() => {
    if (
      highlightedIndex >= 0 &&
      dropdownRef.current &&
      dropdownRef.current.children[highlightedIndex]
    ) {
      const optionElement = dropdownRef.current.children[
        highlightedIndex
      ] as HTMLElement;
      if (optionElement) {
        optionElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newText = e.target.value;
    setSearchText(newText);
    setIsOpen(true);
    setHighlightedIndex(-1);

    // If user clears the input, clear the selection
    if (!newText.trim()) {
      onChange(null);
    }
  };

  const handleInputFocus = () => {
    setIsOpen(true);
    // Clear search text when focusing to allow new search
    if (selectedOption) {
      setSearchText('');
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setSearchText('');
    setIsOpen(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative" ref={containerRef}>
      {/* Label */}
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-neutral-300 mb-2"
        >
          {label}
        </label>
      )}

      {/* Input Container */}
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          name={name}
          type="text"
          value={searchText}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          className="w-full px-5 py-3 bg-gray-800 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all duration-300 ease-out input-modern min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed pr-10"
          autoComplete="off"
        />

        {/* Clear button */}
        {value !== null && value !== '' && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-white/60 hover:text-white transition-colors"
            tabIndex={-1}
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}

        {/* Dropdown arrow */}
        {!value && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none text-white/60">
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && !disabled && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-gray-800 border border-white/20 rounded-xl shadow-lg max-h-60 overflow-auto"
        >
          {isLoading ? (
            <div className="px-4 py-3 text-white/60 text-center">
              Loading...
            </div>
          ) : filteredOptions.length === 0 ? (
            <div className="px-4 py-3 text-white/60 text-center">
              {emptyMessage}
            </div>
          ) : (
            filteredOptions.map((option, index) => (
              <button
                key={option.id}
                type="button"
                onClick={() => handleSelect(option.value)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-700 transition-colors ${
                  option.value === value
                    ? 'bg-primary-500/20 text-primary-400'
                    : 'text-white'
                } ${index === highlightedIndex ? 'bg-gray-700' : ''}`}
                onMouseEnter={() => setHighlightedIndex(index)}
              >
                {option.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default SearchableSelect;
