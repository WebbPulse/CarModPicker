import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import { resolve } from "path";
import { defineConfig } from "vite";
import { copyFileSync, mkdirSync, existsSync, readdirSync, statSync, readFileSync, writeFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Plugin to inline vendor chunk into popup/options for Chrome extension compatibility
const inlineVendorPlugin = () => {
  return {
    name: "inline-vendor",
    closeBundle() {
      const popupJsPath = resolve(__dirname, "dist", "popup.js");
      const optionsJsPath = resolve(__dirname, "dist", "options.js");
      
      // Find vendor chunk
      const assetsDir = resolve(__dirname, "dist", "assets");
      if (!existsSync(assetsDir)) {
        console.log("⚠ No assets directory found, skipping vendor inlining");
        return;
      }
      const vendorFiles = readdirSync(assetsDir).filter(
        (f) => f.startsWith("vendor-") && f.endsWith(".js")
      );
      
      if (vendorFiles.length > 0) {
        const vendorPath = resolve(__dirname, "dist", "assets", vendorFiles[0]);
        const vendorContent = readFileSync(vendorPath, "utf-8");
        
        // Inline vendor into popup.js
        if (existsSync(popupJsPath)) {
          let popupContent = readFileSync(popupJsPath, "utf-8");
          // Replace import statement with vendor content - only match at start of line or after semicolon/newline
          // This avoids matching import statements inside strings
          const importRegex = /(^|\n|;)\s*import\s+.*?\s+from\s+["']\.\/assets\/vendor-[^"']+["'];?/gm;
          if (importRegex.test(popupContent)) {
            popupContent = popupContent.replace(importRegex, (match, prefix) => {
              return prefix + '\n' + vendorContent;
            });
            writeFileSync(popupJsPath, popupContent, "utf-8");
            console.log("✓ Inlined vendor chunk into popup.js");
          } else {
            console.log("⚠ No vendor import found in popup.js to inline");
          }
        }
        
        // Inline vendor into options.js
        if (existsSync(optionsJsPath)) {
          let optionsContent = readFileSync(optionsJsPath, "utf-8");
          const importRegex = /(^|\n|;)\s*import\s+.*?\s+from\s+["']\.\/assets\/vendor-[^"']+["'];?/gm;
          if (importRegex.test(optionsContent)) {
            optionsContent = optionsContent.replace(importRegex, (match, prefix) => {
              return prefix + '\n' + vendorContent;
            });
            writeFileSync(optionsJsPath, optionsContent, "utf-8");
            console.log("✓ Inlined vendor chunk into options.js");
          } else {
            console.log("⚠ No vendor import found in options.js to inline");
          }
        }
      }
    },
  };
};

// Plugin to fix HTML files for Chrome extension (remove crossorigin)
const fixHtmlPlugin = () => {
  return {
    name: "fix-html",
    closeBundle() {
      // Fix popup.html - remove crossorigin and type="module" attributes
      const popupHtmlPath = resolve(__dirname, "dist", "popup.html");
      if (existsSync(popupHtmlPath)) {
        let html = readFileSync(popupHtmlPath, "utf-8");
        // Remove crossorigin attribute from script and link tags
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        // Keep type="module" - required for ES modules
        writeFileSync(popupHtmlPath, html, "utf-8");
        console.log("✓ Fixed popup.html for Chrome extension");
      }

      // Fix options.html
      const optionsHtmlPath = resolve(__dirname, "dist", "options.html");
      if (existsSync(optionsHtmlPath)) {
        let html = readFileSync(optionsHtmlPath, "utf-8");
        // Remove crossorigin attribute from script and link tags
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        // Keep type="module" - required for ES modules
        writeFileSync(optionsHtmlPath, html, "utf-8");
        console.log("✓ Fixed options.html for Chrome extension");
      }
    },
  };
};

// Plugin to copy manifest.json and icons to dist
const copyManifestPlugin = () => {
  return {
    name: "copy-manifest",
    writeBundle() {
      // Copy and fix manifest.json paths
      const manifestSrc = resolve(__dirname, "manifest.json");
      const manifestDest = resolve(__dirname, "dist", "manifest.json");
      if (existsSync(manifestSrc)) {
        const manifest = JSON.parse(readFileSync(manifestSrc, "utf-8"));
        // Fix paths - remove 'dist/' prefix since manifest will be in dist/
        if (manifest.background?.service_worker?.startsWith("dist/")) {
          manifest.background.service_worker = manifest.background.service_worker.replace("dist/", "");
        }
        if (manifest.content_scripts?.[0]?.js) {
          manifest.content_scripts[0].js = manifest.content_scripts[0].js.map((path: string) =>
            path.replace("dist/", "")
          );
        }
        writeFileSync(manifestDest, JSON.stringify(manifest, null, 2), "utf-8");
        console.log("✓ Copied and fixed manifest.json to dist/");
      }

      // Copy icons directory
      const iconsSrc = resolve(__dirname, "icons");
      const iconsDest = resolve(__dirname, "dist", "icons");
      if (existsSync(iconsSrc)) {
        mkdirSync(iconsDest, { recursive: true });
        const files = readdirSync(iconsSrc);
        files.forEach((file: string) => {
          const srcPath = resolve(iconsSrc, file);
          const destPath = resolve(iconsDest, file);
          if (statSync(srcPath).isFile()) {
            copyFileSync(srcPath, destPath);
          }
        });
        console.log("✓ Copied icons to dist/icons/");
      }
    },
  };
};

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), inlineVendorPlugin(), fixHtmlPlugin(), copyManifestPlugin()],
  base: "./", // Use relative paths for Chrome extension
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false, // Disable CSS code splitting for Chrome extensions
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "popup.html"),
        options: resolve(__dirname, "options.html"),
        background: resolve(__dirname, "src/background.ts"),
        content: resolve(__dirname, "src/content.ts"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          // Keep background and content scripts in root of dist (manifest expects them there)
          if (chunkInfo.name === "background" || chunkInfo.name === "content") {
            return "[name].js";
          }
          // Popup and options as single files in root
          if (chunkInfo.name === "popup" || chunkInfo.name === "options") {
            return "[name].js";
          }
          return "assets/[name]-[hash].js";
        },
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith(".css")) {
            return "assets/[name]-[hash][extname]";
          }
          if (assetInfo.name?.endsWith(".html")) {
            return "[name][extname]";
          }
          return "assets/[name]-[hash][extname]";
        },
        // Keep ES module format but ensure proper bundling
        format: "es",
        // Bundle everything together for popup/options (no separate vendor chunk)
        // This avoids MIME type issues with Chrome extensions
        manualChunks: (id, { getModuleInfo }) => {
          const moduleInfo = getModuleInfo(id);
          // For popup and options entries, bundle everything together
          if (moduleInfo?.isEntry) {
            const entryName = moduleInfo.id.split('/').pop()?.replace('.html', '') || '';
            if (entryName === 'popup' || entryName === 'options') {
              return undefined; // Bundle everything into the entry file
            }
          }
          // For background and content, allow vendor chunk
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
    // Don't minify for easier debugging (optional, can enable later)
    minify: false,
    // Use ES2015 target for better Chrome extension compatibility
    target: "es2015",
    modulePreload: false,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
