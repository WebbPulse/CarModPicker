// Debug logging - this runs when the module loads
console.log('[MAIN-OPTIONS] ========================================');
console.log('[MAIN-OPTIONS] Module script started loading');
console.log('[MAIN-OPTIONS] Current location:', window.location.href);
console.log('[MAIN-OPTIONS] Document ready state:', document.readyState);
console.log('[MAIN-OPTIONS] Script URL:', import.meta.url);
console.log('[MAIN-OPTIONS] ========================================');

console.log('[MAIN-OPTIONS] Step 1: Importing react-dom/client...');
import { createRoot } from 'react-dom/client';
console.log('[MAIN-OPTIONS] ✓ React imported successfully');

console.log('[MAIN-OPTIONS] Step 2: Importing Options component...');
import Options from './pages/options';
console.log('[MAIN-OPTIONS] ✓ Options component imported successfully');

console.log('[MAIN-OPTIONS] Step 3: Importing CSS...');
import './index.css';
console.log('[MAIN-OPTIONS] ✓ CSS imported successfully');

// Initialize React app
console.log('[MAIN-OPTIONS] Step 4: Looking for root container...');
const container = document.getElementById('root');
if (container) {
  console.log('[MAIN-OPTIONS] ✓ Root container found');
  console.log('[MAIN-OPTIONS] Step 5: Creating React root...');
  try {
    const root = createRoot(container);
    console.log('[MAIN-OPTIONS] ✓ React root created');
    console.log('[MAIN-OPTIONS] Step 6: Rendering Options component...');
    root.render(<Options />);
    console.log('[MAIN-OPTIONS] ✓✓✓ Options component rendered successfully! ✓✓✓');
  } catch (error) {
    console.error('[MAIN-OPTIONS] ✗ Failed to render React app:', error);
    console.error('[MAIN-OPTIONS] Error type:', error?.constructor?.name);
    console.error('[MAIN-OPTIONS] Error message:', error instanceof Error ? error.message : String(error));
    console.error('[MAIN-OPTIONS] Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    container.innerHTML = `
      <div style="padding: 20px; color: red;">
        <h2>Error Loading Extension Options</h2>
        <p>${error instanceof Error ? error.message : 'Unknown error'}</p>
        <p>Check the console for more details.</p>
      </div>
    `;
  }
} else {
  console.error('[MAIN-OPTIONS] ✗ Root container not found!');
  console.error('[MAIN-OPTIONS] Document body:', document.body);
  console.error('[MAIN-OPTIONS] All elements with id:', Array.from(document.querySelectorAll('[id]')).map(el => el.id));
}
