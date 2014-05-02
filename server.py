#! /usr/bin/env python

__version__ = '0.0.1'

import socket, BaseHTTPServer, cgi, urlparse, shutil, StringIO, optparse, copy
from lib import backends
from lib import util

TTS = None

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
	if value in ('aplay','paplay','sox','mplayer'): return value
	raise optparse.OptionValueError('Invalid player: {0}. Valid players: aplay, paplay, sox and mplayer'.format(value))

class ExtendedOption(optparse.Option):
	TYPES = optparse.Option.TYPES + ('address','player')
	TYPE_CHECKER = copy.copy(optparse.Option.TYPE_CHECKER)
	TYPE_CHECKER["address"] = validateAddressOption
	TYPE_CHECKER["player"] = validatePlayerOption
	
def parseArguments():
	description = 'Ex: python server.py -a 192.168.1.50 -p 12345'
	parser = optparse.OptionParser(option_class=ExtendedOption, description=description , version='speech.server {0}'.format(__version__))
	parser.add_option("-a", "--address", dest="address", type="address", help="address the server binds to [default: ANY]", metavar="ADDR", default='')
	parser.add_option("-p", "--port", dest="port", type="int", help="port the server listens on [default: 8256]", metavar="PORT", default=8256)
	parser.add_option("-P", "--player", dest="player", type="player", help="player command to use when playing speech [default: ANY]", metavar="PLAYER")
	return parser.parse_args()
	
def getAddressForConnect(fallback):
	try:
		return [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
	except:
		pass
	return fallback
	
def start():
	options, args = parseArguments()
	server_address = (options.address,options.port)
	TTSHandler.preferred_player = options.player
	httpd = BaseHTTPServer.HTTPServer(server_address, SpeechHTTPRequestHandler)
	util.LOG('STARTED - Address: {0} Port: {1}'.format(*httpd.server_address))
	
	util.LOG('Connect to {0}:{1}'.format(getAddressForConnect(httpd.server_address[0]),httpd.server_address[1]))
	while True:
		try:
			httpd.handle_request()
		except KeyboardInterrupt:
			util.ABORTREQUESTED = True
			TTS.close()
			break
	util.LOG('Shutting down...')
	import threading, time
	while threading.active_count() > 1: time.sleep(0.1)
	util.LOG('ENDED')
	
if __name__ == '__main__':
	TTS = TTSHandler()
	start()