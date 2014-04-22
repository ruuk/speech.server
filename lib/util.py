# -*- coding: utf-8 -*-
import os, sys, time, binascii

def sleep(ms):
	time.sleep(ms/1000.0)
	
ABORTREQUESTED = False
def abortRequested():
	return ABORTREQUESTED
	
def ERROR(txt,hide_tb=False,notify=False):
	if isinstance (txt,str): txt = txt.decode("utf-8")
	short = str(sys.exc_info()[1])
	if hide_tb:
		LOG('ERROR: {0} - {1}'.format(txt,short))
		return short
	LOG('ERROR: ' + txt)
	import traceback
	traceback.print_exc()
	return short
	
def LOG(message):
	message = 'speech.server: ' + message
	print message
	
def getSetting(key,default=None):
	return default

def setSetting(key,value):
	pass

def processSetting(setting,default):
	if not setting: return default
	if isinstance(default,bool):
		return setting.lower() == 'true'
	elif isinstance(default,int):
		return int(float(setting or 0))
	elif isinstance(default,list):
		if setting: return binascii.unhexlify(setting).split('\0')
		else: return default
	
	return setting
	
def processSettingForWrite(value):
	if isinstance(value,list):
		value = binascii.hexlify('\0'.join(value))
	elif isinstance(value,bool):
		value = value and 'true' or 'false'
	return str(value)
	
def get_tmpfs():
	for tmpfs in ('/run/shm','/dev/shm','/tmp'):
		if os.path.exists(tmpfs): return tmpfs
	import tempfile
	return tempfile.gettempdir()
		
def isATV2():
	return False
	
def isOpenElec():
	return False
	
def commandIsAvailable(command):
	for p in os.environ["PATH"].split(os.pathsep):
		if os.path.isfile(os.path.join(p,command)): return True
	return False
	
DEBUG = True