export async function onRequest(context) {
  const url = new URL(context.request.url);
  const origin = (context.env && context.env.BACKEND_ORIGIN) || 'https://openconstructionerp.com';
  const targetUrl = origin.replace(/\/+$/, '') + url.pathname + url.search;
  const init = {
    method: context.request.method,
    headers: new Headers(context.request.headers),
    redirect: 'manual',
  };
  init.headers.delete('host');
  if (context.request.method !== 'GET' && context.request.method !== 'HEAD') {
    init.body = context.request.body;
  }
  return fetch(targetUrl, init);
}
