'''
Created on Jul 13, 2015

@author: ronaldjosephdesmarais
'''
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Sequence
from sqlalchemy.orm import relationship

Base = declarative_base()

class Credential(Base):
    __tablename__ = 'credentials'
    id = Column(Integer, Sequence('credential_id_seq'), primary_key=True)
    user = Column(Integer,ForeignKey("users.id"), nullable=False)
    user_child = relationship("User")
    site = Column(Integer,ForeignKey("sites.id"), nullable=False)
    site_child = relationship("Site")
    un = Column(String)
    pw = Column(String)
    tenent = Column(String)
    
    def __repr__(self):
        return self.un
    
class Site(Base):
    __tablename__ = 'sites'
    id = Column(Integer, Sequence('site_id_seq'), primary_key=True)
    name = Column(String)
    url = Column(String,unique=True)
    authport = Column(String)
    version = Column(String)
    #Sites
    #OPENSTACK, NIMBUS,EC2,AZURE = 'Openstack','Nimbus','EC2','Azure'
    #SITETYPES = ( (OPENSTACK,_(OPENSTACK)),(NIMBUS,_(NIMBUS)),(EC2,_(EC2)) ,(AZURE,_(AZURE))  )
    
    type = Column(String,default='OPENSTACK')
        
    def __repr__(self):
        return self.name

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    username = Column(String)
    tenent   = Column(String)
    token    = Column(String)
    lastlogin = Column(DateTime)
    
    def __repr__(self):
        return self.username
