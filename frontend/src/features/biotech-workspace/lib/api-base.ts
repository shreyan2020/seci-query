export function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, '');

  if (typeof window !== 'undefined') {
    const configuredPort = process.env.NEXT_PUBLIC_API_PORT?.trim();
    const port = configuredPort === undefined ? '8000' : configuredPort;
    const portPart = port ? `:${port}` : '';
    return `${window.location.protocol}//${window.location.hostname}${portPart}`;
  }

  return 'http://localhost:8000';
}

export const API_BASE = resolveApiBase();
