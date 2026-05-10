import { useContext } from 'react';
import {
  AppSettingsContext,
  type AppSettingsContextType,
} from '../contexts/AppSettingsContextDefinition';

export const useAppSettings = (): AppSettingsContextType => {
  const context = useContext(AppSettingsContext);
  if (context === undefined) {
    throw new Error(
      'useAppSettings must be used within an AppSettingsProvider'
    );
  }
  return context;
};
