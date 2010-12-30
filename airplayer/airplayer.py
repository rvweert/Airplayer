#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Pascal Widdershoven on 2010-12-19.
Copyright (c) 2010 P. Widdershoven. All rights reserved.
"""
from __future__ import with_statement

import sys
import thread
from socket import gethostname
import signal
from optparse import OptionParser
import logging
import os

import bonjour
from web import Webserver
import settings
import utils

class Application(object):
    
    def __init__(self, port):
        self.port = port
        self.media_backend = None
        self.web = None
        
    def _setup_path(self):
        sys.path.append(os.path.join(os.path.dirname(__file__), 'libs'))      
        
    def _configure_logging(self):
        """
        Configure logging.
        When not running in the background we just log to stdout,
        otherwise we'll log to a logfile in the parent diretory.
        """
        self.log = logging.getLogger('airplayer')

        fmt = r"%(asctime)s [%(levelname)s] %(message)s"
        datefmt = r"%Y-%m-%d %H:%M:%S"

        if self.opts.daemon:
            logdir = os.path.expanduser('~/.airplayer/')
            logfile = os.path.join(logdir, 'airplayer.log')
            
            if not os.path.exists(logdir):
                os.mkdir(logdir, 0755)
            
            handler = logging.FileHandler(logfile)
        else:
            handler = logging.StreamHandler()

        if getattr(settings, 'DEBUG', None) and settings.DEBUG:
            loglevel = logging.DEBUG
        else:
            loglevel = logging.WARNING
            
        self.log.setLevel(loglevel)
        handler.setFormatter(logging.Formatter(fmt, datefmt))
        self.log.addHandler(handler)
        
    def _parse_opts(self):
        parser = OptionParser(usage='usage: %prog [options] filename')
        parser.add_option('-d', '--daemon', 
            action='store_true', 
            dest='daemon', 
            default=False,
            help='run Airplayer as a daemon in the background'
        )
        
        (self.opts, self.args) = parser.parse_args()
        
    def _register_bonjour(self):
        """
        Register our service with bonjour.
        """
        if getattr(settings, 'AIRPLAY_HOSTNAME', None):
            hostname = settings.AIRPLAY_HOSTNAME
        else:    
            hostname = gethostname()
            """
            gethostname() often returns <hostname>.local, remove that.
            """
            hostname = utils.clean_hostname(hostname)
            
            if not hostname:
                hostname = 'Airplayer'
        
        thread.start_new_thread(bonjour.register_service, (hostname, "_airplay._tcp", self.port,))
        
    def _connect_to_media_backend(self):        
        backend_module = '%s_media_backend' % settings.MEDIA_BACKEND
        backend_class = '%sMediaBackend' % settings.MEDIA_BACKEND
                
        try:        
            mod = __import__('mediabackends.%s' % backend_module, fromlist=[backend_module])
        except ImportError, e:
            print e
            raise Exception('Invalid media backend specified: %s' % settings.MEDIA_BACKEND)
                
        backend_cls = getattr(mod, backend_class)
        
        username = getattr(settings, 'MEDIA_BACKEND_USERNAME', None)
        password = getattr(settings, 'MEDIA_BACKEND_PASSWORD', None)

        self.media_backend = backend_cls(settings.MEDIA_BACKEND_HOST, settings.MEDIA_BACKEND_PORT, username, password)
        
    def _start_web(self):
        self.web = Webserver(self.port)
        self.web.media_backend = self.media_backend
        self.web.start()
        
    def _run(self):
        self._setup_path()
        self._configure_logging()
        self.log.info('Starting Airplayer')
        
        self._register_bonjour()
        self._connect_to_media_backend()
        
        self.media_backend.notify_started()
        self._start_web()
        
    def run(self):
        self._parse_opts()
                
        if self.opts.daemon:
            utils.daemonize()

        self._run()    
    
    def receive_signal(self, signum, stack):
        self.web.stop()
        self.media_backend.stop_playing()

def main():
    app = Application(6002)
    signal.signal(signal.SIGTERM, app.receive_signal)
    
    try:
        app.run()
    except Exception, e:
        print 'Error: %s' % e
        sys.exit(1)

if __name__ == '__main__':
    main()