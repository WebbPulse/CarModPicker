function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Apex → www 301 redirect. Keeps www.carmodpicker.com canonical.
  // Preserves the path + query string so the extension login flow's
  // /extension-auth?extensionId=…&state=… lands intact on www.
  var host = request.headers.host && request.headers.host.value;
  if (host === 'carmodpicker.com') {
    var parts = [];
    var qs = request.querystring || {};
    for (var k in qs) {
      var entry = qs[k];
      var ek = encodeURIComponent(k);
      if (entry.multiValue) {
        for (var i = 0; i < entry.multiValue.length; i++) {
          parts.push(ek + '=' + encodeURIComponent(entry.multiValue[i].value));
        }
      } else {
        parts.push(ek + '=' + encodeURIComponent(entry.value));
      }
    }
    var query = parts.length ? '?' + parts.join('&') : '';
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: { value: 'https://www.carmodpicker.com' + uri + query },
      },
    };
  }

  if (uri === '' || uri === '/') {
    return request;
  }

  // Paths ending with / → append index.html.
  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
    return request;
  }

  // Extensionless paths (no dot in the final segment) are SPA routes.
  // Rewrite to a directory-index lookup.
  var lastSlash = uri.lastIndexOf('/');
  var lastSegment = uri.slice(lastSlash + 1);
  if (lastSegment.indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }

  return request;
}
