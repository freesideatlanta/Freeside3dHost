#!/usr/bin/env python

import subprocess
import MsgReader
import PrintServer
import Queue

import threading


#StartServer Thread Command

activeServers = dict()

def StartServer(serialnum, device, port):
    if activeServers.has_key(device):
        activeServers[device].stop()
        activeServers[device].join()
        activeServers.pop(device)

    activeServers[device] = PrintServer.PrintServer(serialnum, device, port)
    activeServers[device].start()


#Load Printer Serial -> Port Mapping from File
portMap = dict()

f = open('/etc/3dhost.conf', "r")
lines = f.readlines()
f.close()

for line in lines:
    if not line.strip().startswith('#'):
        tokens = line.split()
        portMap[tokens[0]] = tokens[1]
        print tokens[0] + ':' + tokens[1]


#Setup Process to read dmsg for connected printers

process = subprocess.Popen(['dmesg', '-w', '-t'], bufsize=1, stdout=subprocess.PIPE)

stdout_queue = Queue.Queue()
stdout_reader = MsgReader.MsgReader(process.stdout, stdout_queue)
stdout_reader.daemon = True
stdout_reader.start()

# Read standard out of the child process whilst it is active.
serialList = dict()
devList = dict()


hotplug = False
while True:
    try:
        # Attempt to read available data.
        try:
            line = stdout_queue.get(timeout=0.1)
            #Handle Data Here
            if line.startswith('usb '):
                key = line[4:line.find(':')]
                start_sn = line.find('SerialNumber: ')
                if start_sn > 0:
                    serialList[key] = line[start_sn + 14:-1]

            if line.startswith('cdc_acm '):
                key = line[8:line.find(':')]
                starti = line.find('ttyACM')
                if starti >= 0:
                    endi = line.find(':', starti)
                    devList[serialList[key]] = '/dev/'+ line[starti:endi]
                #Start Devices That Are HotPlugged
                if hotplug:
                    key = serialList[key]
                    if devList.has_key(key) and portMap.has_key(key):
                        StartServer(key, devList[key], portMap[key])



        # If data was not read within time out period. Continue.
        except Queue.Empty:
            if not hotplug:
                # No data currently available. #Should happen only when finished reading old dmesg queue
                keys = portMap.keys()
                for key in keys:
                    if devList.has_key(key) and portMap.has_key(key):
                        StartServer(key, devList[key], portMap[key])
                hotplug = True
            pass

        # Check whether child process is still active.
        if process.poll() != None:
            # Process is no longer active.
            break
        # Dmesg is no longer active. Nothing more to read. Stop Reader thread.
        stdout_reader.stop()

    except KeyboardInterrupt:
        for key in activeServers:
            if activeServers[key] != None:
                activeServers[key].stop()
        stdout_reader.stop()
