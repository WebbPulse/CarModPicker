# Chrome Extension Login Troubleshooting Guide

## Quick Debugging Steps

### 1. Check Browser Console
1. Open the extension popup
2. Right-click on the popup → "Inspect" (or press F12)
3. Check the Console tab for errors

### 2. Check Service Worker Console
1. Go to `chrome://extensions/`
2. Find "CarModPicker Part Scraper"
3. Click "service worker" link (or "Inspect views: service worker")
4. Check the Console tab for errors

### 3. Check Network Requests
1. Open the extension popup
2. Right-click → "Inspect"
3. Go to the Network tab
4. Try logging in
5. Look for the request to `/auth/token`
6. Check:
   - Request URL (should be your API URL + `/auth/token`)
   - Request method (should be POST)
   - Request headers (should include `Content-Type: application/x-www-form-urlencoded`)
   - Request payload (should have `username` and `password`)
   - Response status code
   - Response body

### 4. Verify API URL Configuration
1. Right-click the extension icon → "Options"
2. Verify the API Base URL is correct
3. Default should be: `https://carmodpicker.com/api`
4. For local development, use: `http://localhost:8000/api` (or your local port)

### 5. Check Storage
1. Open DevTools (F12) in the popup
2. Go to Application tab (Chrome) or Storage tab
3. Check:
   - `chrome.storage.sync` → `apiUrl` (should be your API URL)
   - `chrome.storage.local` → `authToken` (should exist after successful login)

## Common Issues

### Issue: CORS (Cross-Origin Resource Sharing) Errors
**Symptoms:**
- "Failed to fetch" error
- "CORS policy" error in console
- Network request shows CORS error in DevTools
- Status 0 or no response

**Cause:** The backend server is blocking requests from the Chrome extension.

**Solution:**
1. **Verify backend CORS configuration:**
   - The backend should allow `null` origin (for service workers)
   - The backend should allow `chrome-extension://*` origins (for popups)
   - Check `backend/app/main.py` - should have `allow_origin_regex=r"chrome-extension://.*"`
   - Check `backend/app/core/config.py` - `allowed_origins_list` should include `"null"`

2. **For local development:**
   - Make sure backend is running
   - Check backend logs for CORS errors
   - Verify `ALLOWED_ORIGINS` environment variable if using one

3. **Test CORS directly:**
   ```bash
   # Test with curl to see CORS headers
   curl -X OPTIONS http://localhost:8000/api/auth/token \
     -H "Origin: null" \
     -H "Access-Control-Request-Method: POST" \
     -v
   ```

### Issue: "Login failed" with no specific error
**Possible causes:**
- API URL is incorrect
- API server is not running
- CORS issues (check Network tab for CORS errors)
- Network connectivity issues

**Solution:**
1. Verify API URL in Options page
2. Test API URL in browser: `https://your-api-url.com/api/auth/token` (should return 405 Method Not Allowed, not 404)
3. Check if API server is running
4. Check browser console for CORS errors
5. Check service worker console for detailed error messages

### Issue: "2FA is enabled" error
**Cause:** User has 2FA enabled, which the extension doesn't support yet

**Solution:**
- Login via the web app first to authenticate
- Or disable 2FA for testing
- Extension will need 2FA support added in the future

### Issue: "Incorrect username or password"
**Possible causes:**
- Wrong credentials
- User account is disabled
- Password has special characters causing encoding issues

**Solution:**
1. Verify credentials work in web app
2. Check if account is active
3. Try with a simple password (no special chars) to test

### Issue: Network request fails
**Possible causes:**
- API URL is wrong
- Server is down
- CORS policy blocking requests
- HTTPS/HTTP mismatch

**Solution:**
1. Check API URL format (should end with `/api`)
2. Verify server is accessible
3. Check CORS headers in Network tab
4. Ensure HTTPS for production, HTTP for localhost

### Issue: Token not being saved
**Possible causes:**
- Storage permissions issue
- Token response format incorrect

**Solution:**
1. Check `chrome.storage.local` in DevTools
2. Verify token is in response: `{ access_token: "...", user: {...} }`
3. Check service worker console for errors

## Debug Mode

Enable debug logging by:
1. Opening the extension popup
2. Opening DevTools (F12)
3. Running in console: `localStorage.setItem('debug', 'true')`
4. Reload extension and try login again
5. Check console for detailed logs

## Manual API Test

Test the API directly to verify it's working:

```javascript
// In browser console (on any page)
const formData = new URLSearchParams();
formData.append('username', 'your_username');
formData.append('password', 'your_password');

fetch('https://carmodpicker.com/api/auth/token', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: formData.toString(),
})
  .then(r => r.json())
  .then(console.log)
  .catch(console.error);
```

## Getting Help

If issues persist:
1. Collect console logs from both popup and service worker
2. Collect Network tab screenshots
3. Note the exact error message
4. Verify API is working via web app or direct API call
