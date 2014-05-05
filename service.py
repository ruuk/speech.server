#! /usr/bin/env python
### Run Python scripts as a service example (ryrobes.com)
### Usage : python aservice.py install (or / then start, stop, remove)

import win32service
import win32serviceutil
import win32api
import win32event
from lib import util
import sys

class aservice(win32serviceutil.ServiceFramework):
	_svc_name_ = "speech.server"
	_svc_display_name_ = "speech.server"
	_svc_description_ = "HTTP speech server. Serves speech wavs for text requests, or speaks on server end."
			
	def __init__(self, args):
		self.server = None
		win32serviceutil.ServiceFramework.__init__(self, args)
		self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)				 

	def SvcStop(self):
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		win32event.SetEvent(self.hWaitStop)
		if self.server: self.server.shutdownServer()
			
	def SvcDoRun(self):
		import servicemanager		
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,servicemanager.PYS_SERVICE_STARTED,(self._svc_name_, '')) 
		import server
		self.server = server
		server.start()
#		 #self.timeout = 640000		#640 seconds / 10 minutes (value is in milliseconds)
#		 self.timeout = 120000		#120 seconds / 2 minutes
#		 # This is how long the service will wait to run / refresh itself (see script below)
#
#		 while 1:
#			 # Wait for service stop signal, if I timeout, loop again
#			 rc = win32event.WaitForSingleObject(self.hWaitStop, self.timeout)
#			 # Check to see if self.hWaitStop happened
#			 if rc == win32event.WAIT_OBJECT_0:
#				 # Stop signal encountered
#				 servicemanager.LogInfoMsg("SomeShortNameVersion - STOPPED!")	#For Event Log
#				 break
#			 else:
#
#						#Ok, here's the real money shot right here.
#						#[actual service code between rests]
#						try:
#							 file_path = "C:\whereever\my_REAL_py_work_to_be_done.py"
#							 execfile(file_path)					#Execute the script
#
#							 inc_file_path2 = "C:\whereever\MORE_REAL_py_work_to_be_done.py"
#							 execfile(inc_file_path2)			#Execute the script
#						except:
#							 pass
#						#[actual service code between rests]


def ctrlHandler(ctrlType):
	return True
			
def LOG(msg):
	import servicemanager
	servicemanager.LogInfoMsg("speech.server: {0}".format(msg))
	
if __name__ == '__main__':
	if sys.platform.startswith('win'):
		util.LOG = LOG
		win32api.SetConsoleCtrlHandler(ctrlHandler, True)	 
		win32serviceutil.HandleCommandLine(aservice)
	else:
		print 'THIS SERVICE MUST BE RUN ON WINDOWS'
