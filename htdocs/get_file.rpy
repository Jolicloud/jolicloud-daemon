import os

from urllib import unquote

from twisted.web import resource, static, http
from twisted.web.resource import Resource, ForbiddenResource

class JoliFile(Resource):
    def render_GET(self, request):
        
        if os.environ.get('JPD_DEBUG', '0') == '0':
           headers = request.getAllHeaders()
           if 'referer' not in headers or headers['referer'] not in ['http://my.jolicloud.com/', 'http://my.jolicloud.local/']:
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
