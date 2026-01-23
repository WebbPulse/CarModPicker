import { createRoot } from 'react-dom/client';
import Options from './pages/options';
import './index.css';

// Initialize React app
const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<Options />);
}
