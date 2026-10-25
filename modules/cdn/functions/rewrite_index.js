// Viewer request on the site: S3's REST endpoint has no directory indexes,
// and the static export (trailingSlash) writes each page as <route>/index.html.
//   /files/    -> /files/index.html
//   /callback  -> /callback/index.html
//   /app.js    -> unchanged
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (uri.split('/').pop().indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }
  return request;
}
