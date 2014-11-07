#! /usr/bin/env python

__version__ = '0.0.7'

import os, sys, ConfigParser, socket, cgi, optparse, copy
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'lib'))
from lib import backends
from lib import util
from lib import appdirs
import cherrypy
from cherrypy.lib import file_generator

TTS = None

user_path = appdirs.user_data_dir('speech.server','ruuksoft')
CONFIG_PATH = os.path.join(user_path,'config.txt')

def strIsNumber(numstr):
    try: float(numstr)
    except: return False
    return True

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
        if backend and (not self.backend or backend.provider != self.backend.provider):
            if self.backend: self.backend._close()
            if self.preferred_player:
                util.setSetting('player.' + provider, self.preferred_player)
            self.backend = backend()
            self.backend.setWavStreamMode()

    def setVoice(self,voice):
        if not self.backend or not voice or not '.' in voice: return
        provider, voice = voice.split('.',1)
        if provider != self.backend.provider: return
        util.setSetting('voice.' + provider, voice)
        
    def setRate(self,rate):
        if not rate: return
        if not strIsNumber(rate): return
        rate = self.backend.scaleSpeed(int(rate),20)
        util.setSetting('speed.' + self.backend.provider, rate)
        
    def setPitch(self,pitch):
        if not pitch: return
        if not strIsNumber(pitch): return
        pitch = self.backend.scalePitch(int(pitch),50)
        util.setSetting('pitch.' + self.backend.provider, pitch)

    def setVolume(self,volume):
        if not volume: return
        if not strIsNumber(volume): return
        volume = self.backend.scaleVolume(int(volume),12)
        util.setSetting('volume.' + self.backend.provider, volume)
    
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
        voices = backend.settingList('voice')
        if not voices: return None
        for i in range(len(voices)):
            voices[i] = '{0}.{1}'.format(backend.provider,voices[i][0])
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

@cherrypy.popargs('method')
class SpeechHTTPRequestHandler(object):
    def __init__(self):
        cherrypy.engine.subscribe('stop', self.finish)
        
    def finish(self):
        TTS.close()
    
    @cherrypy.expose
    def shutdown(self):
        shutdownServer()
    
    @cherrypy.expose(['speak.wav'])
    def wav(self,engine=None,voice=None,rate=None,pitch=None,volume=None,text=None):
        TTS.setEngine(engine,True)
        TTS.setVoice(voice)
        TTS.setRate(rate)
        TTS.setPitch(pitch)
        TTS.setVolume(volume)
        TTS.update()
        wav = TTS.getWavStream(text)
        if not wav:
            if not text:
                raise cherrypy.HTTPError(status=400)
            else:
                raise cherrypy.HTTPError(status=500)
        util.LOG('[{0}] {1} - WAV: {2}'.format(cherrypy.request.remote.ip,TTS.backend.provider,text.decode('utf-8')))
        wav.seek(0)
        cherrypy.response.headers['Content-Type'] = "audio/x-wav"
        return file_generator(wav)
                
    @cherrypy.expose
    def say(self,engine=None,voice=None,rate=None,pitch=None,volume=None,text=None):
        TTS.setEngine(engine)
        TTS.setVoice(voice)
        TTS.setRate(rate)
        TTS.setPitch(pitch)
        TTS.setVolume(volume)
        TTS.update()
        if not text: raise cherrypy.HTTPError(status=400)
        util.LOG('[{0}] {1} - SAY: {2}'.format(cherrypy.request.remote.ip,TTS.backend.provider,text.decode('utf-8')))
        TTS.say(text)
        return ''
        
    @cherrypy.expose
    def stop(self):
        TTS.stop()
        return ''
        
    @cherrypy.expose
    def voices(self,engine=None):
        voices = TTS.voices(engine)
        if not voices: raise cherrypy.HTTPError(status=501)
        return voices
        
    @cherrypy.expose
    def engines(self,method=None):
        engines = TTS.engines(method=='wav')
        if not engines: raise cherrypy.HTTPError(status=501)
        return engines
    
    @cherrypy.expose
    def version(self):
        return 'speech.server {0}'.format(__version__)

def validateAddressOption(option, opt, value):
    if value == '0.0.0.0': return value
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
    parser.add_option("-c", "--configure", dest="configure", action="store_true", help="save command line options as defaults and exit")
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
        cmd = 'cmd /c "%s"' % CONFIG_PATH
    elif sys.platform.startswith('darwin'):
        cmd = 'open "%s"' % CONFIG_PATH
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
        config = ConfigParser.ConfigParser({'address':'0.0.0.0','port':8256,'player':None})
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
            self.port = config.getint('settings','port')
            self.player = config.get('settings','player')
            
    def saveConfig(self, config, config_path):
        config._defaults = None
        config.set('settings','address',self.address)
        config.set('settings','port',self.port)
        config.set('settings','player',self.player)
        with open(config_path,'w') as cf: config.write(cf)
        util.LOG('Settings saved!'.format(CONFIG_PATH))
        
            
def shutdownServer():
    TTS.close()
    import signal
    os.kill(os.getpid(),signal.SIGTERM)
    
    
def setup():
    backends.removeBackendsByProvider(('ttsd','speechutil'))

    user_path = appdirs.user_data_dir('speech.server','ruuksoft')
    if not os.path.exists(user_path): os.makedirs(user_path)
    util.LOG('Config file located at: {0}'.format(CONFIG_PATH))
    if os.path.exists(CONFIG_PATH):
        return
    config = ConfigParser.ConfigParser()
    config.add_section('settings')
    config.set('settings','address','0.0.0.0')
    config.set('settings','port','8256')
    config.set('settings','player','')
    with open(CONFIG_PATH,'w') as cf: config.write(cf)
    
def start(main=False):
    global TTS, SERVER
    
    setup()
    
    if main:
        cl_options, args = parseArguments()
        if cl_options.edit: return editConfig()
        options = ServerOptions(cl_options)
        if cl_options.configure: return
    else:
        options = ServerOptions()
    
    util.LOG('STARTED - Address: {0} Port: {1}'.format(options.address,options.port))
    util.LOG('Connect to {0}:{1}'.format(getAddressForConnect(options.address),options.port))
        
    TTS = TTSHandler()
    TTSHandler.preferred_player = options.player
        
    if sys.platform.startswith('win'): cherrypy.config.update({'server.thread_pool':1})
    try:
        cherrypy.config.update({'server.socket_host': options.address or '0.0.0.0', 'server.socket_port': options.port,'checker.on':False,'log.screen':False})
        cherrypy.quickstart(SpeechHTTPRequestHandler())
    finally:
        TTS.close()
    util.LOG('ENDED')
    
if __name__ == '__main__':
    start(True)
