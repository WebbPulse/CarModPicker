import {
  render,
  type RenderOptions,
  type Screen,
} from '@testing-library/react';
import { type ReactElement } from 'react';
import { expect, vi } from 'vitest';
import { apiClient as sharedMockedApiClient } from '../../api/client';
import type { UserRead } from '../../types/Api';
import { setupApiMocks } from '../mocks/api';
import { mockAdminUser, mockSuperuserUser, mockUseAuth } from './test-mocks';
import { AllTheProviders } from './TestWrapper';

// Custom render function that includes providers
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
  initialAuthState?: {
    isAuthenticated: boolean;
    user?: UserRead | null;
    isLoading?: boolean;
  };
}

// Point both the services/Api shim AND any internal api-client consumers at
// the SAME mock instance — the one setup.ts (D-18) registered under
// `../api/client`. Importing `apiClient` above and re-using it below means
// a test can assert on `vi.mocked(apiClient.post)` regardless of whether
// the component imports `apiClient` directly from `../api/client` or reaches
// the default export through the `../services/Api` shim (Register.tsx), and
// the identity holds.
const mockApiClient = sharedMockedApiClient;

// Mock the API module. Phase 8 plan 08-10 fix: preserve the shim's named
// re-exports (authApi, buildListsApi, etc.) via importOriginal so page tests
// whose components call `authApi.login(...)` get the real domain-API object
// whose internal `apiClient.<verb>(...)` lands on the mocked Axios client.
// Previously this factory returned ONLY `default` (a fresh mock object), which
// stripped every named export AND created a DIFFERENT apiClient instance than
// setup.ts's mock of `../api/client`. Binding `default` to the shared mock
// below makes every apiClient reference — direct, via services/Api default,
// or via a domain API — point at the same `vi.fn()` so assertions converge.
vi.mock('../../services/Api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/Api')>();
  return {
    ...actual,
    default: mockApiClient,
  };
});

// Mock the useAuth hook
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const customRender = (ui: ReactElement, options: CustomRenderOptions = {}) => {
  const { route = '/', initialAuthState, ...renderOptions } = options;

  // Setup API mocks before rendering
  setupApiMocks();

  // Set up route if provided
  if (route !== '/') {
    window.history.pushState({}, 'Test page', route);
  }

  return render(ui, {
    wrapper: ({ children }) => (
      <AllTheProviders initialAuthState={initialAuthState}>
        {children}
      </AllTheProviders>
    ),
    ...renderOptions,
  });
};

// Re-export everything
// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react';

// Override render method
export { customRender as render };

// Test data helpers
export const createMockUser = (overrides = {}) => ({
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  disabled: false,
  email_verified: true,
  image_urls: ['https://example.com/user.jpg'],
  is_superuser: false,
  is_admin: false,
  ...overrides,
});

export const createMockCar = (overrides = {}) => ({
  id: 1,
  car_make_name: 'Toyota',
  car_model_name: 'Camry',
  year: 2020,
  trim: 'SE',
  vin: '1HGBH41JXMN109186',
  image_urls: ['https://example.com/car.jpg'],
  user_id: 1,
  ...overrides,
});

export const createMockBuildList = (overrides = {}) => ({
  id: 1,
  name: 'Test Build',
  description: 'Test build description',
  car_id: 1,
  image_urls: ['https://example.com/build.jpg'],
  ...overrides,
});

export const createMockPart = (overrides = {}) => ({
  id: 1,
  name: 'Test Part',
  description: 'Test part description',
  best_price_cents: 10000, // $100.00
  image_urls: ['https://example.com/part.jpg'],
  category_id: 1,
  user_id: 1,
  car_ids: [],
  is_universal: false,
  part_manufacturer: 'TestPartManufacturer',
  part_number: 'TP001',
  specifications: { weight: '2.5kg', material: 'aluminum' },
  is_verified: true,
  source: 'user',
  edit_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

// Common test scenarios
export const testScenarios = {
  authenticated: {
    initialAuthState: {
      isAuthenticated: true,
      user: createMockUser(),
      isLoading: false,
    },
  },
  unauthenticated: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: false,
    },
  },
  loading: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: true,
    },
  },
  // Phase 8 D-05: admin + superuser scenarios for admin-area page + hook tests.
  adminAuthenticated: {
    initialAuthState: {
      isAuthenticated: true,
      user: mockAdminUser,
      isLoading: false,
    },
  },
  superuserAuthenticated: {
    initialAuthState: {
      isAuthenticated: true,
      user: mockSuperuserUser,
      isLoading: false,
    },
  },
};

// Common assertions
export const expectElementToBeInDocument = (element: HTMLElement) => {
  expect(element).toBeInTheDocument();
};

export const expectElementToHaveText = (element: HTMLElement, text: string) => {
  expect(element).toHaveTextContent(text);
};

export const expectElementToHaveClass = (
  element: HTMLElement,
  className: string
) => {
  expect(element).toHaveClass(className);
};

export const expectElementToBeVisible = (element: HTMLElement) => {
  expect(element).toBeVisible();
};

export const expectElementToBeDisabled = (element: HTMLElement) => {
  expect(element).toBeDisabled();
};

export const expectElementToBeEnabled = (element: HTMLElement) => {
  expect(element).toBeEnabled();
};

// Form testing helpers
export const fillFormField = (screen: Screen, label: string, value: string) => {
  const field = screen.getByLabelText(label);
  if (field instanceof HTMLInputElement) {
    field.value = value;
    field.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return field;
};

export const submitForm = (screen: Screen, submitButtonText = 'Submit') => {
  const submitButton = screen.getByRole('button', { name: submitButtonText });
  submitButton.click();
  return submitButton;
};

// Navigation helpers
export const navigateTo = (route: string) => {
  window.history.pushState({}, 'Test page', route);
};

// Mock function helpers
export const createMockFunction = () => {
  return vi.fn();
};

export const createMockPromise = (value: unknown, delay = 0) => {
  return new Promise((resolve) => {
    setTimeout(() => resolve(value), delay);
  });
};

export const createMockRejectedPromise = (error: Error, delay = 0) => {
  return new Promise((_, reject) => {
    setTimeout(() => reject(error), delay);
  });
};
