import os
import cgi

from twisted.web import resource, static

class JoliFile(resource.Resource):
    def render_GET(self, request):
        path = cgi.escape(request.args.get('path', ['/'])[0])
        root = cgi.escape(request.args.get('root', ['home'])[0])
        
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        static_file = static.File('%s/%s' % (root, path.strip('/')))
        return static_file.render_GET(request)

resource = JoliFile()
