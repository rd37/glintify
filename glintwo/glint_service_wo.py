'''
Created on Jul 10, 2015

@author: ronaldjosephdesmarais
'''
'''
A minimal example of how to use Paste and WebOb to build a custom
WSGI app and serve it.

Depends on:
* paste - http://pypi.python.org/pypi/Paste
* webob - http://pypi.python.org/pypi/WebOb/1.1.1
* routes - http://pypi.python.org/pypi/Routes/1.12.3

I (marmida) still think this is less appropriate than using CouchDB; you'll need
to handle routing and controllers manually to reproduce Couch's default behavior 
(a RESTful interface to db records).

I extracted this from an app I was working on a while ago:
https://github.com/marmida/catalog/blob/master/server/app.py

I originally built that code to work with neo4j, and then switched to sqlite.
At the time, neo4j required thread isolation; I kept that after I moved to sqlite.
If you find yourself hitting threading issues (e.g. sqlite doesn't like being 
called from paste worker threads), you can look at my code on GitHub for a solution.
'''
#from os import environ
import sqlalchemy

import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker

#from sql_alchemy_models import user
from sql_alchemy_models import Base,User
import glint_service as glintclient

import paste.fileapp
import paste.httpserver
import routes
import webob
import webob.dec
import webob.exc

#environ['DJANGO_SETTINGS_MODULE'] = "glintservice.settings"

#from imagedist.models import site,credential
#from imagedist.models import user
 
HOST = '0.0.0.0'
PORT = 9494
 
class GlintService(object):
    '''
    A WSGI "application."

    See: http://pythonpaste.org/do-it-yourself-framework.html#writing-a-wsgi-application
    '''
 
    # Our routes map URIs to methods of this app, and define how to extract args from requests
    # Complaint: in order to make this RESTful, you have to plan routes yourself
    map = routes.Mapper()
    map.connect('index', '/', method='index')
    map.connect('greet', '/greet/{name}', method='greet')
    map.connect('django_test', '/django', method='django_test')
    map.connect('alchemy_get', '/alchemy_get/{un}', method='alchemy_get')
    
    #url(r'^/imagedistribution/$', jsonservices.getImages,name='getImages'),
    map.connect('image_dist/imagedistribution', '/image_dist/imagedistribution/', method='getImages')
    
    @webob.dec.wsgify
    def __call__(self, req):
        '''
        Glue.  A WSGI app is a callable; thus in order to make this object an application, 
        we define __call__ to make it callable.  We then ask our Mapper to do some routing,
        and dispatch to the appropriate method.  That method must return a webob.Response.
        '''
        results = self.map.routematch(environ=req.environ)
        if not results:
            return webob.exc.HTTPNotFound()
        match, route = results
        link = routes.URLGenerator(self.map, req.environ)
        req.urlvars = ((), match)
        kwargs = match.copy()
        method = kwargs.pop('method')
        req.link = link
        return getattr(self, method)(req, **kwargs)
 
    def getImages(self,req):
        print "Get Images"
        session = self.Session()
        response = glintclient.getImages(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
        )
        
    def alchemy_get(self,req,un):
        print "getting alcehcmy"
        session = self.Session()
        our_users = session.query(User).all()
        
        return webob.Response(
            body='<html><body>First user %s </body></html>'%our_users
        )
        
    def django_test(self, req):
        session = self.Session()
        ed_user = User(username='rondes', tenent='HEP', token='edspassword',lastlogin=dt.datetime.today())
        session.add(ed_user)
        session.commit()
        return webob.Response(
            body='<html><body>What wait %s ok a second</body></html>'%ed_user.id
        )
        
    def index(self, req):
        '''
        Controller #1: a landing page.
        '''
        return webob.Response(
            body='''<html><body>
                    <p>Your name: 
                        <form onSubmit="location.href='/greet/' + encodeURI(document.getElementById('name_input').value); return false;">
                            <input type="text" value="" id="name_input"/>
                        </form>
                    </p>
                </body></html>'''
        )
        
    def greet(self, req, name=None):
        '''
        Controller #2: do something with a URI arg to show dynamic behavior.
        '''
        return webob.Response(
            body='<html><body>Dear %s, you\'re a cool dude.</body></html>' % name
        )
 
    def init_db(self):
        print "initialize db"
        self.engine = create_engine('sqlite:///:memory2:', echo=True)
        Base.metadata.create_all(self.engine) 
        self.Session = sessionmaker(bind=self.engine)
        
def main():
    '''
    CLI entry point.
    '''
    app= GlintService()
    app.init_db()
    paste.httpserver.serve(app, host=HOST, port=PORT)
 
# for importability, don't run main() unless we really mean to
if __name__ == '__main__':
    main()
