// Viewer request on /api/*: the API's routes have no /api prefix,
// so /api/files must reach API Gateway as /files.
function handler(event) {
  var request = event.request;
  // The behavior only matches /api/..., so the first 4 chars are always "/api".
  request.uri = request.uri.substring(4) || '/';
  return request;
}
