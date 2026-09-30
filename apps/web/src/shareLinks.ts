const STAGING_IP_HOST = '84.247.130.242';
const STAGING_PUBLIC_ORIGIN = 'http://84.247.130.242:8080';

type ShareLocation = Pick<Location, 'hostname' | 'origin'>;

export function getPublicShareUrl(logNo: string, location: ShareLocation = window.location): string {
  // Keep public log links on the direct address that is reachable without DNS.
  const origin = location.hostname === STAGING_IP_HOST || location.hostname.endsWith('.sslip.io')
    ? STAGING_PUBLIC_ORIGIN
    : location.origin;
  return `${origin}/share/${encodeURIComponent(logNo)}`;
}
