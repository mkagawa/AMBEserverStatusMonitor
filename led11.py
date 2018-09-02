#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#Version 0.11

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
__version__ = "0.11"
__maintainer__ = "Masa Kagawa"
__email__ = "mkagawa@hotmail.com"
__status__ = "Alpha"


from gpiozero import LED
from time import sleep
import warnings
import sys
import re
from threading import Timer, Thread, Event
from signal import signal,SIGINT,SIGHUP,SIGTERM
from subprocess import Popen,PIPE

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
    self.runCmd("echo none >/sys/class/leds/led0/trigger");
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      self.activity = LED(47, active_high=False)
    self.lan = {}
    self.wlan = None
    self.eth = None

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
            self.lan[intf] = {}
            if intf.startswith("wlan"):
              self.wlan = intf
            elif intf.startswith("eth"):
              self.eth = intf
          if len(line) > 7 and line[0] != '#':
            zz = re2.search(line)
            if zz:
              self.lan[intf][zz.group(1)] = zz.group(2).split('/')
        else:
          mm1 = re1.search(line)
          if mm1:
            intf = mm1.group(1)
            self.lan[intf] = {}

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
    self.currentWifi = None
    self.terminate = Event()
    self.changeStat = Event()
    self.setStatus('OK')
    self.checkerTimer = None

  def startTimer(self):
    self.checkerTimer = Timer(60, self.checkerWorker, ())
    self.checkerTimer.start()

  def end(self):
    print "Ctrl-C pressed"
    self.terminate.set()
    if self.checkerTimer:
      self.checkerTimer.cancel()
    self.runCmd("echo mmc0 >/sys/class/leds/led0/trigger");
    print "end requested"

  def checkerWorker(self):
    print "checkerWorker"
    if self.terminate.wait(0):
      return
    self.checkStatus()
    print "CurrentStatus: %s" % self.currentStatus
    if self.terminate.wait(0):
      return
    self.startTimer()

  def checkStatus(self):
    print "start checkStatus"
    #if eth is up, then use treat it as main i/f
    self.curDev = None
    if self.lan[self.wlan]:
      ret = self.ifconfig(self.eth) #see check i/f is up
      if ret:
        self.curDev = self.eth

    #if Wifi is not configured in dhcpcd.txt, then exit as status "N"
    if not self.curDev and not self.lan[self.wlan]:
      return self.setStatus('N') # no device is up

    if not self.curDev:
      #if LAN is not up, check wifi device status
      ret = self.iwconfig(self.wlan) #see if wifi is connected
      if not ret:
        return self.setStatus('W') # wifi is configured but not connected
      print "WIFI = OK (%s:%s)" % (self.wlan,self.currentWifi)
      self.curDev = self.wlan

    if self.terminate.wait(0):
      return

    #check IP conflict
    ret = self.arp(ret[0]) #check dup ip
    if ret:
      return self.setStatus('D') # dup ip
    print "No conflict"

    if self.terminate.wait(0):
      return

    gw = self.lan[self.curDev]['routers'][0]
    dns = self.lan[self.curDev]['domain_name_servers'][0]
    ret = self.route(self.curDev,gw)
    if not ret:
      return self.setStatus('G') # g/w error

    self.gw = ret[1]
    print "Got default route, %s" % self.gw

    if self.terminate.wait(0):
      return

    #print self.lan[self.curDev]
    #ret = self.ping(self.actualNameServer) #ping dns
    #print ret
    ret = self.ping(self.gw) #ping g/w
    if not ret:
      return self.setStatus('P') # "G/W ping failed"
    self.setStatus("OK")
    print "All OK"

  def setStatus(self,stat):
    print "status %s set" % stat
    self.changeStat.set()
    self.currentStatus = stat

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

    for line in out.split("\n"):
      rr1 = re1.search(line.strip())
      if rr1:
        return rr1
      #print ">> " + line

    #print re1.pattern
    #print "failed 2 " + cmd
    return None

  def iwconfig(self, dev):
    cmd = "/sbin/iwconfig %s | grep SSID" % dev
    r = re.compile('SSID:"(.+)"$')
    ret = self.runCmd(cmd,r) 
    self.currentWifi = ret.group(1) if ret else None
    print "WIFI connected: %s" % self.currentWifi
    return self.currentWifi is not None

  def arp(self,dev):
    cmd = "/usr/sbin/arp -n %s" % dev
    r = re.compile('^([\d\.]+)\s+(\w+)\s+([\w:]+)\s+(\w+)\s+(\w+)$')
    ret = self.runCmd(cmd,r)
    return ret.groups() if ret else None

  def route(self,dev,gw):
    cmd = "/sbin/route -n | grep %s | grep '%s '" % (dev,gw)
    print cmd
    r = re.compile('^([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+(\w+)\s+\d+\s+\d+\s+\d+\s+\w+$')
    ret = self.runCmd(cmd,r)
    return ret.groups() if ret else None

  def ifconfig(self,dev):
    cmd = "/sbin/ifconfig %s" % dev
    r = re.compile('^inet\s+([\d\.]+)\s+netmask\s+([\d\.]+)\s+broadcast\s+([\d\.]+)$')
    ret = self.runCmd(cmd,r) 
    return ret.groups() if ret else None

  def ping(self, ipaddr=None):
    cmd = "/bin/ping -t1 -c3 %s" % ipaddr
    r = re.compile('^rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms$')
    ret = self.runCmd(cmd,r) 
    return ret.groups() if ret else None

  def run(self):
    print "run thread"
    self.blink()

  def blink(self,pchr=None):
    if pchr:
      self.currentStatus = pchr
    while not self.terminate.wait(0):
      self.changeStat.clear()
      if self.currentStatus == 'OK':
        while not self.terminate.wait(7.8):
          self.activity.on()
          sleep(.2)
          self.activity.off()
          if self.changeStat.wait(0):
            break
      else:
        print "show status %s" % self.currentStatus
        while not self.terminate.wait(3):
          for c in self.ch[self.currentStatus]:
            self.activity.on()
            sleep(.2 if c=='.' else .6)
            self.activity.off()
            sleep(.2)
          if self.changeStat.wait(0):
            break

if __name__ == "__main__":
  l = Blinker()
  def signal_handler(signum,frame):
    print "Ctrl-C: %d" % signum
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
    l.start()
    l.startTimer()
    print "wait for signal - must be a loop"
    while not l.terminate.wait(2):
      pass
    l.join()
    print "end of process"

