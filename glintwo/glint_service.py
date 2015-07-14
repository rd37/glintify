
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
        print "Filter creds by user %s"%usr.id
        creds = session.query(Credential).filter_by(user=usr.id).all()
        #creds=credential.objects.filter(user=usr)
        print "Creds are %s"%creds
        for cred in creds:
            print "found cred %s"%cred
        
        return sites
    except Exception as e:
        print "Exception occurred %s"%e

def createsite(request,session):
    try:
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        #pprint("glint recieved a valid user token for %s"%request.POST['USER_ID'])
        user_name=request.POST['USER_ID']
        site_data = eval(request.POST['SITEDATA'])
        # print "create site with %s"%site_data
        site_url=site_data['url']
        rexp_url_proc = re.compile('http[s]?://[a-zA-Z0-9._-]+')
        url_str = rexp_url_proc.search(site_url)
        
        port_vers = re.split('http[s]?://[a-zA-Z0-9._-]+:',site_url)
        if port_vers[0] == site_url:
            port_vers = re.split('http[s]?://[a-zA-Z0-9._-]+',site_url)
            port_vers[1]="443%s"%port_vers[1]
        port_version_array = re.split('/',port_vers[1],1)
        #port_version_array = re.split('/',port_vers[1])
        print "create site found found %s with %s and %s"%(url_str.group(0),port_version_array[0],port_version_array[1])
        if url_str.group(0) is None or len(port_version_array) is not 2:
            return {"Result":"Site Url invalid"}
        
        
        s=Site(name=site_data['name'],url=url_str.group(0),authport=port_version_array[0],version=port_version_array[1],type=site_data['disk_format'])
        #s.save()
        session.add(s)
        session.commit()
        print "create site complete with %s"%s.id
        return json.dumps({"Result":"Success","site_id":s.id})
    except:
        return json.dumps({"Result":"Invalid Credentials or Site already in Use"})
    
def listsites(request,session):
    print "try to list sites-oK"
    try:
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        print "Creds ok lets query sites"
        s = session.query(Site).all()
        #s = site.objects.filter()
        
        response = []
        for sobj in s:
            sobjstr = '{"name":"%s","url":"%s:%s/%s","authport":"%s","version":"%s","type":"%s","pk":"%s"}'%(sobj.name,sobj.url,sobj.authport,sobj.version,sobj.authport,sobj.version,sobj.type,sobj.id)
            response.append(sobjstr)
        respstr = json.dumps(response)
        
        return respstr
    except Exception as e:
        return json.dumps({"error":"%s"%e})

def addcredential(request,session):
    try:
        print "try to add credential un:%s pw:%s"%(request.POST['USER_TOKEN'],request.POST['USER_TENANT'])
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        #pprint("glint recieved a valid user token for %s"%request.POST['USER_ID'])
        print "Valid user"
        cred_data = eval(request.POST['CREDDATA'])
           
        usr = _auto_register_user(request,session)
        
        print "find site with %s"%cred_data['site_id']
        ste = session.query(Site).filter_by(id=cred_data['site_id']).all()
        #ste = site.objects.filter(pk=cred_data['site_id'])
        
        print "add credential with %s"%cred_data
        
        #user site and tenent need to be unique
        #cred = session.query(Credential).filter_by(user=usr.id).all()
        cred = session.query(Credential).filter_by(user=usr.id,site=ste[0].id,tenent=cred_data['tenent']).all()
        if len(cred) is 0:
            print "credentials does not exist for this user/site/tenent combo so create it"
            
            cred = Credential(user=usr.id,site=ste[0].id,tenent=cred_data['tenent'],un=cred_data['username'],pw=cred_data['password'])
            session.add(cred)
            session.commit()
            #cred.save()
        else:
            print "credentials exists for this user/site/tenent combo, assume an update"
            cred[0].un=cred_data['username']
            cred[0].pw=cred_data['password']
            #cred[0].save()
            session.commit()
        return json.dumps({"Result":"Sites: add Credential"})
    except Exception as e:
        return json.dumps({"Result Error":"error %s"%e})
    


    