
import keystoneclient.v2_0.client as ksclient
import glanceclient,yaml

import json,datetime,threading,time,os,sys,re

from sql_alchemy_models import Base,User,Site,Credential

stream = open("glint_services.yaml", 'r')
cfg = yaml.load(stream)

_auth_url=cfg['auth_url']
_glance_url=cfg['glance_url']
_root_site=cfg['root_site']


def savi_fix(keystone,glance_ep):
    if 'iam.savitestbed.ca' in keystone.auth_url:
        return glance_ep.replace('/v1','')
    return glance_ep    

def _get_images(keystone):
    glance_ep = keystone.service_catalog.url_for(service_type='image',endpoint_type='publicURL')
    glance_ep = savi_fix(keystone,glance_ep)
    glance = glanceclient.Client('1',glance_ep,token=keystone.auth_token,insecure=True)
    images = glance.images.list()
    return images

def _auto_register_user(request,session):
    user_name=request.POST['USER_ID']
    token=request.POST['USER_TOKEN']
    tenant_name=request.POST['USER_TENANT']
    usr = session.query(User).filter_by(username=user_name,tenent=tenant_name).all()
    #usr = User.objects.filter(username=user_name,tenent=tenant_name)
    print "found %s"%usr
    if len(usr) is 0:
        print "User not seen before adding entry to db"
        usr = User(username=user_name,tenent=tenant_name,token=token,lastlogin=datetime.datetime.now())
        session.add(usr)
        session.commit()
        #usr.save()
        #usr = User(username='rondes', tenent='HEP', token='edspassword',lastlogin=dt.datetime.today())
        return usr
    else:
        print "User exists, so update date time"
        usr[0].lastlogin = datetime.datetime.now()
        usr[0].token = token
        #usr[0].save()
        session.commit()
        return usr[0]
    
def getImages(request,session):
    try:
        keystone = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        print "keystone info %s"%keystone.auth_tenant_id
        ret_obj = {}
        ret_obj['rows']=[]
        
        usr = _auto_register_user(request,session)
        images = _get_images(keystone)
        
        json_msg = {}
        rows = []
        sites = []
        
        sites.append({"name":"%s"%(_root_site),"tenent":"%s"%(request.POST['USER_TENANT'])})
        for index,image in enumerate(images):
            #print "found Image locally %s"%image
            img_obj = {}
            img_obj['image']=image.name
            img_obj['disk_format']=image.disk_format
            img_obj['container_format']=image.container_format
            site_list = []
            if image.owner == keystone.auth_tenant_id:
                site_list.append({"name":"%s"%(_root_site),"tenent":"%s"%(request.POST['USER_TENANT']),"is_public":"%s"%image.is_public,"is_owner":"True"})
            else:
                site_list.append({"name":"%s"%(_root_site),"tenent":"%s"%(request.POST['USER_TENANT']),"is_public":"%s"%image.is_public,"is_owner":"False"})
            img_obj['sites']=site_list
            rows.append(img_obj)
        #usr = session.query(User).filter_by(username=user_name,tenent=tenant_name).all()
        creds = session.query(Credential).filter_by(user=usr).all()
        #creds=credential.objects.filter(user=usr)
        print "Creds are %s"%creds
        for cred in creds:
            print "found cred %s"%cred
        
        return sites
    except Exception as e:
        print "Exception occurred %s"%e




    