import { createRoot } from 'react-dom/client';
import Popup from './pages/popup';
import './index.css';

// Initialize React app
const container = document.getElementById('root');
if (container) {
  try {
    const root = createRoot(container);
    root.render(<Popup />);
  } catch (error) {
    console.error('Failed to render React app:', error);
    container.innerHTML = `
      <div style="padding: 20px; color: red;">
        <h2>Error Loading Extension</h2>
        <p>${error instanceof Error ? error.message : 'Unknown error'}</p>
        <p>Check the console for more details.</p>
      </div>
    `;
  }
} else {
  console.error('Root container not found');
}
