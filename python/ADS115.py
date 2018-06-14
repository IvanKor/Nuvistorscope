import csv
from multiprocessing import Process, current_process, Pipe
import os
import sys
import time

try:
    import serial
    import codecs
    import numpy as np   
    import time 

except:
    ADS115 = False

import utils


ADS115_READ_COUNT = 8 # number of bytes to read from ADS115 at a time



def read_ADS115(conn, conn_start, serial_no, serial_speed, channels):
    """Read data from a device and supply it through a pipe.

    conn:       connection to pipe for sending data
    conn_start: control channel, see start_ADS115 for explanation
    serial_no:  identifier for ADS115 device
    channels:   list of channels to read from (must be integers from 0-255)
    """
    sys.setcheckinterval(1)
    #global iii,ZW,ZWW
    ZWW = 100 #windows for Z
    calc_Gs = 0
    XW=np.zeros(ZWW, dtype=int)
    YW=np.zeros(ZWW, dtype=int)
    ZW=np.zeros(ZWW, dtype=int)
    try:
        #print(serial_no)
        #device = serial.Serial(serial_no, 230400, timeout=None)  # open first serial port
        device = serial.Serial(serial_no, serial_speed, timeout=None)  # open first serial port
        #print('open')
        #device.close()
        #device.open()
        #print(device)   
        #sys.stdout.flush()     
        conn_start.send('ok')
        #print('open Ok')
    except:
        conn_start.send('fail')
        return
    start = utils.timer()
    iii = 0
    ZW_Old = 32767
    while 1:
        try:
            if conn.poll():
                cmd = conn.recv()
                #print(cmd)   
                #sys.stdout.flush()   
                if cmd == 'STOP':
                    break
                if cmd[0] == 'on_128SPS':
                    while (device.in_waiting <= 2):
                        time.sleep(0.001) # seconds
                        pass
                    device.write(b'S')
                    calc_Gs = cmd[1]
                if cmd[0] == 'on_250SPS':
                    while (device.in_waiting <= 2):
                        time.sleep(0.001) # seconds
                        pass
                    device.write(b's')
                    calc_Gs = cmd[1]
            if (iii == 0):
                start = utils.timer()
            #while (device.in_waiting <= 2):
                #time.sleep(0.001) # seconds
                #pass
            line = codecs.decode((device.readline()),'ascii')
            if (device.in_waiting > 100) :
                print(device.in_waiting)
                sys.stdout.flush()
            ZW[int(iii)] = int(line)
            #ZW[int(iii)] = int(round(int(line) * float(calc_Gs)))
            if (ZW[int(iii)] > 32769):
                print(ZW[int(iii)])   
                sys.stdout.flush()   
                ZW[int(iii)] = ZW_Old
            else:
                ZW_Old = ZW[int(iii)]

            #ZW[int(iii)] = int(round((32768 - int(line) - 1900) / 348.71))
            #348.71 per volt
            ZW[int(iii)] = ((32768 - int(line) - 1900 )*1000.0)/348.71
            #ZW[int(iii)] = 10000 
            #ZW[int(iii)] = 32768 - int(line) 
            #ZW[int(iii)] = (32768 - int(line) ) / 348
            #print(ZW[int(iii)])   
            #sys.stdout.flush() 
            iii +=1
            if (iii==ZWW) :
                duration = utils.timer() - start
                conn.send([1, duration, ZW])
                iii =0

        except IOError:
            # probably a pipe failure, so we cannot send a message on it
            # [Errno 109] The pipe has been ended
            # [Errno 232] The pipe is being closed
            print('except IOError read_ADS115', str(sys.exc_info()[1]))
            break
        except:
            print('except read_ADS115', str(sys.exc_info()[1]))
            conn.send(str(sys.exc_info()[1]))
            pass
            #break
    device.close()
    print('process "%s" closing' % current_process().name)


def start(app, path, sources):
    """Start a possible background process to feed data to the application.

    Return:     process, desired application state

    The possible sources are given in the configuration file, e.g.
        sources=ADS115
    They receive on the pipe:
        STOP    terminate the process
        LOOP    (files only) send data slowly and loop when done
        NOLOOP  (files only) send all data at once
    """
    parts = next(csv.reader([sources]))
    parts = [x.strip('" ') for x in parts]
    proc = None
    while parts:
        name = parts.pop(0)
        if name in app.states:
            state = app.states.index(name)
            params = []
            while parts and parts[0] not in app.states:
                params.append(parts.pop(0))
            # try to start the source
            if  state == app.ADS115:
                proc = start_ADS115(app, name, params)
                if proc:
                    break
        else:
            app.child_conn.send('Unknown data source "%s"' % name)
            proc = None
            state = app.SETUP
    return proc, state


def start_ADS115(app, name, params):
    """Start a process to read data from a device."""
    if serial:
        try:
            serial_no = ''
            
            channels = []
            # parse the parameters for device ID and channels
            for part in params:
                if part.isdigit():
                    number = int(part)
                    #print('number= ',number)
                    serial_speed = number
                else:
                    serial_no = part
            channels.append(1)        
            #print(serial_no, channels, number)
            if serial_no and channels:
                # It is not possible to pass an open ADS115 object to a process
                # because it cannot be pickled, so it is opened by the process.
                # In order to know whether it was opened successfully or not,
                # we create a unidirectional pipe.
                parent, child = Pipe(False)

                #print(child)   
                #sys.stdout.flush() 

                # start a process to receive and buffer data
                #print(read_ADS115,name,app.child_conn,child,serial_no, channels)
                proc = Process(target=read_ADS115,
                               name=name,
                               args=(app.child_conn,
                                     child,
                                     serial_no,
                                     serial_speed,
                                     channels))
                proc.daemon = True
                proc.start()
                # read the pipe to determine if we connected to a device
                sts = parent.recv()
                #print(sts)
                if sts == 'ok':
                    return proc
        except:
            print(serial_no,'except: start_ADS115')
            pass
    else:
        app.child_conn.send('Could not import ADS115 module')



