
import keystoneclient.v2_0.client as ksclient
import glanceclient,yaml

import json,datetime,threading,time,os,sys,re

from sql_alchemy_models import Base,User,Site,Credential
from handlers.image_manager import savi_fix,imagecopyhandler,imageremovehandler

stream = open("glint_services.yaml", 'r')
cfg = yaml.load(stream)

_auth_url=cfg['auth_url']
_glance_url=cfg['glance_url']
_root_site=cfg['root_site']

image_copies=[]

def save(request,session):
    try:
        jsonMsg = request.POST['jsonMsg']
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        
        jsonMsgObj = json.loads(jsonMsg)
        print jsonMsgObj
        if jsonMsgObj['op'] == "add_img":
            print "Create image handler and go for it"
            img_hndlr = imagecopyhandler(request,jsonMsgObj['disk_format'],jsonMsgObj['container_format'],jsonMsgObj['image_name'],jsonMsgObj['image_dest'],jsonMsgObj['image_dest_tenent'],jsonMsgObj['img_src'][0]['site_name'],jsonMsgObj['img_src'][0]['tenent_name'],session)
            image_copies.append(img_hndlr)
            idx = image_copies.index(img_hndlr, )
            print "k add image now and return thread id %s"%idx
            img_hndlr.start()
            return '{"thread_id":%s}'%idx
        elif jsonMsgObj['op'] == "rem_img":
            print "try to remove image"
            img_hndlr = imageremovehandler(request,jsonMsgObj,session)
            image_copies.append(img_hndlr)
            idx = image_copies.index(img_hndlr,)
            img_hndlr.start()
            return '{"thread_id":%s}'%idx
        elif jsonMsgObj['op'] == "thread_update":
            jsonMsgObj['status']=image_copies[jsonMsgObj['thread_id']].getstatus()
            return json.dumps(jsonMsgObj)
        
        
        return json.dumps({"error":"Unkown operation %s"%jsonMsg['op']})
    except:
        return json.dumps({"error":"Invalid Save Credentials"})

    

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
            try:
                #print "Try to Create Keystone Client using un:%s pw:%s ten:%s auth_url: %s:%s/v2.0"%(cred.un,cred.pw,cred.tenent,cred.site.url,cred.site.authport)
                _keystone_ = ksclient.Client(insecure=True,username=cred.un,password=cred.pw,tenant_name=cred.tenent,auth_url="%s:%s/%s"%(cred.site_child.url,cred.site_child.authport,cred.site_child.version))
                #print "Success"
                images = _get_images(_keystone_)
                sites.append({"name":"%s"%(cred.site_child.name),"tenent":"%s"%(cred.tenent)})
                for index,image in enumerate(images):
                    #print "found %s"%image.name
                    inserted=False
                    for row in rows:
                        #print "In rows found image %s"%row['image']
                        if row['image'] == image.name:
                            if image.owner == _keystone_.auth_tenant_id:
                                row['sites'].append({"name":"%s"%(cred.site_child.name),"tenent":"%s"%(cred.tenent),"is_public":"%s"%image.is_public,"is_owner":"True"})
                            else:
                                row['sites'].append({"name":"%s"%(cred.site_child.name),"tenent":"%s"%(cred.tenent),"is_public":"%s"%image.is_public,"is_owner":"False"})
                            inserted=True
                        
                    if not inserted:
                        #print "found a new Image list" 
                        img_obj = {}
                        img_obj['image']=image.name
                        img_obj['disk_format']=image.disk_format
                        img_obj['container_format']=image.container_format
                        site_list = []
                        if image.owner == _keystone_.auth_tenant_id:
                            site_list.append({"name":"%s"%(cred.site_child.name),"tenent":"%s"%(cred.tenent),"is_public":"%s"%image.is_public,"is_owner":"True"})
                        else:
                            site_list.append({"name":"%s"%(cred.site_child.name),"tenent":"%s"%(cred.tenent),"is_public":"%s"%image.is_public,"is_owner":"False"})
                        img_obj['sites']=site_list
                        rows.append(img_obj)
            except Exception as e:
                print "Error Occurred getting images from %s error %s"%(cred.site_child.url,e)
        
        json_msg['sites']=sites
        json_msg['rows']=rows
        
        respstr = json.dumps(json_msg)
        
        return respstr
    except Exception as e:
        return json.dumps({"Error":"%s"%e})

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

def deletesite(request,session):
    try:
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        #pprint("glint recieved a valid user token for %s"%request.POST['USER_ID'])
        user_name=request.POST['USER_ID']
        site_id = request.POST['SITE_ID']
        
        s = session.query(Site).filter_by(id=site_id).first()
        #s=site.objects.filter(pk=site_id)
        print "Filter credentials for site %s"%s
        
        cred = session.query(Credential).filter_by(site=s.id).all()
        #cred = credential.objects.filter(site=s)
        print "Creds %s"%cred
        if len(cred) == 0:
        #print "create site with %s"%site_data
            #s=site.objects.filter(pk=site_id)
            print "Delete Site"
            session.delete(s)
            session.commit()
            return json.dumps({"Result":"Successful Delete"})
        else:
            return json.dumps({"Result":"There are still credentials on this site %s"%site_id})
        
    except Exception as e:
        return json.dumps({"Result":"Invalid Credentials Who knows %s"%e})
    
    
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
    
def deletecredential(request,session):
    try:
        print "Try to Remove Credential with %s"%request.POST['USER_TOKEN']
        #print "check if request is valid, then check if user has a credential for this site"
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
    
        site_id = request.POST['SITE_ID']
        user_name = request.POST['USER_ID']
        #ck_type = request.POST['CK_TYPE']
        print "have un: %s and site id :%s "%(user_name,site_id)
        
        usr = session.query(User).filter_by(username=user_name,tenent=request.POST['USER_TENANT']).all()
        #usr = user.objects.filter(username=user_name,tenent=request.POST['USER_TENANT'])
        #print "need to get past this %s"%usr
        #user_id = usr[0].id
        
        cred = session.query(Credential).filter_by(user=usr[0].id,site=site_id).first()
        #cred = credential.objects.filter(user=user_id,site=site_id)
        print "Found Cred %s"%cred
        #cred.delete()
        session.delete(cred)
        session.commit()
        print "Cred Removed"
        
        return json.dumps({"Result":"Success removing Credential"})
        #print "for user %s on site %s we found cred %s"%(user_id,site_id,cred)
    except Exception as e:
        
        return json.dumps({"Result":"Failure Removing Credential %s"%e})
    

def getcredential(request,session):
    try:
        #print "check if request is valid, then check if user has a credential for this site"
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        #pprint("glint recieved a valid user token for %s"%request.POST['USER_ID'])
        site_id = request.POST['SITE_ID']
        user_name = request.POST['USER_ID']
        #ck_type = request.POST['CK_TYPE']
        #print "have un: %s and site id :%s "%(user_name,site_id)
        
        usr = session.query(User).filter_by(username=user_name,tenent=request.POST['USER_TENANT']).all()
        #usr = user.objects.filter(username=user_name,tenent=request.POST['USER_TENANT'])
        #print "need to get past this %s"%usr
        #user_id = usr[0].pk
        #user_id = user_obj[0].pk
        #print "site id hopefully %s and user name %s id is %s"%(site_id,user_name,user_id)
        #cred = None
        #if ck_type == "ONE":
        cred = session.query(Credential).filter_by(user=usr[0].id,site=site_id).all()
        #cred = credential.objects.filter(user=usr[0].pk,site=site_id)
        
        if len(cred) is 1:
            #print "Found Credential Return as Json obj %s"%cred
            cred_obj={}
            cred_obj['cred_id']=cred[0].un
            cred_obj['tenant']=cred[0].tenent
            return json.dumps(cred_obj)
        else:
            return json.dumps({"Result":"Valid User Credentials, but site %s does not have your credentials for user %s"%(site_id,usr[0].id)})
        #else:
        #    cred = credential.objects.filter(site=site_id)
    except:
        return json.dumps({"Result":"Invalid User Credentials"})

def hascredential(request,session):
    try:
        #print "check if request is valid, then check if user has a credential for this site"
        os_user = ksclient.Client(insecure=True,token=request.POST['USER_TOKEN'],tenant_name=request.POST['USER_TENANT'],auth_url=_auth_url)
        #pprint("glint recieved a valid user token for %s"%request.POST['USER_ID'])
        site_id = request.POST['SITE_ID']
        user_name = request.POST['USER_ID']
        ck_type = request.POST['CK_TYPE']
        #print "have un: %s and site id :%s "%(user_name,site_id)
        
        usr = session.query(User).filter_by(username=user_name,tenent=request.POST['USER_TENANT']).all()
        #usr = user.objects.filter(username=user_name,tenent=request.POST['USER_TENANT'])
        #print "need to get past this %s"%usr
        #user_id = usr[0].pk
        #user_id = user_obj[0].pk
        #print "site id hopefully %s and user name %s id is %s"%(site_id,user_name,user_id)
        cred = None
        if ck_type == "ONE":
            cred = session.query(Credential).filter_by(user=usr[0].id,site=site_id).all()
            #cred = credential.objects.filter(user=user_id,site=site_id)
        else:
            cred = session.query(Credential).filter_by(site=site_id).all()
            #cred = credential.objects.filter(site=site_id)
        #print "for user %s on site %s we found cred %s"%(user_id,site_id,cred)
        if len(cred) == 0:
            #str_js = '{"result":False,"error":False}'
            str_js={}
            str_js['result']=False
            str_js['error']=False
            #ret_arr = []
            #ret_arr.append(str_js)
            return json.dumps(str_js)
        else: 
            str_js={}
            str_js['result']=True
            str_js['error']=False
            #ret_arr = []
            #ret_arr.append(str_js)
            return json.dumps(str_js)
    except:
        e = sys.exc_info()[0]
        print "Exception %s"%e
        str_js={}
        str_js['result']=False
        str_js['error']=True
        #ret_arr = []
        #ret_arr.append(str_js)
        return json.dumps(str_js)
    
    

    