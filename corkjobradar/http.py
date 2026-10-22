import ipaddress
import socket
import time
import random
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import httpx
import httpcore
from .config import now

class AccessBlocked(RuntimeError):
    pass

class IncompleteSource(RuntimeError):
    pass

class PublicNetworkBackend(httpcore.SyncBackend):
    """Resolver y conectar a la IP validada conservando Host/SNI del origen original."""
    def connect_tcp(self,host,port,timeout=None,local_address=None,socket_options=None):
        addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError('DNS resolvió una red privada/reservada al conectar')
        # create_connection recibe una IP numérica; no vuelve a resolver el nombre remoto.
        return super().connect_tcp(addresses[0][4][0],port,timeout,local_address,socket_options)

def validate_url(url):
    p = urlsplit(url)
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}:
        raise ValueError('URL HTTP(S) pública inválida')
    host = p.hostname.rstrip('.').lower()
    if host == 'linkedin.com' or host.endswith('.linkedin.com'):
        raise ValueError('LinkedIn excluido por configuración del usuario')
    addresses = socket.getaddrinfo(host, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(addr[4][0]).is_global for addr in addresses):
        raise ValueError('Red local, privada o reservada no permitida')
    return url

class WebClient:
    def __init__(self, profile, db=None, transport=None, sleep=time.sleep, validator=validate_url):
        self.profile, self.db, self.sleep, self.validator = profile, db, sleep, validator
        if transport is None:
            transport=httpx.HTTPTransport(retries=0)
            # Punto de extensión de httpcore; httpx/httpcore están fijados y se prueba en vivo.
            transport._pool._network_backend=PublicNetworkBackend()
        self.client = httpx.Client(timeout=profile['http_timeout'], transport=transport,
                                   headers={'User-Agent':'CorkJobRadar/0.1 (+local personal job research; read-only)', 'Accept':'application/json,text/html;q=0.9,*/*;q=0.1'},
                                   follow_redirects=False, trust_env=False)
        self.last = {}
        self.robots = {}
        self.robots_failures = {}

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get(self, url, check_robots=False, accept=None):
        self.validator(url)
        if check_robots:
            self.check_robots(url)
        current = url
        for _ in range(8):
            self.validator(current)
            if check_robots and urlsplit(current).netloc != urlsplit(url).netloc:
                self.check_robots(current)
            response = self._request(current,accept)
            if response.status_code in {301,302,303,307,308}:
                current = urljoin(current, response.headers['location'])
                continue
            return response
        raise IncompleteSource('Demasiadas redirecciones; no se declara éxito')

    def _request(self, url, accept=None):
        domain = urlsplit(url).netloc
        cache_key = url + ('#accept='+accept if accept else '')
        cached = self.db.rows('SELECT * FROM http_cache WHERE url=?', (cache_key,)) if self.db else []
        headers = {'Accept':accept} if accept else {}
        if cached:
            if cached[0]['etag']:
                headers['If-None-Match'] = cached[0]['etag']
            if cached[0]['modified']:
                headers['If-Modified-Since'] = cached[0]['modified']
        for attempt in range(self.profile['http_retries'] + 1):
            self.sleep(max(0, self.profile['domain_interval_seconds'] - (time.monotonic() - self.last.get(domain, 0))))
            try:
                with self.client.stream('GET', url, headers=headers) as stream:
                    self.last[domain] = time.monotonic()
                    body = bytearray()
                    for part in stream.iter_bytes():
                        body.extend(part)
                        if len(body) > self.profile['max_response_bytes']:
                            raise IncompleteSource('Respuesta supera el límite técnico de tamaño')
                    # iter_bytes ya descomprime. Evitar descomprimir dos veces al reconstruir.
                    response_headers = dict(stream.headers)
                    response_headers.pop('content-encoding',None)
                    response_headers.pop('content-length',None)
                    response = httpx.Response(stream.status_code, headers=response_headers, content=bytes(body), request=stream.request)
                if response.status_code == 304 and cached:
                    return httpx.Response(200, headers=json.loads(cached[0]['headers']), content=cached[0]['body'], request=response.request)
                if response.status_code in {401,403}:
                    raise AccessBlocked(f'HTTP {response.status_code}: acceso restringido, no significa cierre')
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == self.profile['http_retries']:
                        response.raise_for_status()
                    delay = 2 ** attempt + random.random()
                    retry = response.headers.get('Retry-After')
                    if retry:
                        try:
                            delay = max(delay, float(retry))
                        except ValueError:
                            delay = max(delay, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                    if delay > 60:
                        raise AccessBlocked(f'Retry-After exige esperar {delay:.0f}s; fuente suspendida')
                    self.sleep(delay)
                    continue
                if response.status_code in {301,302,303,307,308}:
                    return response
                response.raise_for_status()
                if 'text/html' in response.headers.get('content-type','') and any(
                    marker in response.text.lower() for marker in ('cf-chl-', 'verify you are human', 'access denied', 'captcha challenge')):
                    raise AccessBlocked('Respuesta de bloqueo/CAPTCHA; fuente suspendida')
                if self.db and response.status_code == 200:
                    self.db.execute('INSERT OR REPLACE INTO http_cache VALUES(?,?,?,?,?,?)',
                                    (cache_key,response.headers.get('etag'),response.headers.get('last-modified'),response.content,
                                     json.dumps(dict(response.headers)),now()))
                return response
            except httpx.TransportError:
                if attempt == self.profile['http_retries']:
                    raise
                self.sleep(2 ** attempt + random.random())

    def check_robots(self, url):
        p = urlsplit(url)
        base = f'{p.scheme}://{p.netloc}'
        if base in self.robots_failures:
            raise AccessBlocked(self.robots_failures[base])
        if base not in self.robots:
            rp = RobotFileParser()
            try:
                response = self.get(base + '/robots.txt')
                rp.parse(response.text.splitlines())
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    rp.parse([])
                else:
                    self.robots_failures[base]='No se pudo verificar robots.txt; dominio suspendido en esta ejecución'
                    raise AccessBlocked('No se pudo verificar robots.txt') from exc
            except (AccessBlocked,httpx.TransportError) as exc:
                self.robots_failures[base]='robots.txt inaccesible/restringido; dominio suspendido en esta ejecución'
                raise AccessBlocked(self.robots_failures[base]) from exc
            self.robots[base] = rp
        robot = self.robots[base]
        if not robot.can_fetch('CorkJobRadar',url):
            raise AccessBlocked('robots.txt restringe el acceso a esta URL')
        crawl_delay = robot.crawl_delay('CorkJobRadar') or robot.crawl_delay('*')
        if crawl_delay:
            self.sleep(crawl_delay)
