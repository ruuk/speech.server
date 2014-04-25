import BaseHTTPServer, cgi
from lib import backends
from lib import util
import shutil, StringIO
TTS = None

class TTSHandler:
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
			self.backend = backend()
			util.LOG('Backend changed to: {0}'.format(self.backend.provider))

	def setVoice(self,voice):
		if not self.backend or not voice or not '.' in voice: return
		provider, voice = voice.split('.',1)
		if provider != self.backend.provider: return
		util.setSetting('voice.' + provider, voice)
		
	def setRate(self,rate):
		if not rate: return
		if self.backend: self.backend._settings['speed'] = rate
		
	def update(self):
		if self.backend: self.backend.update()
		
	def say(self,text):
		if self.backend: self.backend.say(text,True)
		
	def voices(self):
		voices = self.backend.voices()
		if not voices: return None
		for i in range(len(voices)):
			voices[i] = '{0}.{1}'.format(self.backend.provider,voices[i])
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
		if self.path == '/voices':
			self.voices()
		else:
			self.sendCode(404)
			
	def do_POST(self):
		postData = PostData(self)
		
		if self.path == '/wav' or self.path == '/speak.wav':
			self.wav(postData)
		elif self.path == '/say':
			self.say(postData)
		elif self.path == '/voices':
			self.voices()
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
		wav = TTS.getWavStream(postData.get('text'))
		if not wav: return self.sendCode(403)
		self.send_response(200)
		self.send_header('Content-Type','audio/x-wav')
		wav.seek(0,2)
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
		self.send_response(200)
		self.end_headers()
		TTS.say(text)
		
	def voices(self):
		voices = TTS.voices()
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
		
	def sendCode(self,code):
		self.send_response(code)
		self.end_headers()

def start():
	server_address = ('', 8256)
	httpd = BaseHTTPServer.HTTPServer(server_address, SpeechHTTPRequestHandler)
	while True:
		try:
			httpd.handle_request()
		except KeyboardInterrupt:
			util.ABORTREQUESTED = True
			TTS.close()
			break
	
if __name__ == '__main__':
	TTS = TTSHandler()
	start()