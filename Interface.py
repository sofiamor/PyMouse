from DatabaseTables import *
from time import sleep
import numpy as np
from utils.Timer import *
from concurrent.futures import ThreadPoolExecutor
import threading, multiprocessing,struct, time, socket

class Interface:
    def __init__(self, logger):
        self.logger = logger
        self.probe = 0
        self.lick_tmst = 0
        self.ready_tmst = 0
        self.ready_dur =0
        self.ready = False
        self.logging = False
        self.timer_probe1 = Timer()
        self.timer_probe2 = Timer()
        self.timer_ready = Timer()
        self.thread = ThreadPoolExecutor(max_workers=2)
        self.probes = (LiquidCalibration() & dict(setup=self.logger.setup)).fetch('probe')
        self.weight_per_pulse = dict()
        self.pulse_dur = dict()
        for probe in list(set(self.probes)):
            key = dict(setup=self.logger.setup, probe=probe)
            dates = (LiquidCalibration() & key).fetch('date', order_by='date')
            key['date'] = dates[-1]  # use the most recent calibration
            self.pulse_dur[probe], pulse_num, weight = \
                (LiquidCalibration.PulseWeight() & key).fetch('pulse_dur', 'pulse_num', 'weight')
            self.weight_per_pulse[probe] = np.divide(weight, pulse_num)

    def give_air(self, probe, duration, log=True):
        pass

    def give_liquid(self, probe, duration=False, log=True):
        pass

    def give_odor(self, odor_idx, duration, log=True):
        pass

    def give_sound(self, sound_freq, duration, dutycycle):
        pass

    def get_last_lick(self):
        probe = self.probe
        self.probe = 0
        return probe, self.lick_tmst

    def probe1_licked(self, channel):
        self.lick_tmst = self.logger.log('Lick', dict(probe=1)) if self.logging else self.logger.logger_timer.elapsed_time()
        self.timer_probe1.start()
        self.probe = 1

    def probe2_licked(self, channel):
        self.lick_tmst = self.logger.log('Lick', dict(probe=2)) if self.logging else self.logger.logger_timer.elapsed_time()
        self.timer_probe2.start()
        self.probe = 2

    def in_position(self):
        return True, 0

    def create_pulse(self, probe, duration):
        pass

    def calc_pulse_dur(self, reward_amount):  # calculate pulse duration for the desired reward amount
        actual_rew = dict()
        for probe in list(set(self.probes)):
            duration = np.interp(reward_amount/1000,
                                                  self.weight_per_pulse[probe], self.pulse_dur[probe])
            self.create_pulse(probe, duration)
            actual_rew[probe] = np.max((np.min(self.weight_per_pulse[probe]), reward_amount/1000)) * 1000 # in uL
        return actual_rew

    def cleanup(self):
        pass


class RPProbe(Interface):
    def __init__(self, logger, callbacks=True, logging=True):
        super(RPProbe, self).__init__(logger)
        from RPi import GPIO
        import pigpio
        self.setup_name = int(''.join(list(filter(str.isdigit, socket.gethostname()))))
        self.GPIO = GPIO
        self.logging = logging
        self.GPIO.setmode(self.GPIO.BCM)
        self.channels = {'air': {1: 24, 2: 25},
                         'liquid': {1: 22, 2: 23},
                         'lick': {1: 17, 2: 27},
                         'start': {1: 9},
                         'sound': {1: 18}}
        self.callbacks = callbacks
        self.frequency = 20
        self.pulses = dict()
        self.GPIO.setup(list(self.channels['lick'].values()) + [self.channels['start'][1]],
                        self.GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self.GPIO.setup(list(self.channels['air'].values()), self.GPIO.OUT, initial=self.GPIO.LOW)
        self.Pulser = pigpio.pi()
        self.PulseGen = pigpio.pulse
        self.Pulser.set_mode(self.channels['liquid'][1], pigpio.OUTPUT)
        self.Pulser.set_mode(self.channels['liquid'][2], pigpio.OUTPUT)
        self.Pulser.set_mode(self.channels['sound'][1], pigpio.OUTPUT)
        if callbacks:
            self.GPIO.add_event_detect(self.channels['lick'][2], self.GPIO.RISING,
                                       callback=self.probe2_licked, bouncetime=100)
            self.GPIO.add_event_detect(self.channels['lick'][1], self.GPIO.RISING,
                                       callback=self.probe1_licked, bouncetime=100)
            self.GPIO.add_event_detect(self.channels['start'][1], self.GPIO.BOTH,
                                       callback=self.position_change, bouncetime=50)

    def give_liquid(self, probe):
        self.thread.submit(self.pulse_out, probe)

    def give_odor(self, delivery_port, odor_id, odor_duration, dutycycle):
        for i, idx in enumerate(odor_id):
            self.thread.submit(self.__pwd_out, self.channels['air'][delivery_port[i]], odor_duration, dutycycle[i])

    def give_sound(self, sound_freq=40000, duration=500, dutycycle=50):
        self.thread.submit(self.__pwd_out, self.channels['air'][1], sound_freq, duration, dutycycle)

    def position_change(self, channel=0):
        if self.getStart():
            self.timer_ready.start()
            if not self.ready:
                self.ready = True
                self.ready_tmst = self.logger.log('CenterPort', dict(in_position=self.ready))
                print('in position')
        else:
            if self.ready:
                self.ready = False
                tmst = self.logger.log('CenterPort', dict(in_position=self.ready))
                self.ready_dur = tmst - self.ready_tmst
                print('off position')

    def in_position(self):
        # handle missed events
        ready = self.getStart()
        if self.ready != ready:
            self.position_change()
        if not self.ready:
            ready_dur = self.ready_dur
        else:
            ready_dur = self.timer_ready.elapsed_time()
        return self.ready, ready_dur, self.ready_tmst

    def __pwd_out(self, channel, duration, dutycycle):
        pwm = self.GPIO.PWM(channel, self.frequency)
        pwm.ChangeFrequency(self.frequency)
        pwm.start(dutycycle)
        sleep(duration/1000)    # to add a  delay in seconds
        pwm.stop()

    def __pwm_out(self, channel, freq, duration, dutycycle=50):
        self.Pulser.hardware_PWM(channel, freq, dutycycle*10000)
        sleep(duration/1000)    # to add a  delay in seconds
        self.Pulser.hardware_PWM(channel, 0, 0)

    def create_pulse(self, probe, duration):
        if probe in self.pulses:
            self.Pulser.wave_delete(self.pulses[probe])
        pulse = []
        pulse.append(self.PulseGen(1 << self.channels['liquid'][probe], 0, int(duration*1000)))
        pulse.append(self.PulseGen(0, 1 << self.channels['liquid'][probe], int(duration)))
        self.Pulser.wave_add_generic(pulse)  # 500 ms flashes
        self.pulses[probe] = self.Pulser.wave_create()

    def pulse_out(self, probe):
        self.Pulser.wave_send_once(self.pulses[probe])

    def getStart(self):
        return not self.GPIO.input(self.channels['start'][1])

    def cleanup(self):
        self.Pulser.wave_clear()
        if self.callbacks:
            self.GPIO.remove_event_detect(self.channels['lick'][1])
            self.GPIO.remove_event_detect(self.channels['lick'][2])
            self.GPIO.remove_event_detect(self.channels['start'][1])
        self.GPIO.cleanup()


class VRProbe(Interface):
    def __init__(self, logger):
        super(VRProbe, self).__init__(logger)
        from RPi import GPIO
        import pigpio
        self.setup = int(''.join(list(filter(str.isdigit, socket.gethostname()))))
        self.GPIO = GPIO
        self.GPIO.setmode(self.GPIO.BCM)
        self.frequency = 5
        self.channels = {'odor': {1: 19, 2: 16, 3: 26, 4: 20},
                         'liquid': {1: 22},
                         'lick': {1: 17}}
        self.dutycycles = 50
        self.GPIO.setup(list(self.channels['lick'].values()),
                        self.GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self.GPIO.setup(list(self.channels['odor'].values()), self.GPIO.OUT, initial=self.GPIO.LOW)
        self.GPIO.add_event_detect(self.channels['lick'][1], self.GPIO.RISING, callback=self.probe1_licked, bouncetime=100)
        self.Pulser = pigpio.pi()
        self.PulseGen = pigpio.pulse
        self.Pulser.set_mode(self.channels['liquid'][1], pigpio.OUTPUT)
        self.pulses = dict()
        self.pwm = dict()

    def give_air(self, probe, duration, log=True):
        super().give_air(probe, duration, log)

    def give_liquid(self, probe):
        self.thread.submit(self.pulse_out, probe)

    def start_odor(self, dutycycle = 50):
        for idx, channel in enumerate(list(self.channels['odor'].values())):
            self.pwm[idx] = self.GPIO.PWM(channel, self.frequency)
            self.pwm[idx].ChangeFrequency(self.frequency)
            self.pwm[idx].start(dutycycle)

    def update_odor(self, dutycycles):  # for 2D olfactory setup
        for idx, dutycycle in enumerate(dutycycles):
            self.pwm[idx].ChangeDutyCycle(dutycycle)

    def create_pulse(self, probe, duration):
        if probe in self.pulses:  self.Pulser.wave_delete(self.pulses[probe])
        pulse = [self.PulseGen(1 << self.channels['liquid'][probe], 0, int(duration*1000)),
                 self.PulseGen(0, 1 << self.channels['liquid'][probe], int(duration))]
        self.Pulser.wave_add_generic(pulse)  # 500 ms flashes
        self.pulses[probe] = self.Pulser.wave_create()

    def pulse_out(self, probe):
        self.Pulser.wave_send_once(self.pulses[probe])

    def clean_odor_pulses(self):
        for idx, channel in enumerate(list(self.channels['odor'].values())):
            self.pwm[idx].stop()

    def cleanup(self):
        for idx, channel in enumerate(list(self.channels['odor'].values())):
            self.pwm[idx].stop()
        self.GPIO.remove_event_detect(self.channels['lick'][1])
        self.GPIO.cleanup()
        self.Pulser.wave_clear()


class Ball(Interface):
    def __init__(self, logger, ball_radius=0.125, path="", target_path=False):
        from utils.Writer import Writer
        self.quit()
        self.logger = logger
        self.mouse1 = MouseReader("/dev/input/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.1:1.0-mouse", logger)
        self.mouse2 = MouseReader("/dev/input/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-mouse", logger)
        self.Writer = Writer
        self.speed = 0
        self.timestamp = 0
        self.setPosition()
        self.phi_z1 = 1  # angle of z axis (rotation)
        self.phi_z2 = self.phi_z1
        self.phi_y1 = np.pi - 0.13  # angle of y1 axis (mouse1) .6
        self.phi_y2 = self.phi_y1 + np.pi/2  # angle of y2 axis (mouse2)
        self.ball_radius = ball_radius
        self.createDataset(path, target_path)
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.readMouse)
        self.thread_runner.start()


    def readMouse(self):
        while not self.thread_end.is_set():
            x1, y1, x2, y2, tmst1, tmst2 = 0, 0, 0, 0, time.time(), time.time()
            while not self.mouse1.queue.empty():
                data1 = self.mouse1.queue.get()
                x1 += data1['x']; y1 += data1['y']; tmst1 = data1['timestamp']

            while not self.mouse2.queue.empty():
                data2 = self.mouse2.queue.get()
                x2 += data2['x']; y2 += data2['y']; tmst2 = data2['timestamp']

            theta_contamination1 = y2*(np.sin(self.phi_z1)**2)
            theta_contamination2 = -y1*(np.sin(self.phi_z2)**2)

            theta_step1 = (x1 - theta_contamination1)/(np.sin(self.phi_z1)**2)/self.ball_radius
            theta_step2 = (x2 - theta_contamination2)/(np.sin(self.phi_z2)**2)/self.ball_radius

            xm = y2 * np.cos(self.phi_y1) - y1 * np.sin(self.phi_y1)
            ym = y2 * np.sin(self.phi_y1) + y1 * np.cos(self.phi_y1)

            self.theta += (theta_step2 + theta_step1)/2
            self.theta = np.mod(self.theta, 2*np.pi)

            x = -xm*np.sin(self.theta) - ym*np.cos(self.theta)
            y = -xm*np.cos(self.theta) + ym*np.sin(self.theta)

            loc_x = min(self.loc_x + np.double(x), self.xmx)
            loc_y = min(self.loc_y + np.double(y), self.ymx)
            timestamp = max(tmst1, tmst2)
            self.speed = np.sqrt((loc_x - self.loc_x)**2 + (loc_y - self.loc_y)**2)/(timestamp - self.timestamp)
            self.loc_x = loc_x
            self.loc_y = loc_y
            self.timestamp = timestamp
            print(self.loc_x, self.loc_y, self.theta/np.pi*180)
            self.append2Dataset()
            time.sleep(.1)

    def setPosition(self, xmx=1, ymx=1, x0=0, y0=0, theta0=0):
        self.loc_x = x0
        self.loc_y = y0
        self.theta = theta0
        self.xmx = xmx
        self.ymx = ymx

    def getPosition(self):
        return self.loc_x, self.loc_y, self.theta,  self.timestamp

    def getSpeed(self):
        return self.speed

    def createDataset(self, path='', target_path=False):
        datapath = path + datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + ".h5"
        TIME_SERIES_DOUBLE = np.dtype([("loc_x", np.double),
                                       ("loc_y", np.double),
                                       ("theta", np.double),
                                       ("tmst", np.double)])

        self.dataset = self.Writer(datapath, target_path)
        self.dataset.createDataset('tracking_data', shape=(4,), dtype=TIME_SERIES_DOUBLE)

    def append2Dataset(self):
        self.dataset.append('tracking_data', [self.loc_x, self.loc_y, self.theta, self.timestamp])

    def closeDatasets(self):
        print('GIATI')
        self.dataset.exit()

    def quit(self):
        print('I m quitting')
        try:
            self.thread_end.set()
            self.closeDatasets()
            self.mouse1.close()
            self.mouse2.close()
        except:
            print('ball not running')


class MouseReader:
    def __init__(self, path, logger, dpm=31200):
        print('setting up mouse')
        self.logger = logger
        self.dpm = dpm
        self.queue = multiprocessing.Queue()
        self.file = open(path, "rb")
        self.thread_end = multiprocessing.Event()
        self.thread_runner = multiprocessing.Process(target=self.reader, args=(self.queue, self.dpm,))
        self.thread_runner.start()

    def reader(self, queue, dpm):
        while not self.thread_end.is_set():
            # print('Reading file')
            data = self.file.read(3)  # Reads the 3 bytes
            x, y = struct.unpack("2b", data[1:])
            queue.put({'x': x/dpm, 'y': y/dpm, 'timestamp': self.logger.session_timer.elapsed_time()})

    def close(self):
        self.thread_end.set()
        self.thread_runner.join()

