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
    #url(r'^/imagedistribution/$', jsonservices.getImages,name='getImages'),
    map.connect('image_dist/imagedistribution', '/image_dist/imagedistribution/', method='getImages')
    map.connect('image_dist/addcredential', '/image_dist/addcredential/', method='addCredential')
    map.connect('image_dist/deletecredential', '/image_dist/deletecredential/', method='deleteCredential')
    map.connect('image_dist/listsites', '/image_dist/listsites/', method='listSites')
    map.connect('image_dist/createsite', '/image_dist/createsite/', method='createSite')
    map.connect('image_dist/deletesite', '/image_dist/deletesite/', method='deleteSite')
    
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
    
    def createSite(self,req):
        print "create Site"
        session = self.Session()
        response = glintclient.createsite(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
        )
        
    def deleteSite(self,req):
        print "delete Site"
        session = self.Session()
        response = glintclient.deletesite(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
        )
        
    def listSites(self,req):
        print "list sites"
        session = self.Session()
        response = glintclient.listsites(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
        )
    
    def addCredential(self,req):
        print "Add Credential"
        session = self.Session()
        response = glintclient.addcredential(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
        )    
        
    def deleteCredential(self,req):
        print "Add Credential"
        session = self.Session()
        response = glintclient.deletecredential(req,session);
        print "Received Response %s"%response
        return webob.Response(
            body='%s'%response
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
