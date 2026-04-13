export function getApiBaseUrl() {
  return (
    process.env.HYPATIA_API_BASE_URL ||
    process.env.NEXT_PUBLIC_HYPATIA_API_BASE_URL ||
    "http://127.0.0.1:8000"
  );
}
