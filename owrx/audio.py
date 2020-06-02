from abc import ABC, ABCMeta, abstractmethod
from owrx.config import Config
from owrx.metrics import Metrics, CounterMetric, DirectMetric
import threading
import wave
import subprocess
import os
from multiprocessing.connection import Pipe, wait
from datetime import datetime, timedelta
from queue import Queue, Full


import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class QueueJob(object):
    def __init__(self, decoder, file, freq):
        self.decoder = decoder
        self.file = file
        self.freq = freq

    def run(self):
        self.decoder.decode(self)

    def unlink(self):
        try:
            os.unlink(self.file)
        except FileNotFoundError:
            pass


class QueueWorker(threading.Thread):
    def __init__(self, queue):
        self.queue = queue
        self.doRun = True
        super().__init__(daemon=True)

    def run(self) -> None:
        while self.doRun:
            job = self.queue.get()
            try:
                job.run()
            except Exception:
                logger.exception("failed to decode job")
                self.queue.onError()
            finally:
                job.unlink()

            self.queue.task_done()


class DecoderQueue(Queue):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with DecoderQueue.creationLock:
            if DecoderQueue.sharedInstance is None:
                pm = Config.get()
                DecoderQueue.sharedInstance = DecoderQueue(maxsize=pm["decoding_queue_length"], workers=pm["decoding_queue_workers"])
        return DecoderQueue.sharedInstance

    def __init__(self, maxsize, workers):
        super().__init__(maxsize)
        metrics = Metrics.getSharedInstance()
        metrics.addMetric("decoding.queue.length", DirectMetric(self.qsize))
        self.inCounter = CounterMetric()
        metrics.addMetric("decoding.queue.in", self.inCounter)
        self.outCounter = CounterMetric()
        metrics.addMetric("decoding.queue.out", self.outCounter)
        self.overflowCounter = CounterMetric()
        metrics.addMetric("decoding.queue.overflow", self.overflowCounter)
        self.errorCounter = CounterMetric()
        metrics.addMetric("decoding.queue.error", self.errorCounter)
        self.workers = [self.newWorker() for _ in range(0, workers)]

    def put(self, item, **kwars):
        self.inCounter.inc()
        try:
            super(DecoderQueue, self).put(item, block=False)
        except Full:
            self.overflowCounter.inc()
            raise

    def get(self, **kwargs):
        # super.get() is blocking, so it would mess up the stats to inc() first
        out = super(DecoderQueue, self).get(**kwargs)
        self.outCounter.inc()
        return out

    def newWorker(self):
        worker = QueueWorker(self)
        worker.start()
        return worker

    def onError(self):
        self.errorCounter.inc()


class AudioChopperProfile(ABC):
    @abstractmethod
    def getInterval(self):
        pass

    @abstractmethod
    def getFileTimestampFormat(self):
        pass

    @abstractmethod
    def decoder_commandline(self, file):
        pass


class AudioWriter(object):
    def __init__(self, dsp, source, profile: AudioChopperProfile):
        self.dsp = dsp
        self.source = source
        self.profile = profile
        self.tmp_dir = Config.get()["temporary_directory"]
        self.wavefile = None
        self.wavefilename = None
        self.switchingLock = threading.Lock()
        self.timer = None
        (self.outputReader, self.outputWriter) = Pipe()

    def getWaveFile(self):
        filename = "{tmp_dir}/openwebrx-audiochopper-{id}-{timestamp}.wav".format(
            tmp_dir=self.tmp_dir,
            id=id(self),
            timestamp=datetime.utcnow().strftime(self.profile.getFileTimestampFormat()),
        )
        wavefile = wave.open(filename, "wb")
        wavefile.setnchannels(1)
        wavefile.setsampwidth(2)
        wavefile.setframerate(12000)
        return filename, wavefile

    def getNextDecodingTime(self):
        t = datetime.utcnow()
        zeroed = t.replace(minute=0, second=0, microsecond=0)
        delta = t - zeroed
        interval = self.profile.getInterval()
        seconds = (int(delta.total_seconds() / interval) + 1) * interval
        t = zeroed + timedelta(seconds=seconds)
        logger.debug("scheduling: {0}".format(t))
        return t

    def cancelTimer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _scheduleNextSwitch(self):
        self.cancelTimer()
        delta = self.getNextDecodingTime() - datetime.utcnow()
        self.timer = threading.Timer(delta.total_seconds(), self.switchFiles)
        self.timer.start()

    def switchFiles(self):
        self.switchingLock.acquire()
        file = self.wavefile
        filename = self.wavefilename
        (self.wavefilename, self.wavefile) = self.getWaveFile()
        self.switchingLock.release()

        file.close()
        job = QueueJob(self, filename, self.dsp.get_operating_freq())
        try:
            DecoderQueue.getSharedInstance().put(job)
        except Full:
            logger.warning("decoding queue overflow; dropping one file")
            job.unlink()
        self._scheduleNextSwitch()

    def decode(self, job: QueueJob):
        logger.debug("processing file %s", job.file)
        decoder = subprocess.Popen(
            ["nice", "-n", "10"] + self.profile.decoder_commandline(job.file),
            stdout=subprocess.PIPE,
            cwd=self.tmp_dir,
            close_fds=True,
            )
        for line in decoder.stdout:
            self.outputWriter.send((job.freq, line))
        try:
            rc = decoder.wait(timeout=10)
            if rc != 0:
                logger.warning("decoder return code: %i", rc)
        except subprocess.TimeoutExpired:
            logger.warning("subprocess (pid=%i}) did not terminate correctly; sending kill signal.", decoder.pid)
            decoder.kill()

    def start(self):
        (self.wavefilename, self.wavefile) = self.getWaveFile()
        self._scheduleNextSwitch()

    def write(self, data):
        self.switchingLock.acquire()
        self.wavefile.writeframes(data)
        self.switchingLock.release()

    def stop(self):
        self.outputReader.close()
        self.outputWriter.close()
        self.cancelTimer()
        try:
            os.unlink(self.wavefilename)
        except Exception:
            logger.exception("error removing undecoded file")


class AudioChopper(threading.Thread, metaclass=ABCMeta):
    def __init__(self, dsp, source, *profiles: AudioChopperProfile):
        self.source = source
        self.writers = [AudioWriter(dsp, source, p) for p in profiles]
        self.doRun = True
        super().__init__()

    def run(self) -> None:
        logger.debug("Audio chopper starting up")
        for w in self.writers:
            w.start()
        while self.doRun:
            data = self.source.read(256)
            if data is None or (isinstance(data, bytes) and len(data) == 0):
                self.doRun = False
            else:
                for w in self.writers:
                    w.write(data)

        logger.debug("Audio chopper shutting down")
        for w in self.writers:
            w.stop()

    def read(self):
        try:
            readers = wait([w.outputReader for w in self.writers])
            return [r.recv() for r in readers]
        except EOFError:
            return None
