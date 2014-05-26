# -*- coding: utf-8 -*-
import os, sys, time, binascii

_SETTINGS = {}

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
	
def sleep(ms):
	time.sleep(ms/1000.0)
	
ABORTREQUESTED = False
def abortRequested():
	return ABORTREQUESTED

def configDirectory():
	from lib import appdirs
	return appdirs.user_data_dir('speech.server','ruuksoft')
	
def profileDirectory():
	import tempfile
	return tempfile.gettempdir()

def backendsDirectory():
	return os.path.join(os.path.dirname(__file__),'backends')
	
def getSetting(key,default=None):
	return processSetting(_SETTINGS.get(key),default)

def setSetting(key,value):
	global _SETTINGS
	_SETTINGS[key] = processSettingForWrite(value)

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
	
def getTmpfs():
	for tmpfs in ('/run/shm','/dev/shm','/tmp'):
		if os.path.exists(tmpfs): return tmpfs
	import tempfile
	return tempfile.gettempdir()
	
def isWindows():
	return sys.platform.lower().startswith('win')

def isOSX():
	return sys.platform.lower().startswith('darwin')
	
def isATV2():
	return False
	
def isOpenElec():
	return False
	
def commandIsAvailable(command):
	for p in os.environ["PATH"].split(os.pathsep):
		if os.path.isfile(os.path.join(p,command)): return True
	return False
	
DEBUG = True