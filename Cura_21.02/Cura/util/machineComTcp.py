"""
MachineCom handles communication with GCode based printers trough (USB) serial ports.
For actual printing of objects this module is used from Cura.serialCommunication and ran in a separate process.
"""
__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import os
import glob
import sys
import time
import math
import re
import traceback
import threading
import platform
import socket
import Queue as queue

from Cura.avr_isp import stk500v2
from Cura.avr_isp import ispBase

from Cura.util import profile
from Cura.util import version

try:
	import _winreg
except:
	pass

CMDBUFFER_SIZE = 3


class VirtualPrinter():
	"""
	A virtual printer class used for debugging. Acts as a tcp.TCP class, but without connecting to any port.
	Only available when running the development version of Cura.
	"""
	def __init__(self):
		self.readList = ['start\n', 'Marlin: Virtual Marlin!\n', '\x80\n']
		self.temp = 0.0
		self.targetTemp = 0.0
		self.lastTempAt = time.time()
		self.bedTemp = 1.0
		self.bedTargetTemp = 1.0
	
	def write(self, data):
		if self.readList is None:
			return
		#print "Send: %s" % (data.rstrip())
		if 'M104' in data or 'M109' in data:
			try:
				self.targetTemp = float(re.search('S([0-9]+)', data).group(1))
			except:
				pass
		if 'M140' in data or 'M190' in data:
			try:
				self.bedTargetTemp = float(re.search('S([0-9]+)', data).group(1))
			except:
				pass
		if 'M105' in data:
			self.readList.append("ok T:%.2f /%.2f B:%.2f /%.2f @:64\n" % (self.temp, self.targetTemp, self.bedTemp, self.bedTargetTemp))
		elif len(data.strip()) > 0:
			self.readList.append("ok\n")

	def readline(self):
		if self.readList is None:
			return ''
		n = 0
		timeDiff = self.lastTempAt - time.time()
		self.lastTempAt = time.time()
		if abs(self.temp - self.targetTemp) > 1:
			self.temp += math.copysign(timeDiff * 10, self.targetTemp - self.temp)
		if abs(self.bedTemp - self.bedTargetTemp) > 1:
			self.bedTemp += math.copysign(timeDiff * 10, self.bedTargetTemp - self.bedTemp)
		while len(self.readList) < 1:
			time.sleep(0.1)
			n += 1
			if n == 20:
				return ''
			if self.readList is None:
				return ''
		time.sleep(0.001)
		#print "Recv: %s" % (self.readList[0].rstrip())
		return self.readList.pop(0)
	
	def close(self):
		self.readList = None

class MachineComTcpPrintCallback(object):
	"""
	Base class for callbacks from the MachineComTcp class.
	This class has all empty implementations and is attached to the MachineCom if no other callback object is attached.
	"""
	def mcLog(self, message):
		pass
	
	def mcTempUpdate(self, temp, bedTemp, targetTemp, bedTargetTemp):
		pass
	
	def mcStateChange(self, state):
		pass
	
	def mcMessage(self, message):
		pass
	
	def mcProgress(self, lineNr):
		pass
	
	def mcZChange(self, newZ):
		pass

class MachineComTcp(object):
	"""
	Class for (TCP) communication with 3D printers.
	This class keeps track of if the connection is still live
	"""
	STATE_NONE = 0
	STATE_OPEN_TCP = 1
	STATE_CONNECTING = 4
	STATE_OPERATIONAL = 5
	STATE_PRINTING = 6
	STATE_PAUSED = 7
	STATE_CLOSED = 8
	STATE_ERROR = 9
	STATE_CLOSED_WITH_ERROR = 10
	
	def __init__(self, ip = None, callbackObject = None):
		if ip is None:
			ip = profile.getMachineSetting('tcp_ip_address')
		if callbackObject is None:
			callbackObject = MachineComTcpPrintCallback()
		
		tklist = ip.split(":");
		if(tklist.Count() > 1)
		
		#Split IP into IP/Port if necessarry
		self._ip = tklist[0];
		self._port = int(tklist[1]);
		self._callback = callbackObject
		self._state = self.STATE_NONE
		self._socket = None
		self._extruderCount = int(profile.getMachineSetting('extruder_amount'))
		self._temperatureRequestExtruder = 0
		self._temp = [0] * self._extruderCount
		self._targetTemp = [0] * self._extruderCount
		self._bedTemp = 0
		self._bedTargetTemp = 0
		self._gcodeList = None
		self._gcodePos = 0
		self._commandQueue = queue.Queue()
		self._logQueue = queue.Queue(256)
		self._feedRateModifier = {}
		self._currentZ = -1
		self._heatupWaitStartTime = 0
		self._heatupWaitTimeLost = 0.0
		self._heatupWaiting = False
		self._printStartTime100 = None
		self._currentCommands = []
		
		self._linebuf = StringIO.StringIO(2048)  

		self._thread_lock = threading.Lock()
		self.thread = threading.Thread(target=self._monitor)
		self.thread.daemon = True
		self.thread.start()
	
	def _changeState(self, newState):
		if self._state == newState:
			return
		oldState = self.getStateString()
		self._state = newState
		self._log('Changing monitoring state from \'%s\' to \'%s\'' % (oldState, self.getStateString()))
		self._callback.mcStateChange(newState)
	
	def getState(self):
		return self._state
	
	def getStateString(self):
		if self._state == self.STATE_NONE:
			return "Offline"
		if self._state == self.STATE_OPEN_TCP:
			return "Opening TCP connection"
		if self._state == self.STATE_CONNECTING:
			return "Connecting"
		if self._state == self.STATE_OPERATIONAL:
			return "Operational"
		if self._state == self.STATE_PRINTING:
			return "Printing"
		if self._state == self.STATE_PAUSED:
			return "Paused"
		if self._state == self.STATE_CLOSED:
			return "Closed"
		if self._state == self.STATE_ERROR:
			return "Error: %s" % (self.getShortErrorString())
		if self._state == self.STATE_CLOSED_WITH_ERROR:
			return "Error: %s" % (self.getShortErrorString())
		return "?%d?" % (self._state)
	
	def getShortErrorString(self):
		if len(self._errorValue) < 35:
			return self._errorValue
		return self._errorValue[:35] + "..."

	def getErrorString(self):
		return self._errorValue

	def isClosed(self):
		return self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

	def isClosedOrError(self):
		return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR or self._state == self.STATE_CLOSED

	def isError(self):
		return self._state == self.STATE_ERROR or self._state == self.STATE_CLOSED_WITH_ERROR
	
	def isOperational(self):
		return self._state == self.STATE_OPERATIONAL or self._state == self.STATE_PRINTING or self._state == self.STATE_PAUSED
	
	def isPrinting(self):
		return self._state == self.STATE_PRINTING
	
	def isPaused(self):
		return self._state == self.STATE_PAUSED

	def getPrintPos(self):
		return self._gcodePos
	
	def getPrintTime(self):
		return time.time() - self._printStartTime

	def getPrintTimeRemainingEstimate(self):
		if self._printStartTime100 is None or self.getPrintPos() < 200:
			return None
		printTime = (time.time() - self._printStartTime100) / 60
		printTimeTotal = printTime * (len(self._gcodeList) - 100) / (self.getPrintPos() - 100)
		printTimeLeft = printTimeTotal - printTime
		return printTimeLeft
	
	def getTemp(self):
		return self._temp
	
	def getBedTemp(self):
		return self._bedTemp
	
	def getLog(self):
		ret = []
		while not self._logQueue.empty():
			ret.append(self._logQueue.get())
		for line in ret:
			self._logQueue.put(line, False)
		return ret

	def receivedOK(self):
		if len(self._currentCommands) > 0:
			popped = False
			# Marlin will answer 'ok' immediatly to G[0-3] commands
			for i in xrange(0, len(self._currentCommands)):
				if "G0 " in self._currentCommands[i] or \
				   "G1 " in self._currentCommands[i] or \
				   "G2 " in self._currentCommands[i] or \
				   "G3 " in self._currentCommands[i]:
					self._currentCommands.pop(i)
					popped = True
					break
			if not popped:
				self._currentCommands.pop(0)
		if self._heatupWaiting:
			if len(self._currentCommands) == 0:
				self._heatupWaiting = False

	def _monitor(self):
		#Open the TCP connection
		
		if self._port == 'VIRTUAL':
			self._changeState(self.STATE_OPEN_TCP)
			self._tcp = VirtualPrinter()
		else:
			self._changeState(self.STATE_OPEN_TCP)
			self._log("Connecting to: %s on port %d)" % (self._ip) % (self._port))
			
		
		#Connect Here
		
		self._changeState(self.STATE_CONNECTING)
		
		s.settimeout(3.0);
		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._socket.connect((self._ip, self._port))
		

		while True:
			#Read input
			line = self._readline()
			if line is None: #connection closed
				break

			#No matter the state, if we see an fatal error, goto the error state and store the error for reference.
			# Only goto error on known fatal errors.
			if line.startswith('Error:'):
				#Oh YEAH, consistency.
				# Marlin reports an MIN/MAX temp error as "Error:x\n: Extruder switched off. MAXTEMP triggered !\n"
				#	But a bed temp error is reported as "Error: Temperature heated bed switched off. MAXTEMP triggered !!"
				#	So we can have an extra newline in the most common case. Awesome work people.
				if re.match('Error:[0-9]\n', line):
					line = line.rstrip() + self._readline()
				#Skip the communication errors, as those get corrected.
				if 'Extruder switched off' in line or 'Temperature heated bed switched off' in line or 'Something is wrong, please turn off the printer.' in line or 'PROBE FAIL' in line:
					if not self.isError():
						self._errorValue = line[6:]
						self._changeState(self.STATE_ERROR)
						
			if ' T:' in line or line.startswith('T:'):
				tempRequestTimeout = time.time() + 5
				try:
					self._temp[self._temperatureRequestExtruder] = float(re.search("T: *([0-9\.]*)", line).group(1))
				except:
					pass
				if 'B:' in line:
					try:
						self._bedTemp = float(re.search("B: *([0-9\.]*)", line).group(1))
					except:
						pass
				self._callback.mcTempUpdate(self._temp, self._bedTemp, self._targetTemp, self._bedTargetTemp)
				#If we are waiting for an M109 or M190 then measure the time we lost during heatup, so we can remove that time from our printing time estimate.
				if not 'ok' in line and self._heatupWaitStartTime != 0:
					t = time.time()
					self._heatupWaitTimeLost = t - self._heatupWaitStartTime
					self._heatupWaitStartTime = t
			elif line.strip() != '' and line.strip() != 'ok' and not line.startswith('Resend:') and \
				 not line.startswith('Error:checksum mismatch') and not line.startswith('Error:Line Number is not Last Line Number+1') and \
				 not line.startswith('Error:No Checksum with line number') and not line.startswith('Error:No Line Number with checksum') and \
				 line != 'echo:Unknown command:""\n' and self.isOperational():
				self._callback.mcMessage(line)

				
			if self._state == self.STATE_CONNECTING:
				if line == '' or 'wait' in line or 'start' in line:        # 'wait' needed for Repetier (kind of watchdog)
					self._sendCommand("M105")
				elif 'ok' in line:
					self._changeState(self.STATE_OPERATIONAL)
				if time.time() > timeout:
					self.close()
					
			elif self._state == self.STATE_OPERATIONAL:
				# Request the temperature on comm timeout (every 2 seconds) when we are not printing.
				# unless we had a temperature feedback (from M109 or M190 for example)
				if line == '' and time.time() > tempRequestTimeout:
					if self._heatupWaiting and len(self._currentCommands) == 1:
						self._log("Canceling heatup due to missing T: line in the past 5 seconds. cmdbuffer desync?")
						self._heatupWaiting = False
						# Force a timeout now if necessary
						timeout = time.time() - 1
					if self._extruderCount > 0:
						self._temperatureRequestExtruder = (self._temperatureRequestExtruder + 1) % self._extruderCount
						self.sendCommand("M105 T%d" % (self._temperatureRequestExtruder))
					else:
						self.sendCommand("M105")
					# set timeout to less than 2 seconds to make sure it always triggers when comm times out
					tempRequestTimeout = time.time() + 1.5
				if line == '' and time.time() > timeout:
					line = 'ok'
				if 'ok' in line:
					self.receivedOK()
					timeout = time.time() + 30
					if not self._heatupWaiting and not self._commandQueue.empty():
						self._sendCommand(self._commandQueue.get())
					if len(self._currentCommands) > 0 and \
					   ("G28" in self._currentCommands[0] or "G29" in self._currentCommands[0] or \
						"M109" in self._currentCommands[0] or "M190" in self._currentCommands[0]):
						# Long command detected. Timeout is now set to 10 minutes to avoid forcing 'ok'
						# every 30 seconds while it's not needed
						timeout = time.time() + 600
				elif 'start' in line:
					self._currentCommands = []
					timeout = time.time() + 30
			elif self._state == self.STATE_PRINTING:
				#Even when printing request the temperature every 5 seconds.
				if time.time() > tempRequestTimeout:
					if self._heatupWaiting and len(self._currentCommands) == 1:
						self._log("Canceling heatup due to missing T: line in the past 5 seconds. cmdbuffer desync?")
						self._heatupWaiting = False
						# Force a timeout now if necessary
						timeout = time.time() - 1
					if self._extruderCount > 0:
						self._temperatureRequestExtruder = (self._temperatureRequestExtruder + 1) % self._extruderCount
						self.sendCommand("M105 T%d" % (self._temperatureRequestExtruder))
					else:
						self.sendCommand("M105")
					tempRequestTimeout = time.time() + 5
				if line == '' and time.time() > timeout:
					self._log("Communication timeout during printing, forcing a line")
					line = 'ok'
				if 'ok' in line:
					self.receivedOK()
					timeout = time.time() + 30
					# If we are heating up with M109 or M190, then we can't send any new
					# commands until the command buffer queue in firmware is empty (M109/M190 done)
					# otherwise, we will fill up the buffer queue (2 more commands will be accepted after M109/M190)
					# and anything else we send will just end up in the serial ringbuffer and will not be read until
					# the M109/M190 is done.
					# So if we want to cancel the heatup, we need to send M108 which needs to be able to be read from
					# the ringbuffer, which means the command queue needs to be empty.
					# So we stop sending any commands after M109/M190 unless it's M108 (or until heating done) if we want
					# M108 to get handled.
					# the small delay that is caused by the firmware buffer getting empty is not important because
					# this happens during a heat&wait, not during a move command.
					# If M108 is received, it gets sent directly from the receiving thread, not from here
					# because the _commandQueue is not iterable
					if not self._heatupWaiting:
						# We iterate in case we just came out of a heat&wait
						for i in xrange(len(self._currentCommands), CMDBUFFER_SIZE):
							# One of the next 4 could enable the heatupWaiting mode
							if not self._heatupWaiting:
								if not self._commandQueue.empty():
									self._sendCommand(self._commandQueue.get())
								else:
									self._sendNext()
					if len(self._currentCommands) > 0 and \
					   ("G28" in self._currentCommands[0] or "G29" in self._currentCommands[0] or \
						"M109" in self._currentCommands[0] or "M190" in self._currentCommands[0]):
						# Long command detected. Timeout is now set to 10 minutes to avoid forcing 'ok'
						# every 30 seconds while it's not needed
						timeout = time.time() + 600

				elif 'start' in line:
					self._currentCommands = []
					timeout = time.time() + 30
				elif "resend" in line.lower() or "rs" in line:
					newPos = self._gcodePos
					try:
						newPos = int(line.replace("N:"," ").replace("N"," ").replace(":"," ").split()[-1])
					except:
						if "rs" in line:
							newPos = int(line.split()[1])
					# If we need to resend more than 10 lines, we can assume that the machine
					# was shut down and turned back on or something else that's weird just happened.
					# In that case, it can be dangerous to restart the print, so we'd better kill it
					if newPos == 1 or self._gcodePos > newPos + 100:
						self._callback.mcMessage("Print canceled due to loss of communication to printer (USB unplugged or power lost)")
						self.cancelPrint()
					else:
						self._gcodePos = newPos
			elif self._state == self.STATE_PAUSED:
				#Even when printing request the temperature every 5 seconds.
				if time.time() > tempRequestTimeout:
					if self._heatupWaiting and len(self._currentCommands) == 1:
						self._log("Canceling heatup due to missing T: line in the past 5 seconds. cmdbuffer desync?")
						self._heatupWaiting = False
						# Force a timeout now if necessary
						timeout = time.time() - 1
					if self._extruderCount > 0:
						self._temperatureRequestExtruder = (self._temperatureRequestExtruder + 1) % self._extruderCount
						self.sendCommand("M105 T%d" % (self._temperatureRequestExtruder))
					else:
						self.sendCommand("M105")
					tempRequestTimeout = time.time() + 5
				if line == '' and time.time() > timeout:
					line = 'ok'
				if 'ok' in line:
					self.receivedOK()
					timeout = time.time() + 30
					if not self._heatupWaiting and not self._commandQueue.empty():
						self._sendCommand(self._commandQueue.get())
					if len(self._currentCommands) > 0 and \
					   ("G28" in self._currentCommands[0] or "G29" in self._currentCommands[0] or \
						"M109" in self._currentCommands[0] or "M190" in self._currentCommands[0]):
						# Long command detected. Timeout is now set to 10 minutes to avoid forcing 'ok'
						# every 30 seconds while it's not needed
						timeout = time.time() + 600
				elif 'start' in line:
					self._currentCommands = []
					timeout = time.time() + 30

		self._log("Connection closed, closing down monitor")

	
	def _log(self, message):
		#sys.stderr.write(message + "\n");
		self._callback.mcLog(message)
		try:
			self._logQueue.put(message, False)
		except:
			#If the log queue is full, remove the first message and append the new message again
			self._logQueue.get()
			try:
				self._logQueue.put(message, False)
			except:
				pass

	def _readline(self):
		if self._socket is None:
			return None
		try:
			while True:
				try:
					data=self._socket.recv(1024)
				except:
					#self._log("Recv: TIMEOUT")
					return ''
					
				self._linebuf.write(data)
				if '\n' in data: break
			self._linebuf = StringIO.StringIO(2048)
			self._linebuf = buff.getvalue().split(1)[1]
			
			ret = buff.getvalue().split(1)[0] + '\n'
			
		except:
			self._log("Unexpected error while reading TCP port: %s" % (getExceptionString()))
			self._errorValue = getExceptionString()
			self.close(True)
			return None
		if ret == '':
			#self._log("Recv: TIMEOUT")
			return ''
		self._log("Recv: %s" % (unicode(ret, 'ascii', 'replace').encode('ascii', 'replace').rstrip()))
		return ret
	
	def close(self, isError = False):
		if self._socket != None:
			self._socket.close()
			if isError:
				self._changeState(self.STATE_CLOSED_WITH_ERROR)
			else:
				self._changeState(self.STATE_CLOSED)
		self._socket = None
	
	def __del__(self):
		self.close()
	
	def _sendCommand(self, cmd):
		self._thread_lock.acquire(True)
		if self._socket is None:
			self._thread_lock.release()
			return
		if 'M109' in cmd or 'M190' in cmd:
			self._heatupWaitStartTime = time.time()
			self._heatupWaiting = True
		if 'M104' in cmd or 'M109' in cmd:
			try:
				t = 0
				if 'T' in cmd:
					t = int(re.search('T([0-9]+)', cmd).group(1))
				self._targetTemp[t] = float(re.search('S([0-9]+)', cmd).group(1))
			except:
				pass
		if 'M140' in cmd or 'M190' in cmd:
			try:
				self._bedTargetTemp = float(re.search('S([0-9]+)', cmd).group(1))
			except:
				pass
		self._log('Send: %s' % (cmd))
		if self.isOperational():
			self._currentCommands.append(cmd)
		try:
			self._socket.send(cmd + '\n')
		except serial.SerialTimeoutException:
			self._log("Network timeout while writing to TCP port, trying again.")
			try:
				time.sleep(0.5)
				self._socket.write(cmd + '\n')
			except:
				self._log("Unexpected error while writing serial port: %s" % (getExceptionString()))
				self._errorValue = getExceptionString()
				self.close(True)
		except:
			self._log("Unexpected error while writing serial port: %s" % (getExceptionString()))
			self._errorValue = getExceptionString()
			self.close(True)
		self._thread_lock.release()

	def _sendNext(self):
		if self._gcodePos >= len(self._gcodeList):
		        self._callback.mcProgress(self._gcodePos)
			self._changeState(self.STATE_OPERATIONAL)
			return
		if self._gcodePos == 100:
			self._printStartTime100 = time.time()
		line = self._gcodeList[self._gcodePos]
		if type(line) is tuple:
			self._printSection = line[1]
			line = line[0]
		try:
			if line == 'M0' or line == 'M1':
				self.setPause(True)
				line = 'M105'	#Don't send the M0 or M1 to the machine, as M0 and M1 are handled as an LCD menu pause.
			if self._printSection in self._feedRateModifier:
				line = re.sub('F([0-9]*)', lambda m: 'F' + str(int(int(m.group(1)) * self._feedRateModifier[self._printSection])), line)
			if ('G0' in line or 'G1' in line) and 'Z' in line:
				z = float(re.search('Z([-+]?[0-9\.]*)', line).group(1))
				if self._currentZ != z:
					self._currentZ = z
					self._callback.mcZChange(z)
		except:
			self._log("Unexpected error: %s" % (getExceptionString()))
		checksum = reduce(lambda x,y:x^y, map(ord, "N%d%s" % (self._gcodePos, line)))
		pos = self._gcodePos
		self._gcodePos += 1
		self._sendCommand("N%d%s*%d" % (pos, line, checksum))
		self._callback.mcProgress(self._gcodePos)

	def sendCommand(self, cmd):
		cmd = cmd.encode('ascii', 'replace')
		if self.isPrinting() or self.isPaused() or self.isOperational():
			# If waiting for heating, send M108 immediatly to
			# interrupt it instead of queueing it
			if self._heatupWaiting and "M108" in cmd:
				self._sendCommand(cmd)
			else:
				self._commandQueue.put(cmd)
				if len(self._currentCommands) == 0:
					self._sendCommand(self._commandQueue.get())

	def printGCode(self, gcodeList):
		if not self.isOperational() or self.isPrinting() or self.isPaused():
			return
		self._gcodeList = gcodeList
		self._gcodePos = 0
		self._printStartTime100 = None
		self._printSection = 'CUSTOM'
		self._changeState(self.STATE_PRINTING)
		self._printStartTime = time.time()
		for i in xrange(len(self._currentCommands), CMDBUFFER_SIZE):
			# One of the next 4 could enable the heatupWaiting mode
			if not self._heatupWaiting:
				self._sendNext()
	
	def cancelPrint(self):
		if self.isOperational():
			self._changeState(self.STATE_OPERATIONAL)
	
	def setPause(self, pause):
		if not pause and self.isPaused():
			self._changeState(self.STATE_PRINTING)
			for i in xrange(len(self._currentCommands), CMDBUFFER_SIZE):
				# One of the next 4 could enable the heatupWaiting mode
				if not self._heatupWaiting:
					if not self._commandQueue.empty():
						self._sendCommand(self._commandQueue.get())
					else:
						self._sendNext()
		if pause and self.isPrinting():
			self._changeState(self.STATE_PAUSED)
	
	def setFeedrateModifier(self, type, value):
		self._feedRateModifier[type] = value

def getExceptionString():
	locationInfo = traceback.extract_tb(sys.exc_info()[2])[0]
	return "%s: '%s' @ %s:%s:%d" % (str(sys.exc_info()[0].__name__), str(sys.exc_info()[1]), os.path.basename(locationInfo[0]), locationInfo[2], locationInfo[1])
