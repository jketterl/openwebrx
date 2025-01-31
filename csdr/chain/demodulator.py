from csdr.chain import Chain
from abc import ABC, ABCMeta, abstractmethod
from pycsdr.modules import Writer


class FixedAudioRateChain(ABC):
    @abstractmethod
    def getFixedAudioRate(self) -> int:
        pass


class FixedIfSampleRateChain(ABC):
    @abstractmethod
    def getFixedIfSampleRate(self) -> int:
        pass


class DialFrequencyReceiver(ABC):
    @abstractmethod
    def setDialFrequency(self, frequency: int) -> None:
        pass


# marker interface
class HdAudio:
    pass


class MetaProvider(ABC):
    @abstractmethod
    def setMetaWriter(self, writer: Writer) -> None:
        pass


class SlotFilterChain(ABC):
    @abstractmethod
    def setSlotFilter(self, filter: int) -> None:
        pass


class SecondarySelectorChain(ABC):
    def getBandwidth(self) -> float:
        pass


class DeemphasisTauChain(ABC):
    @abstractmethod
    def setDeemphasisTau(self, tau: float) -> None:
        pass


class RdsChain(ABC):
    @abstractmethod
    def setRdsRbds(self, rdsRbds: bool) -> None:
        pass


class AudioServiceSelector(ABC):
    @abstractmethod
    def setAudioServiceId(self, serviceId: int) -> None:
        pass


class BaseDemodulatorChain(Chain):
    def supportsSquelch(self) -> bool:
        return True

    def setSampleRate(self, sampleRate: int) -> None:
        pass


class SecondaryDemodulator(Chain):
    def supportsSquelch(self) -> bool:
        return True

    def setSampleRate(self, sampleRate: int) -> None:
        pass

    def isSecondaryFftShown(self):
        return True


class ServiceDemodulator(SecondaryDemodulator, FixedAudioRateChain, metaclass=ABCMeta):
    pass


class DemodulatorError(Exception):
    pass
