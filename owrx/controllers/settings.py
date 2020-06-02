from .admin import AdminController
from owrx.config import Config
from urllib.parse import parse_qs
from owrx.form import (
    TextInput,
    NumberInput,
    FloatInput,
    LocationInput,
    TextAreaInput,
    CheckboxInput,
    DropdownInput,
    Option,
    ServicesCheckboxInput,
    Js8ProfileCheckboxInput,
)
from urllib.parse import quote
import json
import logging

logger = logging.getLogger(__name__)


class Section(object):
    def __init__(self, title, *inputs):
        self.title = title
        self.inputs = inputs

    def render_inputs(self):
        config = Config.get()
        return "".join([i.render(config) for i in self.inputs])

    def render(self):
        return """
            <div class="col-12 settings-category">
                <h3 class="settings-header">
                    {title}
                </h3>
                {inputs}
            </div>
        """.format(
            title=self.title, inputs=self.render_inputs()
        )

    def parse(self, data):
        return {k: v for i in self.inputs for k, v in i.parse(data).items()}


class SettingsController(AdminController):
    def indexAction(self):
        self.serve_template("settings.html", **self.template_variables())


class SdrSettingsController(AdminController):
    def template_variables(self):
        variables = super().template_variables()
        variables["devices"] = self.render_devices()
        return variables

    def render_devices(self):
        return "".join(self.render_device(key, value) for key, value in Config.get()["sdrs"].items())

    def render_device(self, device_id, config):
        return """
            <div class="card device bg-dark text-white">
                <div class="card-header">
                    {device_name}
                </div>
                <div class="card-body">
                    {form}
                </div>
            </div>
        """.format(device_name=config["name"], form=self.render_form(device_id, config))

    def render_form(self, device_id, config):
        return """
            <form class="sdrdevice" data-config="{formdata}"></form>
        """.format(device_id=device_id, formdata=quote(json.dumps(config)))

    def indexAction(self):
        self.serve_template("sdrsettings.html", **self.template_variables())


class GeneralSettingsController(AdminController):
    sections = [
        Section(
            "General settings",
            TextInput("receiver_name", "Receiver name"),
            TextInput("receiver_location", "Receiver location"),
            NumberInput(
                "receiver_asl",
                "Receiver elevation",
                infotext="Elevation in meters above mean see level",
            ),
            TextInput("receiver_admin", "Receiver admin"),
            LocationInput("receiver_gps", "Receiver coordinates"),
            TextInput("photo_title", "Photo title"),
            TextAreaInput("photo_desc", "Photo description"),
        ),
        Section(
            "Waterfall settings",
            NumberInput(
                "fft_fps",
                "FFT frames per second",
                infotext="This setting specifies how many lines are being added to the waterfall per second. "
                + "Higher values will give you a faster waterfall, but will also use more CPU.",
            ),
            NumberInput("fft_size", "FFT size"),
            FloatInput(
                "fft_voverlap_factor",
                "FFT vertical overlap factor",
                infotext="If fft_voverlap_factor is above 0, multiple FFTs will be used for creating a line on the "
                + "diagram.",
            ),
            NumberInput("waterfall_min_level", "Lowest waterfall level"),
            NumberInput("waterfall_max_level", "Highest waterfall level"),
        ),
        Section(
            "Compression",
            DropdownInput(
                "audio_compression",
                "Audio compression",
                options=[Option("adpcm", "ADPCM"), Option("none", "None"),],
            ),
            DropdownInput(
                "fft_compression",
                "Waterfall compression",
                options=[Option("adpcm", "ADPCM"), Option("none", "None"),],
            ),
        ),
        Section(
            "Digimodes",
            CheckboxInput("digimodes_enable", "", checkboxText="Enable Digimodes"),
            NumberInput("digimodes_fft_size", "Digimodes FFT size"),
        ),
        Section(
            "Digital voice",
            NumberInput(
                "digital_voice_unvoiced_quality",
                "Quality of unvoiced sounds in synthesized voice",
                infotext="Determines the quality, and thus the cpu usage, for the ambe codec used by digital voice"
                + "modes.<br />If you're running on a Raspi (up to 3B+) you should leave this set at 1",
            ),
            CheckboxInput(
                "digital_voice_dmr_id_lookup",
                "DMR id lookup",
                checkboxText="Enable lookup of DMR ids in the radioid database to show callsigns and names",
            ),
        ),
        Section(
            "Experimental pipe settings",
            CheckboxInput(
                "csdr_dynamic_bufsize",
                "",
                checkboxText="Enable dynamic buffer sizes",
                infotext="This allows you to change the buffering mode of csdr.",
            ),
            CheckboxInput(
                "csdr_print_bufsizes",
                "",
                checkboxText="Print buffer sizez",
                infotext="This prints the buffer sizes used for csdr processes.",
            ),
            CheckboxInput(
                "csdr_through",
                "",
                checkboxText="Print throughput",
                infotext="Enabling this will print out how much data is going into the DSP chains.",
            ),
        ),
        Section(
            "Map settings",
            TextInput(
                "google_maps_api_key",
                "Google Maps API key",
                infotext="Google Maps requires an API key, check out "
                + '<a href="https://developers.google.com/maps/documentation/embed/get-api-key" target="_blank">'
                + "their documentation</a> on how to obtain one.",
            ),
            NumberInput(
                "map_position_retention_time",
                "Map retention time",
                infotext="Unit is seconds<br/>Specifies how log markers / grids will remain visible on the map",
            ),
        ),
        Section(
            "Decoding settings",
            NumberInput("decoding_queue_workers", "Number of decoding workers"),
            NumberInput("decoding_queue_length", "Maximum length of decoding job queue"),
            NumberInput(
                "wsjt_decoding_depth",
                "Default WSJT decoding depth",
                infotext="A higher decoding depth will allow more results, but will also consume more cpu",
            ),
            NumberInput(
                "js8_decoding_depth",
                "Js8Call decoding depth",
                infotext="A higher decoding depth will allow more results, but will also consume more cpu",
            ),
            Js8ProfileCheckboxInput(
                "js8_enabled_profiles",
                "Js8Call enabled modes"
            ),
        ),
        Section(
            "Background decoding",
            CheckboxInput(
                "services_enabled",
                "Service",
                checkboxText="Enable background decoding services",
            ),
            ServicesCheckboxInput("services_decoders", "Enabled services"),
        ),
        Section(
            "APRS settings",
            TextInput(
                "aprs_callsign",
                "APRS callsign",
                infotext="This callsign will be used to send data to the APRS-IS network",
            ),
            CheckboxInput(
                "aprs_igate_enabled",
                "APRS I-Gate",
                checkboxText="Enable APRS receive-only I-Gate",
            ),
            TextInput("aprs_igate_server", "APRS-IS server"),
            TextInput("aprs_igate_password", "APRS-IS network password"),
            CheckboxInput(
                "aprs_igate_beacon",
                "APRS beacon",
                checkboxText="Send the receiver position to the APRS-IS network",
                infotext="Please check that your receiver location is setup correctly",
            ),
        ),
        Section(
            "pskreporter settings",
            CheckboxInput(
                "pskreporter_enabled",
                "Reporting",
                checkboxText="Enable sending spots to pskreporter.info",
            ),
            TextInput(
                "pskreporter_callsign",
                "pskreporter callsign",
                infotext="This callsign will be used to send spots to pskreporter.info",
            ),
        ),
    ]

    def render_sections(self):
        sections = "".join(section.render() for section in GeneralSettingsController.sections)
        return """
            <form class="settings-body" method="POST">
                {sections}
                <div class="buttons">
                    <button type="submit" class="btn btn-primary">Apply</button>
                </div>
            </form>
        """.format(
            sections=sections
        )

    def indexAction(self):
        self.serve_template("generalsettings.html", **self.template_variables())

    def template_variables(self):
        variables = super().template_variables()
        variables["sections"] = self.render_sections()
        return variables

    def processFormData(self):
        data = parse_qs(self.get_body().decode("utf-8"))
        data = {
            k: v for i in GeneralSettingsController.sections for k, v in i.parse(data).items()
        }
        config = Config.get()
        for k, v in data.items():
            config[k] = v
        Config.store()
        self.send_redirect("/admin")
