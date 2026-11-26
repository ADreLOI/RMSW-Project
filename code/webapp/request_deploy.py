"""Request a Render deployment without printing the secret hook URL."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    hook = os.getenv("RENDER_DEPLOY_HOOK_URL", "")
    if not hook:
        raise SystemExit("Set repository secret RENDER_DEPLOY_HOOK_URL to enable automatic relay deployment.")
    url = urlsplit(hook)
    if url.scheme != "https" or url.netloc != "api.render.com" or not url.path.startswith("/deploy/srv-"):
        raise SystemExit("Invalid Render deploy hook URL.")
    query = dict(parse_qsl(url.query))
    query["ref"] = os.environ["GITHUB_SHA"]
    address = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ""))
    try:
        with build_opener(NoRedirect).open(Request(address, method="POST"), timeout=30) as response:
            if response.status not in (200, 202):
                raise RuntimeError()
    except Exception:
        raise SystemExit("Render did not accept the deploy request. Check its status and the repository secret.") from None
    print("Render accepted the deployment request for the tested commit. Check Render for build completion.")


if __name__ == "__main__":
    main()
