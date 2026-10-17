"""Instaloader metadata first; bounded media retrieval only when explicitly called."""
import contextlib
import re
import time
from http.cookiejar import LoadError, MozillaCookieJar
from pathlib import Path
from urllib.parse import urljoin, urlparse


def allowed_media(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.port in (None,443) and not p.username and any(
        (p.hostname or '') == host or (p.hostname or '').endswith('.'+host)
        for host in ('cdninstagram.com','fbcdn.net','instagram.com'))


@contextlib.contextmanager
def client(config, checkpoint):
    import instaloader

    class InterruptibleRateController(instaloader.RateController):
        def sleep(self, secs):
            if secs>30:
                raise RuntimeError('Instagram retrieval needs a cooldown. Wait before retrying.')
            end = time.monotonic()+secs
            while time.monotonic()<end:
                checkpoint()
                time.sleep(min(.25,max(0,end-time.monotonic())))

        def handle_429(self, query_type):
            raise RuntimeError('Instagram rate limited retrieval. Wait before retrying.')

    loader = instaloader.Instaloader(quiet=True, max_connection_attempts=1, request_timeout=20,
        download_videos=False, download_pictures=False, save_metadata=False,
        rate_controller=lambda ctx:InterruptibleRateController(ctx))
    # Upstream errors can include signed media URLs; do not copy them into logs.
    loader.context.error = lambda *args,**kwargs:None
    try:
        checkpoint()
        cookiefile = config.get('cookies_file')
        if cookiefile:
            jar = MozillaCookieJar(cookiefile)
            try:
                jar.load(ignore_discard=True,ignore_expires=False)
            except (OSError,LoadError):
                raise RuntimeError('Instagram session file unavailable or invalid. Reconnect the extension.') from None
            cookies = {c.name:c.value for c in jar if c.domain.lstrip('.')=='instagram.com'}
            if all(cookies.get(k) for k in ('sessionid','csrftoken','ds_user_id')):
                # Only post lookup is used; account ID identifies the loaded session.
                loader.load_session(cookies['ds_user_id'],cookies)
        yield loader
    finally:
        loader.close()


def resolve(url, config, checkpoint, include_video=False):
    import instaloader
    parsed = urlparse(url)
    match = re.fullmatch(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)/?',parsed.path)
    if parsed.scheme!='https' or parsed.hostname not in ('instagram.com','www.instagram.com') or not match:
        raise ValueError('Expected an Instagram post or reel URL.')
    with client(config,checkpoint) as loader:
        try:
            checkpoint()
            post = instaloader.Post.from_shortcode(loader.context,match.group(1))
            caption = post.caption or ''
            result = {'title':caption.splitlines()[0][:500] if caption else '',
                      'caption':caption[:12000], 'creator':str(post.owner_username or '')[:200],
                      'cover_url':str(post.url or '')[:4000]}
            # Metadata acquisition must never resolve or request video media.
            if include_video:
                if not post.is_video:
                    raise ValueError('This saved post has no video.')
                duration = float(post.video_duration or 0)
                if duration>600:
                    raise ValueError('Reel is longer than 10 minutes.')
                result['video_url'] = post.video_url
                result['duration'] = duration
                if not result['video_url']:
                    raise ValueError('No downloadable video found.')
            checkpoint()
            return result
        except instaloader.exceptions.InstaloaderException as exc:
            raise RuntimeError('Instagram retrieval unavailable. Check your session, access and rate limits.') from exc


def download_video(url, folder, checkpoint):
    import requests
    target = Path(folder)/'video.mp4'
    deadline = time.monotonic()+120
    complete = False
    try:
        for _ in range(4):
            checkpoint()
            if not allowed_media(url):
                raise ValueError('Video must use an Instagram media host.')
            # No Instagram session cookies are attached to media requests.
            with requests.get(url,stream=True,timeout=25,allow_redirects=False) as response:
                if response.is_redirect:
                    url = urljoin(url,response.headers['Location'])
                    continue
                response.raise_for_status()
                if not response.headers.get('Content-Type','').startswith('video/'):
                    raise ValueError('Video response is not a video.')
                if int(response.headers.get('Content-Length') or 0)>250_000_000:
                    raise ValueError('Video is too large.')
                size = 0
                with target.open('wb') as output:
                    for chunk in response.iter_content(65536):
                        checkpoint()
                        size += len(chunk)
                        if size>250_000_000 or time.monotonic()>deadline:
                            raise ValueError('Video exceeded the download budget.')
                        output.write(chunk)
                with target.open('rb') as downloaded:
                    if b'ftyp' not in downloaded.read(32):
                        raise ValueError('Expected an MP4 video.')
                checkpoint()
                complete = True
                return target
        raise ValueError('Too many video redirects.')
    except requests.RequestException as exc:
        raise RuntimeError('Instagram video download unavailable. Check access or retry later.') from exc
    finally:
        # The caller owns successful media; failed partial files are disposable.
        if not complete:
            target.unlink(missing_ok=True)
