// Debug logging - this runs when the module loads
console.log('[MAIN-POPUP] ========================================');
console.log('[MAIN-POPUP] Module script started loading');
console.log('[MAIN-POPUP] Current location:', window.location.href);
console.log('[MAIN-POPUP] Document ready state:', document.readyState);
console.log('[MAIN-POPUP] Script URL:', import.meta.url);
console.log('[MAIN-POPUP] ========================================');

console.log('[MAIN-POPUP] Step 1: Importing react-dom/client...');
import { createRoot } from 'react-dom/client';
console.log('[MAIN-POPUP] ✓ React imported successfully');

console.log('[MAIN-POPUP] Step 2: Importing Popup component...');
import Popup from './pages/popup';
console.log('[MAIN-POPUP] ✓ Popup component imported successfully');

console.log('[MAIN-POPUP] Step 3: Importing CSS...');
import './index.css';
console.log('[MAIN-POPUP] ✓ CSS imported successfully');

// Initialize React app
console.log('[MAIN-POPUP] Step 4: Looking for root container...');
const container = document.getElementById('root');
if (container) {
  console.log('[MAIN-POPUP] ✓ Root container found');
  console.log('[MAIN-POPUP] Step 5: Creating React root...');
  try {
    const root = createRoot(container);
    console.log('[MAIN-POPUP] ✓ React root created');
    console.log('[MAIN-POPUP] Step 6: Rendering Popup component...');
    root.render(<Popup />);
    console.log('[MAIN-POPUP] ✓✓✓ Popup component rendered successfully! ✓✓✓');
  } catch (error) {
    console.error('[MAIN-POPUP] ✗ Failed to render React app:', error);
    console.error('[MAIN-POPUP] Error type:', error?.constructor?.name);
    console.error('[MAIN-POPUP] Error message:', error instanceof Error ? error.message : String(error));
    console.error('[MAIN-POPUP] Error stack:', error instanceof Error ? error.stack : 'No stack trace');
    container.innerHTML = `
      <div style="padding: 20px; color: red;">
        <h2>Error Loading Extension</h2>
        <p>${error instanceof Error ? error.message : 'Unknown error'}</p>
        <p>Check the console for more details.</p>
      </div>
    `;
  }
} else {
  console.error('[MAIN-POPUP] ✗ Root container not found!');
  console.error('[MAIN-POPUP] Document body:', document.body);
  console.error('[MAIN-POPUP] All elements with id:', Array.from(document.querySelectorAll('[id]')).map(el => el.id));
}
