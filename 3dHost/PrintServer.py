import socket
import serial
import time
import Queue
import threading

class PrintClientThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, conn, device):
        super(PrintClientThread, self).__init__()
        self._stop = threading.Event()
        self._conn = conn
        self._device = device
        self._ser = None
        self._isIdle = False

    def isIdle(self):
        return self._isIdle

    def stop(self):
        try:
            self._ser.close()
        except serial.SerialException:
            pass

        try:
            self._conn.close()
        except socket.error:
            pass

        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        # Open Serial Port Connection
        print 'Opening Connection to Printer on Device %s' % (self._device)
        self._ser = serial.Serial(self._device, 115200, timeout=0.1)

        self._conn.settimeout(0.1);

        idleTimeout = time.time() + 10

        while True:
            try:
                data = self._conn.recv(1024)
                self._ser.write(data)

                # Check For Idle State
                if not data.find('M105') >= 0:
                    # reset timeout
                    idleTimeout = time.time() + 10;
                    self._isIdle = False
                if time.time() > idleTimeout:
                    self._isIdle = True

            except socket.timeout:  # No Data Received, Pass
                pass
            except socket.error, e:
                if e[0] == socket.errno.ECONNRESET:
                    print 'Socket Reset by Client for Device: %s' % (self._device)
                else:
                    print 'Socket Error on Write'
                break
            except serial.SerialException:
                break

            try:
                data = self._ser.readline()
                self._conn.send(data)
            except serial.SerialTimeoutException:  # No Data Received, Pass
                pass
            except serial.SerialException:
                break;
            except socket.error, e:
                if e[0] == socket.errno.ECONNRESET:
                    print 'Socket Reset by Client for Device: %s' % (self._device)
                else:
                    print 'Socket Error on Write'
                break
        time.sleep(0.1)
        # Connection Closed. Listen For More Connections
        try:
            self._conn.close()
        except:
            pass

        try:
            self._ser.close()
        except:
            pass




class PrintServer(threading.Thread):

    def __init__(self, serialnum, device, port):
        super(PrintServer, self).__init__()
        self._stop = threading.Event()

        self._serialnum = serialnum
        self._device = device
        self._port = port
        self._tcp = None
        self._connIdleQueue = Queue.Queue
        self._clientThread = None

    def stop(self):
        if self._tcp != None:
            try:
                self._tcp.close()
            except socket.Error:
                pass
        if self._clientThread != None:
            self._clientThread.stop()
            self._clientThread.join()

        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        print 'Starting Server for Printer: %s on Device: %s on Port: %s.' % (self._serialnum, self._device, self._port)
        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.bind(('', int(self._port)))

        while True:
            try:
                self._tcp.settimeout(1.0)
                self._tcp.listen(1)
                conn, addr = self._tcp.accept()

                print "New Connection Accepted"
                #Kill the existing Thread if Allowed
                if self._clientThread != None:
                    if self._clientThread.isAlive():
                        if self._clientThread.isIdle():
                            print "Killing Old Connection"
                            self._clientThread.stop();
                            self._clientThread.join();

                            self._clientThread = PrintClientThread(conn, self._device)
                            self._clientThread.start()
                            print "Client Thread Started"
                        else:
                            conn.close()
                    else:
                        self._clientThread = PrintClientThread(conn, self._device)
                        self._clientThread.start()
                else:
                    print "Client Thread Started"
                    self._clientThread = PrintClientThread(conn, self._device)
                    self._clientThread.start()
            except socket.timeout:
                pass
            except:
                return;






