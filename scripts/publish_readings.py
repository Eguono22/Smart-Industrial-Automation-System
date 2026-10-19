"""Forward a JSON sensor snapshot from an equipment gateway to an asset."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='SIAS server URL; use HTTPS in production')
    parser.add_argument('--asset-id', required=True, type=int)
    parser.add_argument('--file', required=True, help='Gateway JSON payload file')
    args = parser.parse_args()
    token = os.environ.get('SIAS_DEVICE_TOKEN', '')
    if not token:
        sys.exit('Set SIAS_DEVICE_TOKEN to this asset’s device credential.')
    if args.asset_id < 1 or not args.base_url.startswith(('https://', 'http://')):
        parser.error('Provide a valid HTTP(S) base URL and positive asset ID')
    try:
        with open(args.file, 'rb') as source:
            body = source.read(32769)
        if len(body) > 32768:
            sys.exit('Payload exceeds 32 KiB.')
        json.loads(body)
        request = Request(f"{args.base_url.rstrip('/')}/api/telemetry/{args.asset_id}/readings", data=body,
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method='POST')
        # Redirects are refused so an equipment token cannot be forwarded to another host.
        import urllib.request
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            print('Readings accepted:', response.status)
    except HTTPError as error:
        sys.exit(f'SIAS rejected the upload (HTTP {error.code}).')
    except (OSError, ValueError, URLError):
        sys.exit('Unable to publish readings. Check the payload file and gateway connection.')
