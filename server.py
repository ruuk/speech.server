#! /usr/bin/env python

__version__ = '0.0.3'

import os, ConfigParser, socket, BaseHTTPServer, cgi, urlparse, shutil, StringIO, optparse, copy
from lib import backends
from lib import util
from lib import appdirs

TTS = None
SERVER = None
ACTIVE = True

user_path = appdirs.user_data_dir('speech.server','ruuksoft')
CONFIG_PATH = os.path.join(user_path,'config.txt')
		
class TTSHandler:
	preferred_player = None
	def __init__(self):
		self.backend = None

	def setEngine(self,provider,wav_stream=False):
		if not provider:
			if self.backend: return
		else:
			if self.backend and self.backend.provider == provider: return
		if wav_stream:
			backend = backends.getWavStreamBackend(provider)
		else:
			backend = backends.getBackend(provider)
		if backend:
			if self.backend: self.backend._close()
			if self.preferred_player:
				util.setSetting('player.' + provider, self.preferred_player)
			self.backend = backend()
			util.LOG('Backend changed to: {0}'.format(self.backend.provider))

	def setVoice(self,voice):
		if not self.backend or not voice or not '.' in voice: return
		provider, voice = voice.split('.',1)
		if provider != self.backend.provider: return
		util.setSetting('voice.' + provider, voice)
		
	def setRate(self,rate):
		if not rate: return
		try:
			rate = int(rate)
		except:
			return
		rate = self.backend.scaleSpeed(rate)
		util.setSetting('speed.' + self.backend.provider, rate)
		
	def update(self):
		if self.backend: self.backend.update()
		
	def say(self,text):
		if self.backend: self.backend.say(text,False)
		
	def stop(self):
		if self.backend: self.backend._stop()
		
	def voices(self,provider=None):
		backend = None
		if provider: backend = backends.getBackend(provider)
		if not backend: return
		with backend() as backend: voices = backend.voices()
		if not voices: return None
		for i in range(len(voices)):
			voices[i] = '{0}.{1}'.format(backend.provider,voices[i])
		return '\n'.join(voices)

	def engines(self,can_stream_wav=False):
		engines = backends.getAvailableBackends(can_stream_wav)
		if not engines: return None
		ret = []
		for b in engines:
			ret.append('{0}.{1}'.format(b.provider,b.displayName))
		return '\n'.join(ret)

	def getWavStream(self,text):
		if not text: return
		if not self.backend.canStreamWav: return None
		return self.backend.getWavStream(text)
		
	def close(self):
		if self.backend: self.backend._close()

class PostData():
	def __init__(self,handler,method='POST'):
		environ = {'REQUEST_METHOD':method, 'CONTENT_TYPE':'Content-Type' in handler.headers and handler.headers['Content-Type'] or ''}
		self.form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ=environ)
		
	def get(self,name,default=None):
		if not name in self.form: return default
		return self.form[name].value
	
class SpeechHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def log_message(self,fmt,*args):
		pass

	def do_GET(self):
		path = self.path.split('?')[0]
		data = {}
		if '?' in self.path: data = dict(urlparse.parse_qsl(self.path.split('?')[-1]))
		if path == '/voices':
			self.voices(data)
		elif path == '/version':
			self.version()
		else:
			self.sendCode(404)
			
	def do_POST(self):
		postData = PostData(self)
		
		if self.path == '/wav' or self.path == '/speak.wav':
			self.wav(postData)
		elif self.path == '/say':
			self.say(postData)
		elif self.path == '/stop':
			self.stop()
		elif self.path == '/voices':
			self.voices(postData.get('engine'))
		elif self.path == '/engines/wav':
			self.engines(can_stream_wav=True)
		elif self.path == '/engines/say':
			self.engines(can_stream_wav=False)
		else:
			self.sendCode(404)

	def wav(self,postData):
		TTS.setEngine(postData.get('engine'),True)
		TTS.setVoice(postData.get('voice'))
		TTS.setRate(postData.get('rate'))
		TTS.update()
		text = postData.get('text')
		wav = TTS.getWavStream(text)
		if not wav: return self.sendCode(403)
		util.LOG('WAV: {0}'.format(text.decode('utf-8')))
		self.send_response(200)
		self.send_header('Content-Type','audio/x-wav')
		wav.seek(0,2) #Seek to the end to get the size with tell()
		self.send_header("Content-Length", str(wav.tell()))
		wav.seek(0)
		self.end_headers()
		shutil.copyfileobj(wav,self.wfile)
		wav.close()
		
	def say(self,postData):
		TTS.setEngine(postData.get('engine'))
		TTS.setVoice(postData.get('voice'))
		TTS.setRate(postData.get('rate'))
		TTS.update()
		text = postData.get('text')
		if not text: return self.sendCode(403)
		util.LOG('SAY: {0}'.format(text.decode('utf-8')))
		self.send_response(200)
		self.end_headers()
		TTS.say(text)
		
	def stop(self):
		TTS.stop()
		self.send_response(200)
		self.end_headers()
		
	def voices(self,postData):
		voices = TTS.voices(postData.get('engine'))
		if not voices: return self.sendCode(500)
		data = StringIO.StringIO()
		data.write(voices)
		self.send_response(200)
		self.send_header('Content-Type','text/plain')
		self.send_header("Content-Length", str(data.tell()))
		self.end_headers()
		data.seek(0)
		shutil.copyfileobj(data,self.wfile)
		data.close()
	
	def engines(self,can_stream_wav=False):
		engines = TTS.engines(can_stream_wav)
		if not engines: return self.sendCode(500)
		data = StringIO.StringIO()
		data.write(engines)
		self.send_response(200)
		self.send_header('Content-Type','text/plain')
		self.send_header("Content-Length", str(data.tell()))
		self.end_headers()
		data.seek(0)
		shutil.copyfileobj(data,self.wfile)
		data.close()
		
	def version(self):
		data = StringIO.StringIO()
		data.write('speech.server {0}'.format(__version__))
		self.send_response(200)
		self.send_header('Content-Type','text/plain')
		self.send_header("Content-Length", str(data.tell()))
		self.end_headers()
		data.seek(0)
		shutil.copyfileobj(data,self.wfile)
		data.close()
		
	def sendCode(self,code):
		util.LOG('Sending code: {0}'.format(code))
		self.send_response(code)
		self.end_headers()

def validateAddressOption(option, opt, value):
	if value == '': return value
	try:
		socket.inet_pton(socket.AF_INET, value)
		return value
	except:
		pass
	try:
		socket.inet_pton( socket.AF_INET6, value)
		return value
	except:
		pass
	raise optparse.OptionValueError('Option {0} Invalid: {1}'.format(opt,value))

def validatePlayerOption(option, opt, value):
	if value in ('aplay','paplay','sox','mplayer','mpg123'): return value
	raise optparse.OptionValueError('Invalid player: {0}. Valid players: aplay, paplay, sox and mplayer'.format(value))

class ExtendedOption(optparse.Option):
	TYPES = optparse.Option.TYPES + ('address','player')
	TYPE_CHECKER = copy.copy(optparse.Option.TYPE_CHECKER)
	TYPE_CHECKER["address"] = validateAddressOption
	TYPE_CHECKER["player"] = validatePlayerOption
	
def parseArguments():
	description = 'Ex: python server.py -a 192.168.1.50 -p 12345'
	parser = optparse.OptionParser(option_class=ExtendedOption, description=description , version='speech.server {0}'.format(__version__))
	parser.add_option("-a", "--address", dest="address", type="address", help="address the server binds to [default: ANY]", metavar="ADDR")
	parser.add_option("-p", "--port", dest="port", type="int", help="port the server listens on [default: 8256]", metavar="PORT")
	parser.add_option("-P", "--player", dest="player", type="player", help="player command to use when playing speech [default: ANY]", metavar="PLAYER")
	parser.add_option("-c", "--configure", dest="configure", action="store_true", help="save command line options as defaults")
	parser.add_option("-e", "--edit", dest="edit", action="store_true", help="edit the config file in the default editor")
	return parser.parse_args()
	
def getAddressForConnect(fallback):
	try:
		return [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
	except:
		pass
	return fallback
	
def editConfig():
	import sys
	if sys.platform.startswith('win'):
		cmd = 'cmd /c start %s' % CONFIG_PATH
	elif sys.platform.startswith('darwin'):
		cmd = 'open %s' % CONFIG_PATH
	else:
		cmd = os.environ.get('EDITOR') or os.environ.get('HGEDITOR') or os.environ.get('VISUAL')
		if not cmd:
			if util.commandIsAvailable('nano'):
				cmd = 'nano %s' % CONFIG_PATH
			elif util.commandIsAvailable('pico'):
				cmd = 'pico %s' % CONFIG_PATH
			else:
				cmd = 'vi %s' % CONFIG_PATH
	os.system(cmd)

class ServerOptions:
	def __init__(self,options=None):
		config = ConfigParser.ConfigParser({'address':'','port':8256,'player':None})
		if os.path.exists(CONFIG_PATH):
			config.read(CONFIG_PATH)
		if not config.has_section('settings'): config.add_section('settings')
		
		if options:
			self.address = options.address or config.get('settings','address')
			self.port = options.port or config.getint('settings','port')
			self.player = options.player or config.get('settings','player')
			if options.configure: self.saveConfig(config, CONFIG_PATH)
		else:
			self.address = config.get('settings','address')
			self.port = config.get('settings','port')
			self.player = config.get('settings','player')
			
	def saveConfig(self, config, config_path):
		config._defaults = None
		config.set('settings','address',self.address)
		config.set('settings','port',self.port)
		config.set('settings','player',self.player)
		with open(config_path,'w') as cf: config.write(cf)
		
			
def shutdownServer():
	global ACTIVE
	ACTIVE = False
	import urllib2
	try:
		urllib2.urlopen('http://{0}:{1}'.format(*SERVER.server_address))
		return
	except:
		pass
	try:
		urllib2.urlopen('http://{0}:{1}'.format('127.0.0.1',SERVER.server_address[1]))
		return
	except:
		pass
	
	
def setup():
	backends.removeBackendsByProvider(('ttsd',))

	user_path = appdirs.user_data_dir('speech.server','ruuksoft')
	if not os.path.exists(user_path): os.makedirs(user_path)
	util.LOG('Config file stored at: {0}'.format(CONFIG_PATH))
	if os.path.exists(CONFIG_PATH):
		return
	config = ConfigParser.ConfigParser()
	config.add_section('settings')
	config.set('settings','address','')
	config.set('settings','port','8259')
	config.set('settings','player','')
	with open(CONFIG_PATH,'w') as cf: config.write(cf)

def start(main=False):
	global TTS, SERVER
	
	setup()
	
	TTS = TTSHandler()
	if main:
		cl_options, args = parseArguments()
		if cl_options.edit: return editConfig()
		options = ServerOptions(cl_options)
	else:
		options = ServerOptions()
		
	server_address = (options.address,options.port)
	TTSHandler.preferred_player = options.player
	SERVER = BaseHTTPServer.HTTPServer(server_address, SpeechHTTPRequestHandler)
	util.LOG('STARTED - Address: {0} Port: {1}'.format(*SERVER.server_address))
	
	util.LOG('Connect to {0}:{1}'.format(getAddressForConnect(SERVER.server_address[0]),SERVER.server_address[1]))
	while ACTIVE:
		try:
			SERVER.handle_request()
		except KeyboardInterrupt:
			util.ABORTREQUESTED = True
			TTS.close()
			break
	util.LOG('Shutting down...')
	import threading, time
	while threading.active_count() > 1: time.sleep(0.1)
	util.LOG('ENDED')
	
if __name__ == '__main__':
	start(main=True)