import os

from urllib import unquote
from urlparse import urlparse

from jolicloud_daemon.enums import TRUSTED_DOMAINS

from twisted.web import resource, static, http
from twisted.web.resource import Resource, ForbiddenResource

class JoliFile(Resource):
    def render_GET(self, request):
        
        if os.environ.get('JPD_DEBUG', '0') == '0':
            headers = request.getAllHeaders()
            if 'referer' in headers:
                parsed_referer = urlparse(headers['referer'])
                if not (parsed_referer.hostname and '.'.join(parsed_referer.hostname.split('.')[-2:]) in TRUSTED_DOMAINS):
                    return ForbiddenResource().render(request)
            elif request.args.get('session', [False])[0] != os.environ.get('JD_SESSION', True):
                return ForbiddenResource().render(request)
        
        path = unquote(request.args.get('path', ['/'])[0])
        root = unquote(request.args.get('root', ['home'])[0])
        
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        static_file = static.File('%s/%s' % (root, path.strip('/')))
        
        if static_file.type is None:
            static_file.type, static_file.encoding = static.getTypeAndEncoding(
                static_file.basename(),
                static_file.contentTypes,
                static_file.contentEncodings,
                static_file.defaultType
            )
        
        if static_file.type.startswith('image/') or static_file.type.startswith('video/') or static_file.type.startswith('audio/'):
            return static_file.render_GET(request)
        else:
            return ForbiddenResource().render(request)

resource = JoliFile()
