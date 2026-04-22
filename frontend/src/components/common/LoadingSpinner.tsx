import React from 'react';

interface LoadingSpinnerProps {
  size?: 'xs' | 'sm' | 'base' | 'md' | 'lg' | 'xl';
  color?: 'primary' | 'white' | 'custom';
  className?: string;
  text?: string;
  inline?: boolean;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'primary',
  className = '',
  text,
  inline = false,
}) => {
  const sizeClasses = {
    xs: 'w-4 h-4',
    sm: 'w-4 h-4', // Keep backward compatibility
    base: 'w-5 h-5',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12',
  };

  // Border width - thicker for better visibility
  const borderWidths = {
    xs: '2px',
    sm: '2px',
    base: '2.5px',
    md: '3px',
    lg: '3px',
    xl: '4px',
  };

  const getSpinnerContent = () => {
    if (color === 'white') {
      return (
        <div
          className={`${sizeClasses[size]} rounded-full border-solid animate-spin`}
          style={{
            borderWidth: borderWidths[size],
            borderColor: 'rgba(255, 255, 255, 0.25)',
            borderTopColor: 'rgba(255, 255, 255, 1)',
          }}
        />
      );
    } else if (color === 'primary') {
      // Use the gradient-primary colors with high opacity for visibility
      // #667eea (purple-blue) and #764ba2 (purple) from gradient-primary
      return (
        <div
          className={`${sizeClasses[size]} rounded-full border-solid animate-spin`}
          style={{
            borderWidth: borderWidths[size],
            borderColor: 'rgba(102, 126, 234, 0.4)', // #667eea with opacity
            borderTopColor: 'rgba(118, 75, 162, 1)', // #764ba2 solid
            borderRightColor: 'rgba(102, 126, 234, 0.8)', // Brighter accent
            boxShadow:
              '0 0 12px rgba(102, 126, 234, 0.6), inset 0 0 12px rgba(118, 75, 162, 0.3)',
          }}
        />
      );
    } else {
      return (
        <div
          className={`${sizeClasses[size]} rounded-full border-solid animate-spin`}
          style={{
            borderWidth: borderWidths[size],
            borderColor: 'currentColor',
            borderTopColor: 'currentColor',
            opacity: 0.6,
          }}
        />
      );
    }
  };

  const spinnerElement = (
    <div className="relative">
      {getSpinnerContent()}

      {/* Enhanced glow for primary on larger sizes */}
      {(size === 'lg' || size === 'xl') && color === 'primary' && (
        <div
          className={`absolute inset-0 ${sizeClasses[size]} rounded-full animate-pulse`}
          style={{
            border: `${borderWidths[size]} solid rgba(102, 126, 234, 0.4)`,
            borderRadius: '50%',
            filter: 'blur(5px)',
            zIndex: -1,
            transform: 'scale(1.15)',
          }}
        />
      )}
    </div>
  );

  if (inline) {
    return spinnerElement;
  }

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      {spinnerElement}

      {/* Loading text */}
      {text && (
        <p className="mt-3 text-sm text-neutral-400 animate-pulse">{text}</p>
      )}
    </div>
  );
};

export default LoadingSpinner;
