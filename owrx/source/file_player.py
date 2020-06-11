from .direct import DirectSource

class FilePlayerSource(DirectSource):
    def getCommandMapper(self):
        cmd = "(while true; do xzcat {p[file]}; done) | csdr flowcontrol $(csdr ={p[samp_rate]}*{p[bytes_per_sample]}*1.05) 20 | {p[format_conversion]}"
        return super().getCommandMapper().setBase(cmd)

    def getEventNames(self):
        return super().getEventNames() + ["file", "bytes_per_sample", "format_conversion"]
