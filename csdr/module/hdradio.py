from csdr.module.nrsc5 import NRSC5, Mode, EventType, ComponentType, Access
from csdr.module import ThreadModule
from pycsdr.modules import Writer
from pycsdr.types import Format
from owrx.map import Map, LatLngLocation

import logging
import threading
import pickle

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class StationLocation(LatLngLocation):
    def __init__(self, data):
        super().__init__(data["lat"], data["lon"])
        # Complete station data
        self.data = data

    def getSymbolData(self, symbol, table):
        return {"symbol": symbol, "table": table, "index": ord(symbol) - 33, "tableindex": ord(table) - 33}

    def __dict__(self):
        # Return APRS-like dictionary object with "antenna tower" symbol
        res = super(StationLocation, self).__dict__()
        res["symbol"] = self.getSymbolData('r', '/')
        res.update(self.data)
        return res


class HdRadioModule(ThreadModule):
    def __init__(self, program: int = 0, amMode: bool = False):
        self.program    = program
        self.frequency  = 0
        self.metaLock   = threading.Lock()
        self.metaWriter = None
        self.meta       = {}
        self._clearMeta()
        # Initialize and start NRSC5 decoder
        self.radio = NRSC5(lambda evt_type, evt: self.callback(evt_type, evt))
        self.radio.open_pipe()
        self.radio.start()
# Crashes things?
#        self.radio.set_mode(Mode.AM if amMode else Mode.FM)
        super().__init__()

    def __del__(self):
        # Make sure NRSC5 object is truly destroyed
        if self.radio is not None:
            self.radio.stop()
            self.radio.close()
            self.radio = None

    def getInputFormat(self) -> Format:
        return Format.COMPLEX_SHORT

    def getOutputFormat(self) -> Format:
        return Format.SHORT

    def getFixedAudioRate(self) -> int:
        return 744188 # 744187.5

    # Change program
    def setProgram(self, program: int) -> None:
        if program != self.program:
            self.program = program
            logger.info("Now playing program #{0}".format(self.program))
            # Clear program metadata
            with self.metaLock:
                self.meta["program"] = self.program
                if "title" in self.meta:
                    del self.meta["title"]
                if "artist" in self.meta:
                    del self.meta["artist"]
                if "album" in self.meta:
                    del self.meta["album"]
                if "genre" in self.meta:
                    del self.meta["genre"]
                self._writeMeta()

    # Change frequency
    def setFrequency(self, frequency: int) -> None:
        if frequency != self.frequency:
            self.frequency = frequency
            self.program = 0
            logger.info("Now playing program #{0} at {1}MHz".format(self.program, self.frequency / 1000000))
            self._clearMeta()

    # Set metadata consumer
    def setMetaWriter(self, writer: Writer) -> None:
        self.metaWriter = writer

    # Write metadata
    def _writeMeta(self) -> None:
        if self.meta and self.metaWriter:
            logger.debug("Metadata: {0}".format(self.meta))
            self.metaWriter.write(pickle.dumps(self.meta))

    # Clear all metadata
    def _clearMeta(self) -> None:
        with self.metaLock:
            self.meta = {
                "mode"      : "HDR",
                "frequency" : self.frequency,
                "program"   : self.program
            }
            self._writeMeta()

    # Update existing metadata
    def _updateMeta(self, data) -> None:
        # Update station location on the map
        if "station" in data and "lat" in data and "lon" in data:
            loc = StationLocation(data)
            Map.getSharedInstance().updateLocation(data["station"], loc, "HDR")
        # Update any new or different values
        with self.metaLock:
            changes = 0
            for key in data.keys():
                if key not in self.meta or self.meta[key] != data[key]:
                    self.meta[key] = data[key]
                    changes = changes + 1
            # If anything changed, write metadata to the buffer
            if changes > 0:
                self._writeMeta()

    def run(self):
        # Start NRSC5 decoder
        logger.debug("Starting NRSC5 decoder...")

        # Main loop
        logger.debug("Running the loop...")
        while self.doRun:
            data = self.reader.read()
            if data is None or len(data) == 0:
                self.doRun = False
            else:
                try:
                    self.radio.pipe_samples_cs16(data.tobytes())
                except Exception as exptn:
                    logger.debug("Exception: %s" % str(exptn))

        # Stop NRSC5 decoder
        logger.debug("Stopping NRSC5 decoder...")
        self.radio.stop()
        self.radio.close()
        self.radio = None
        logger.debug("DONE.")

    def callback(self, evt_type, evt):
        if evt_type == EventType.LOST_DEVICE:
            logger.info("Lost device")
            self.doRun = False
        elif evt_type == EventType.AUDIO:
            if evt.program == self.program:
                self.writer.write(evt.data)
        elif evt_type == EventType.HDC:
            if evt.program == self.program:
                #logger.info("HDC data for program %d", evt.program)
                pass
        elif evt_type == EventType.IQ:
            logger.info("IQ data")
        elif evt_type == EventType.SYNC:
            logger.info("Synchronized")
        elif evt_type == EventType.LOST_SYNC:
            logger.info("Lost synchronization")
        elif evt_type == EventType.MER:
            logger.info("MER: %.1f dB (lower), %.1f dB (upper)", evt.lower, evt.upper)
        elif evt_type == EventType.BER:
            logger.info("BER: %.6f", evt.cber)
        elif evt_type == EventType.ID3:
            if evt.program == self.program:
                # Collect new metadata
                meta = {}
                if evt.title:
                    meta["title"] = evt.title
                if evt.artist:
                    meta["artist"] = evt.artist
                if evt.album:
                    meta["album"] = evt.album
                if evt.genre:
                    meta["genre"] = evt.genre
                if evt.ufid:
                    logger.info("Unique file identifier: %s %s", evt.ufid.owner, evt.ufid.id)
                if evt.xhdr:
                    logger.info("XHDR: param=%s mime=%s lot=%s", evt.xhdr.param, evt.xhdr.mime, evt.xhdr.lot)
                # Update existing metadata
                self._updateMeta(meta)
        elif evt_type == EventType.SIG:
            for service in evt:
                logger.info("SIG Service: type=%s number=%s name=%s",
                    service.type, service.number, service.name)
                for component in service.components:
                    if component.type == ComponentType.AUDIO:
                        logger.info("  Audio component: id=%s port=%04X type=%s mime=%s",
                            component.id, component.audio.port,
                            component.audio.type, component.audio.mime)
                    elif component.type == ComponentType.DATA:
                        logger.info("  Data component: id=%s port=%04X service_data_type=%s type=%s mime=%s",
                            component.id, component.data.port,
                            component.data.service_data_type,
                            component.data.type, component.data.mime)
        elif evt_type == EventType.STREAM:
            logger.info("Stream data: port=%04X seq=%04X mime=%s size=%s",
                evt.port, evt.seq, evt.mime, len(evt.data))
        elif evt_type == EventType.PACKET:
            logger.info("Packet data: port=%04X seq=%04X mime=%s size=%s",
                evt.port, evt.seq, evt.mime, len(evt.data))
        elif evt_type == EventType.LOT:
            time_str = evt.expiry_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info("LOT file: port=%04X lot=%s name=%s size=%s mime=%s expiry=%s",
                         evt.port, evt.lot, evt.name, len(evt.data), evt.mime, time_str)
        elif evt_type == EventType.SIS:
            # Collect new metadata
            meta = {
                "audio_services" : [],
                "data_services"  : []
            }
            if evt.country_code:
                meta["country"] = evt.country_code
                meta["fcc_id"]  = evt.fcc_facility_id
            if evt.name:
                meta["station"] = evt.name
            if evt.slogan:
                meta["slogan"] = evt.slogan
            if evt.message:
                meta["message"] = evt.message
            if evt.alert:
                meta["alert"] = evt.alert
            if evt.latitude:
                meta["lat"] = evt.latitude
                meta["lon"] = evt.longitude
                meta["altitude"] = round(evt.altitude)
            for audio_service in evt.audio_services:
                #logger.info("Audio program %s: %s, type: %s, sound experience %s",
                #    audio_service.program,
                #    "public" if audio_service.access == Access.PUBLIC else "restricted",
                #    self.radio.program_type_name(audio_service.type),
                #    audio_service.sound_exp)
                meta["audio_services"] += [{
                    "id"   : audio_service.program,
                    "type" : audio_service.type.value,
                    "name" : self.radio.program_type_name(audio_service.type),
                    "public" : audio_service.access == Access.PUBLIC,
                    "experience" : audio_service.sound_exp
                }]
            for data_service in evt.data_services:
                #logger.info("Data service: %s, type: %s, MIME type %03x",
                #    "public" if data_service.access == Access.PUBLIC else "restricted",
                #    self.radio.service_data_type_name(data_service.type),
                #    data_service.mime_type)
                meta["data_services"] += [{
                    "mime" : data_service.mime_type,
                    "type" : data_service.type.value,
                    "name" : self.radio.service_data_type_name(data_service.type),
                    "public" : data_service.access == Access.PUBLIC
                }]
            # Update existing metadata
            self._updateMeta(meta)
