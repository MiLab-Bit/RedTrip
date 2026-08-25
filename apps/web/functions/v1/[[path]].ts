export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const target = new URL(`/v1/${url.pathname.slice(4)}${url.search}`, "https://military-micro-recent-several.trycloudflare.com");
  return fetch(target.toString(), context.request);
};
