# Chrome Extension Development Workflow

## Quick Reload (No Delete/Re-add Needed!)

**You never need to delete and re-add the extension.** Just use the reload button:

1. Go to `chrome://extensions/`
2. Find your extension
3. Click the **reload icon** (circular arrow) 🔄

That's it! Much faster than delete/re-add.

## What Needs Reloading When

### Files That Require Extension Reload:
- ✅ `manifest.json` - **Always requires reload**
- ✅ `background.ts` (compiled to `dist/background.js`) - **Requires reload**
- ✅ `popup.html`, `options.html` - **Requires reload**
- ✅ `popup.css` - **Requires reload** (if changed)

### Files That Auto-Update (No Reload):
- ✅ `content.ts` (compiled to `dist/content.js`) - **Auto-updates** on next page navigation
- ✅ `popup.ts` (compiled to `dist/popup.js`) - **Auto-updates** when you reopen popup
- ✅ `options.ts` (compiled to `dist/options.js`) - **Auto-updates** when you reopen options page

**Note:** Service workers (background scripts) always need a reload because they persist in memory.

## Development Workflow

### Option 1: Manual Reload (Simplest)
1. Run `npm run watch` in one terminal (auto-compiles TypeScript)
2. Make your changes
3. Wait for TypeScript to compile
4. Click reload button in `chrome://extensions/`
5. Test your changes

### Option 2: Watch Mode + Manual Reload
```bash
# Terminal 1: Watch TypeScript files
npm run watch

# Terminal 2: Watch and rebuild (if you modify build process)
# (Not needed for simple changes)
```

Then just reload in Chrome when files change.

### Option 3: Automated Reload Script (Advanced)
Use the `dev` script (see below) which watches files and can trigger reloads.

## Hot Reload Limitations

Chrome extensions **cannot** automatically reload themselves for security reasons. You must manually click the reload button.

However, you can:
- Use watch mode to auto-compile TypeScript
- Use browser extensions like "Extensions Reloader" for one-click reload
- Use the `dev` script below for file watching

## Tips

1. **Keep `chrome://extensions/` open** in a pinned tab for quick reloads
2. **Use keyboard shortcut**: After reloading once, Chrome remembers the extension - just press the reload button
3. **Service Worker Debugging**: If background script changes, always reload and check service worker console
4. **Content Scripts**: These update automatically on next page load, so you can just refresh the page you're testing on
5. **Popup Scripts**: These update when you close and reopen the popup

## Testing Checklist

After making changes:
- [ ] Run `npm run build` or `npm run watch`
- [ ] Reload extension in `chrome://extensions/`
- [ ] Test popup (close and reopen if you changed popup.ts)
- [ ] Test content script (refresh the page you're testing on)
- [ ] Test background script (check service worker console)
- [ ] Test options page (reopen if you changed options.ts)
