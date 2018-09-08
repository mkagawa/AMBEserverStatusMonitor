#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# The MIT License (MIT)
#
# Copyright (c) 2018 Masa Kagawa (NW6UP) mkagawa@hotmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__author__ = "Masa Kagawa (NW6UP)"
__copyright__ = "Copyright 2018, Masa Kagawa"
__license__ = "MIT"
__version__ = "0.9"
__maintainer__ = "Masa Kagawa"
__email__ = "mkagawa@hotmail.com"
__status__ = "Beta"

from argparse import Namespace
from pyroute2 import IPRoute
from gpiozero import LED
from time import sleep
from select import select,error as selerr
from threading import Timer, Thread, Event
from signal import signal,SIGINT,SIGHUP,SIGTERM
from subprocess import Popen,PIPE
from time import asctime
import warnings
import sys
import re
import traceback

LEDDEV="/sys/class/leds/led0/trigger"

''' class to receive dict to convert class attributes '''
class Attrs(Namespace):
   def __init__(self,attrs):
     if attrs:
       for x, y in attrs:
         if not "CACHEINFO" in x:
           self.__dict__[x] = y
   def __getattr__(self,name):
     try:
       return getattr(self,name)
     except: #no key found is not an error
       return None

class Blinker(Thread):
  def __init__(self):
    Thread.__init__(self)
    self.ch = {
      'A':'._',
      'B':'_...',
      'C':'_._.',
      'D':'_..',
      'E':'.',
      'F':'.._.',
      'G':'__.',
      'H':'....',
      'I':'..',
      'J':'.___',
      'K':'_._',
      'L':'._..',
      'M':'__',
      'N':'_.',
      'O':'___',
      'P':'.__.',
      'Q':'__._',
      'R':'._.',
      'S':'...',
      'T':'_',
      'U':'.._',
      'V':'..._',
      'W':'.__',
      'X':'_.._',
      'Y':'_.__',
      'Z':'__..',
      '0':'_____',
      '1':'.____',
      '2':'..___',
      '3':'...__',
      '4':'...._',
      '5':'.....',
      '6':'_....',
      '7':'__...',
      '8':'___..',
      '9':'____.',
    }
    with open(LEDDEV,"w") as f:
      f.write("none")
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      self.activity = LED(47, active_high=False)
      self.activity.off()
    self.currentStatus = None
    self.lanConfig = {}
    self.ipr = IPRoute()
    self.ipAddr = None
    self.eth = None
    self.wlan = None
    self.curDev = None

    #parse ip address from dhcpcd.conf
    #these are expected static ip addresses
    #self.dev = 'wlan0'
    #self.devl = 'eth0'
    with open("/etc/wpa_supplicant/wpa_supplicant.conf", "r") as f:
      re1 = re.compile('ssid\s*=\s*"?(\w*?)"?$')
      re2 = re.compile('key_mgmt\s*=\s*"?([\w_\-]*?)"?$')
      txt = f.read()
      for line in txt.split('\n'):
        line = line.strip()
        if len(line) > 0 and line[0] != '#':
          rr1 = re1.search(line)
          rr2 = re2.search(line)
          if rr1:
            self.expectedWifi = rr1.group(1)
            print "WIFI config name: %s" % self.expectedWifi
          elif rr2:
            self.expectedWifiType = rr2.group(1)
            print "WIFI config type: %s" % self.expectedWifiType
          else:
            #print line
            pass

    with open("/etc/dhcpcd.conf", "r") as f:
      txt = f.read()
      re1 = re.compile('^interface\s+(.+)$')
      re2 = re.compile('^static\s+(\w+)\s*=\s*(.+)$')
      intf = ''
      for line in txt.split('\n'):
        if intf:
          #other interface
          mm1 = re1.search(line)
          if mm1:
            intf = mm1.group(1)
            self.lanConfig[intf] = {}
            if intf.startswith("wlan"):
              self.wlan = intf
            elif intf.startswith("eth"):
              self.eth = intf
          if len(line) > 7 and line[0] != '#':
            zz = re2.search(line)
            if zz:
              self.lanConfig[intf][zz.group(1)] = zz.group(2).split('/')
        else:
          mm1 = re1.search(line)
          if mm1:
            intf = mm1.group(1)
            if intf.startswith("wlan"):
              self.wlan = intf
            elif intf.startswith("eth"):
              self.eth = intf
            self.lanConfig[intf] = {}
    #actual name server set to resolv.conf
    self.actualNameServer = None
    with open("/etc/resolv.conf", "r") as f:
      txt = f.read()
      re1 = re.compile('^nameserver\s+([\.\d]+)$')
      intf = ''
      for line in txt.split('\n'):
        r = re1.search(line)
        if r:
          self.actualNameserver = r.group(1)
    self.curDev = None
    self.terminate = Event()
    self.setCurrentStatus('OK')

  def getCurrentStatusOK(self):
    return self.currentStatus == 'OK'

  def setCurrentStatus(self,st):
    if self.currentStatus != st:
      if self.currentStatus != None:
        print "%s - status %s set" % (asctime(), st)
      self.currentStatus = st
    return (st == 'OK')

  def end(self):
    if self.terminate.wait(0):
      return
    print "Ctrl-C pressed - will exit in few seconds"
    self.activity.off()
    with open(LEDDEV,"w") as f:
      f.write("mmc0")
    self.terminate.set()
    self.ipr.close()
    self.ipr = None

  def checkStatus(self):
    #if eth is up, then use treat it as main i/f
    self.curDev = None
    self.ipAddr = None

    self.setCurrentStatus('OK')
    if self.eth and self.lanConfig[self.eth]:
      ret = self.ifconfig(self.eth) #see check eth i/f is up
      if ret:
        if self.lanConfig[self.eth]['ip_address'][0] == ret[0]:
          #got right ip address
          print "Got LAN ip address: %s" % ret[0]
          self.ipAddr = ret[0]
          self.curDev = self.eth
          self.setCurrentStatus('OK')
        else:
          print "wrong ip address for dev %s: %s" % (self.eth,ret[0])
          self.setCurrentStatus('X')

    #if eth is not up and wlan is configured
    if self.wlan and self.lanConfig[self.wlan] and not self.ipAddr:
      #if LAN is not up, check wifi device status
      ret = self.iwconfig(self.wlan) #see if wifi is connected
      if not ret:
        return

      self.curDev = self.wlan
      #print "WIFI = OK (%s:%s)" % (self.wlan,self.currentWifi)
      ret = self.ifconfig(self.wlan) #see check wlan i/f is up
      if ret:
        self.curDev = self.wlan
        if self.lanConfig[self.wlan]['ip_address'][0] == ret[0]:
          print "Got WIFI ip address: %s" % ret[0]
          self.ipAddr = ret[0]
          self.setCurrentStatus('OK')
        else:
          print "wrong ip address for dev %s: %s" % (self.wlan,ret[0])
          self.setCurrentStatus('X')

    if not self.ipAddr:
      print "both eth and wlan are down, status=%s" % self.currentStatus
      return

    #check IP conflict
    if not self.arp():
      return

    if self.terminate.wait(0):
      return

    self.gw = self.lanConfig[self.curDev]['routers'][0]
    self.dns = self.lanConfig[self.curDev]['domain_name_servers'][0]
    self.setCurrentStatus('OK')
    ret = self.route(self.curDev)
    if not ret:
      return
    print "Got default route, %s" % self.gw

    if self.terminate.wait(0):
      return

    #print self.lanConfig[self.curDev]
    #ret = self.ping(self.actualNameServer) #ping dns
    #print ret
    ret = self.ping(self.gw) #ping g/w
    if not ret:
      print "G/W ping failed"
      self.setCurrentStatus('P')
      return
    self.setCurrentStatus('OK')
    #print "All OK"

  def runCmd(self, cmd, re1 = None):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    ok = False
    for i in range(0,5):
      if p.poll() is not None:
        ok = True
        out,err = p.communicate()
        break
      sleep(1)
    if not ok:
      p.kill()
      print "failed 1 %s" % cmd
      return None

    if not re1:
      return out

    if type(re1).__name__ == 'SRE_Pattern':
      re1 = [re1]

    for rrr in re1:
      for line in out.split("\n"):
        rr1 = rrr.search(line.strip())
        #print line
        if rr1:
          return rr1
        #print ">> " + line

    #print re1.pattern
    #print "failed 2 " + cmd
    return None

  def iwconfig(self, dev):
    cmd = "/sbin/iwconfig %s | grep SSID" % dev
    r = re.compile('SSID:"(.+?)"')
    ret = self.runCmd(cmd,r) 
    self.currentWifi = ret.group(1) if ret else None
    print "WIFI connected: %s" % self.currentWifi
    if self.currentWifi is not None:
      return True
    return self.setCurrentStatus('W') # wifi is configured but not connected

  def arp(self):
    #check IP conflict
    for n in self.ipr.get_neighbours():
      attrs = Attrs(n['attrs'] if 'attrs' in n else None)
      if attrs and attrs.NDA_LLADDR == '00:00:00:00:00:00':
        continue
      if attrs.NDA_DST == self.ipAddr:
        print "detect conflict with with mac addr %s" % (NDA_LLADDR)
        return self.setCurrentStatus('D')
    print "ip address  %s has no conflict" % self.ipAddr
    return True

  def route(self,dev):
    gwmatch = False
    for n in self.ipr.get_routes():
      if 'family' in n and n['family'] != 2:
        #ipv4 only
        continue
      attrs = Attrs(n['attrs'] if 'attrs' in n else None)
      #print attrs
      if attrs and attrs.RTA_GATEWAY == self.gw:
        gwmatch = True

    if not gwmatch:
      print "default g/w doesn't match with config: %s" % attrs.RTA_GATEWAY
      self.setCurrentStatus('G')
    return self.getCurrentStatusOK()

  def ifconfig(self,dev):
    for dd in self.ipr.get_links(): #filter may not work always
      attrs = Attrs(dd['attrs'] if 'attrs' in dd else None)
      if attrs and attrs.IFLA_IFNAME == dev:
        #print "dev:%s,index: %s" % (dev,dd['index'])
        aa = self.ipr.get_addr(index=dd['index'])
        if aa:
          attrs = Attrs(aa[0]['attrs'] if 'attrs' in aa[0] else None)
          return (attrs.IFA_ADDRESS,attrs.IFA_BROADCAST) if attrs else None
    return None

  def ping(self, ipaddr=None):
    cmd = "/bin/ping -t1 -c3 %s" % ipaddr
    r = re.compile('^rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms$')
    ret = self.runCmd(cmd,r) 
    return ret.groups() if ret else None

  def run(self):
    self.blink()
    #print "blinker thread ended"

  def changeDetector(self):
    if not self.ipr:
      return
    try:
      self.ipr.bind()
    except:
      print "Exception: %s" % traceback.format_exc()
      return

    self.checkerTimer = None
    def checker():
      print "%s - checker invoked" % asctime()
      self.checkerTimer = None
      self.checkStatus() 
    def checkerInvoker():
      if not self.checkerTimer:
        print "%s - network state changed" % asctime()
        self.checkerTimer = Timer(8, checker)
        self.checkerTimer.start()

    while not self.terminate.wait(.1):
      if not self.ipr:
        return
      try:
        ret = select([self.ipr],[],[],5)
        if len(ret[0]) == 0:
          continue
        for msg in self.ipr.get():
          if 'family' in msg and msg['family'] != 2:
            #ipv4 only
            continue
          attrs = Attrs(msg['attrs'] if 'attrs' in msg else None)
          event = msg['event']
          #print 'change detected: %s' % event
          msg.pop('event', None)
          msg.pop('attrs', None)
          msg.pop('header', None)

          if event in ("RTM_NEWADDR", "RTM_DELADDR","RTM_GETADDR"):
            #print "%s - %s" % (asctime(),event)
            checkerInvoker()
          elif event in ("RTM_NEWROUTE","RTM_DELROUTE","RTM_GETROUTE"):
            #print "%s - %s" % (asctime(),event)
            checkerInvoker()
          elif event in ("RTM_NEWNEIGH"):
            if attrs.NDA_LLADDR == '00:00:00:00:00:00':
              continue
            if attrs.NDA_DST == self.ipAddr:
              print "detect conflict with with mac addr %s" % (NDA_LLADDR)
              self.setCurrentStatus('D')
      except selerr,e:
        if e[0] != 4:
          print "Exception: %s" % e
        break
      except:
        print "Exception: %s" % (traceback.format_exc())

  def blink(self,pchr=None):
    while not self.terminate.wait(3):
      chr = self.currentStatus if not pchr else pchr
      if chr == 'OK':
        if self.terminate.wait(2.8):
          return True
        self.activity.on()
        sleep(.2)
        self.activity.off()
      else:
        for c in self.ch[chr]:
          self.activity.on()
          sleep(.2 if c=='.' else .6)
          self.activity.off()
          sleep(.2)
    return True

if __name__ == "__main__":
  l = Blinker()
  def signal_handler(signum,frame):
    print signum
    l.end()
  signal(SIGINT, signal_handler)
  if len(sys.argv) == 2:
    m = re.search('^([A-Z\d])$', sys.argv[1])
    if m:
      l.blink(m.group(1))
    else:
      print "parameter error, %s" % sys.argv[1]
  else:
    l.checkStatus()
    print "%s - monitor started" % asctime()
    l.start()
    l.changeDetector()

    while not l.terminate.wait(5):
      pass
    l.join()
    print "%s - process end" % asctime()

