'''
Created on Jul 15, 2015

@author: ronaldjosephdesmarais
'''

import keystoneclient.v2_0.client as ksclient
import glanceclient,yaml

import json,datetime,threading,time,os,sys,re
from sql_alchemy_models import Base,User,Site,Credential

stream = open("glint_services.yaml", 'r')
cfg = yaml.load(stream)

_auth_url=cfg['auth_url']
_glance_url=cfg['glance_url']
_root_site=cfg['root_site']


thread_id=0

def savi_fix(keystone,glance_ep):
    if 'iam.savitestbed.ca' in keystone.auth_url:
        return glance_ep.replace('/v1','')
    return glance_ep

def touch(path):
    os.makedirs(path)
    

class imageremovehandler():
    jsonMsgObj=''
    status="incomplete"
    local_user=''
    local_tenent=''
    
    def __init__(self,request,jsonMsgObj,session):
        self.jsonMsgObj=jsonMsgObj
        self.local_user=request.POST['USER_ID']
        self.local_tenent=request.POST['USER_TENANT']
        self.session=session
     
    def getstatus(self):
        return self.status   
    
    def start(self):
        print "create thread and start image removal work"
        self.thread = threading.Thread(target=self.remove_image,args=[] )
        self.thread.start()
        
    def remove_image(self):
        print "remove image as per jsonMsgObj"
        try:
            keystone_src=''
            if self.jsonMsgObj['img_src_site'] ==_root_site:
                #print "remove from Rat is not allowed"
                self.status="complete"
                return
            else:
                src_site_name = self.session.query(Site).filter_by(name=self.jsonMsgObj['img_src_site']).all()
                #src_site_name = site.objects.filter(name=self.jsonMsgObj['img_src_site'])
                user_name = self.session.query(User).filter_by(username=self.local_user,tenent=self.local_tenent).all()
                #user_name = user.objects.filter(username=self.local_user,tenent=self.local_tenent)
                #print "now generate credentials"
                cred = self.session.query(Credential).filter_by(user=user_name,site=src_site_name,tenent=self.jsonMsgObj['image_src_tenent']).all()
                #cred = credential.objects.filter(user=user_name,site=src_site_name,tenent=self.jsonMsgObj['image_src_tenent'])
                print "now get keystoe client"
                keystone_src = ksclient.Client(insecure=True,auth_url="%s:%s/%s"%(src_site_name[0].url,src_site_name[0].authport,src_site_name[0].version),username=cred[0].un,password=cred[0].pw,tenant_name=cred[0].tenent)
            print "now create service ep"
            glance_ep_src = keystone_src.service_catalog.url_for(service_type='image',endpoint_type='publicURL')
            glance_ep_src = savi_fix(keystone_src,glance_ep_src)
            glance_src = glanceclient.Client('1',glance_ep_src,token=keystone_src.auth_token,insecure=True)
            print "now list images"
            images = glance_src.images.list()
    #image = images.find()
            for index,image in enumerate(images):
                #pprint('Images:%s:%s' %(index,image))
                if image.name == self.jsonMsgObj['image_name']:
                    print "found image name %s" % image.name
                    image.delete()
                    print "done deleting image"
            self.status="complete"
        except:
            print "error occurred removing image"
        
    
class imagecopyhandler():
    status="incomplete"
    thread=''
    img_name=''
    disk_format=''
    container_format=''
    source_site=''
    source_tenent=''
    remote_site=''
    remote_tenent=''
    count=0
    copy_from_root=False
    local_user=''
    user_token=''
    local_tenent=''
    
    
    def __init__(self,request,diskformat,containerformat,imagename,remotesite,remotetenent,sourcesite,sourcetenent):
        self.container_format=containerformat
        self.disk_format=diskformat
        self.img_name=imagename
        self.remote_site=remotesite
        self.source_site=sourcesite
        self.remote_tenent=remotetenent
        self.source_tenent=sourcetenent
        self.local_user=request.POST['USER_ID']
        self.user_token=request.POST['USER_TOKEN']
        self.local_tenent=request.POST['USER_TENANT']
        if sourcesite == _root_site:
            self.copy_from_root=True
        else:
            self.copy_from_root=False
        
    def getstatus(self):
        self.count=self.count+1
        return self.status
    
    def start(self):
        print "create thread and start work"
        self.thread = threading.Thread(target=self.transfer_image,args=[self.img_name,self.remote_site,self.source_site] )
        self.thread.start()
    
    def transfer_image(self,imageName,remoteSite,sourceSite):
        print "start image transfer %s from %s:%s to %s:%s"%(self.img_name,self.source_site,self.source_tenent,self.remote_site,self.remote_tenent)   
        directory=''
        
        try:
            keystone_src=''
            if self.source_site ==_root_site:
                #print "copy from Rat is source"
                keystone_src = ksclient.Client(insecure=True,token=self.user_token,tenant_name=self.local_tenent,auth_url=_auth_url)
            else:
                src_site_name = self.session.query(Site).filter_by(name=self.source_site).all()
                #src_site_name = site.objects.filter(name=self.source_site)
                user_name = self.session.query(User).filter_by(username=self.local_user,tenent=self.local_tenent).all()
                #user_name = user.objects.filter(username=self.local_user,tenent=self.local_tenent)
                
                cred = self.session.query(Credential).filter_by(user=user_name,site=src_site_name,tenent=self.source_tenent).all()
                #cred = credential.objects.filter(user=user_name,site=src_site_name,tenent=self.source_tenent)
                print "copy from other %s:%s/%s"%(src_site_name[0].url,src_site_name[0].authport,src_site_name[0].version)
                print "using creds %s:%s,%s"%(cred[0].un,cred[0].pw,cred[0].tenent)
                keystone_src = ksclient.Client(insecure=True,auth_url="%s:%s/%s"%(src_site_name[0].url,src_site_name[0].authport,src_site_name[0].version),username=cred[0].un,password=cred[0].pw,tenant_name=cred[0].tenent)
            
            glance_ep_src = keystone_src.service_catalog.url_for(service_type='image',endpoint_type='publicURL')
            glance_ep_src = savi_fix(keystone_src,glance_ep_src) 
            glance_src = glanceclient.Client('1',glance_ep_src,token=keystone_src.auth_token,insecure=True)
            
            images = glance_src.images.list()
            img_id=''
            for img in images:
                if img.name == self.img_name:
                    img_id=img.id
                
            image_src = glance_src.images.get(img_id)
            img_data = glance_src.images.data(image_src,True)
            directory = "/home/ubuntu/imgcopytmp/%s/%s_%s/"%(img_id,self.remote_site,self.remote_tenent)
            touch(directory)
            with open('%s/%s'%(directory,self.img_name),'wb') as f:
                for data_chunk in img_data:
                    f.write(data_chunk)
            
            print "image download complete"
        except Exception as e:
            return json.dumps({"error":"error Downloading Image: %s "%e })      
       
        try:
            print "Create Image Remote Upload %s,%s,%s to %s"%(self.disk_format,self.container_format,self.img_name,self.remote_site)
            
            keystone_dest=''
            if self.remote_site ==_root_site:
                print "copy to Rat is dest"
                keystone_dest = ksclient.Client(insecure=True,token=self.user_token,tenant_name=self.local_tenent,auth_url=_auth_url)
            else:
                remote_site_name = self.session.query(Site).filter_by(name=self.remote_site).all()
                #remote_site_name = site.objects.filter(name=self.remote_site)
                
                user_name = self.session.query(User).filter_by(username=self.local_user,tenent=self.local_tenent).all()
                #user_name = user.objects.filter(username=self.local_user,tenent=self.local_tenent)
                
                cred = self.session.query(Credential).filter_by(user=user_name,site=remote_site_name,tenent=self.remote_tenent).all()
                #cred = credential.objects.filter(user=user_name,site=remote_site_name,tenent=self.remote_tenent)
                keystone_dest = ksclient.Client(insecure=True,auth_url="%s:%s/%s"%(remote_site_name[0].url,remote_site_name[0].authport,remote_site_name[0].version),username=cred[0].un,password=cred[0].pw,tenant_name=cred[0].tenent)
                
            glance_ep_dest = keystone_dest.service_catalog.url_for(service_type='image',endpoint_type='publicURL')
            glance_ep_dest = savi_fix(keystone_dest,glance_ep_dest)
            glance_dest = glanceclient.Client('1',glance_ep_dest,token=keystone_dest.auth_token,insecure=True)
            
            file_loc='%s%s'%(directory,self.img_name)
            fimage = open(file_loc)
            glance_dest.images.create(name=self.img_name,is_public="False",disk_format=self.disk_format,container_format=self.container_format,owner=self.remote_tenent,data=fimage)
            
            print "done update with data upload"
            
        except:
            print "error uploading image occurred"
            
        print "done remote file transfer"
        self.status="complete"