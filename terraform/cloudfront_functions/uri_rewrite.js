function handler(event) {
  var request = event.request;
  var uri = request.uri;

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
