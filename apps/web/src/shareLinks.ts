const STAGING_IP_HOST = '84.247.130.242';
const STAGING_HTTPS_ORIGIN = 'https://84-247-130-242.sslip.io';

type ShareLocation = Pick<Location, 'hostname' | 'origin'>;

export function getPublicShareUrl(logNo: string, location: ShareLocation = window.location): string {
  // The legacy :8080 address is still useful for direct access, but chat apps
  // do not consistently turn an insecure IP + port into a clickable link.
  const origin = location.hostname === STAGING_IP_HOST ? STAGING_HTTPS_ORIGIN : location.origin;
  return `${origin}/share/${encodeURIComponent(logNo)}`;
}
