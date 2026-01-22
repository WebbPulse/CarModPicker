/**
 * Post-build script to remove ES module syntax from compiled files
 * Chrome extensions don't support ES modules in service workers
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const distDir = path.join(__dirname, 'dist');
const filesToClean = ['background.js', 'content.js', 'popup.js', 'options.js', 'types.js'];

function cleanFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  
  // Remove "use strict"; if present
  content = content.replace(/^"use strict";\s*\n?/gm, '');
  
  // Remove Object.defineProperty(exports, "__esModule", { value: true });
  content = content.replace(/Object\.defineProperty\(exports,\s*"__esModule",\s*\{\s*value:\s*true\s*\}\);\s*\n?/g, '');
  
  // Remove export {}; statements
  content = content.replace(/^export\s+\{\s*\}\s*;?\s*$/gm, '');
  
  // Remove any remaining export statements at the end
  content = content.replace(/\n\s*export\s+\{\s*\}\s*;?\s*$/g, '');
  
  // Clean up any double newlines at the end
  content = content.replace(/\n{3,}$/, '\n');
  
  fs.writeFileSync(filePath, content, 'utf8');
  console.log(`✓ Cleaned ${path.basename(filePath)}`);
}

filesToClean.forEach(file => {
  const filePath = path.join(distDir, file);
  if (fs.existsSync(filePath)) {
    cleanFile(filePath);
  } else {
    console.log(`⚠ File not found: ${file}`);
  }
});

console.log('\nBuild cleanup complete!');
