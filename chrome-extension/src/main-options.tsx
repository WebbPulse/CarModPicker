import { createRoot } from 'react-dom/client';
import Options from './pages/options';
import './index.css';

const container = document.getElementById('root');
if (container) {
  try {
    const root = createRoot(container);
    root.render(<Options />);
  } catch (error) {
    container.innerHTML = `
      <div style="padding: 20px; color: red;">
        <h2>Error Loading Extension Options</h2>
        <p>${error instanceof Error ? error.message : 'Unknown error'}</p>
        <p>Check the console for more details.</p>
      </div>
    `;
  }
}
