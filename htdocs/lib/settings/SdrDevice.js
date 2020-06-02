function SdrDevice(el, data) {
    this.el = el;
    this.data = data;
    this.inputs = {};
    this.render();

    var self = this;
    el.on('click', '.fieldselector .btn', function() {
        var key = el.find('.fieldselector select').val();
        self.data[key] = self.getInitialValue(key);
        self.render();
    });
};

SdrDevice.create = function(el) {
    var data = JSON.parse(decodeURIComponent(el.data('config')));
    var type = data.type;
    var constructor = SdrDevice.types[type] || SdrDevice;
    return new constructor(el, data);
};

SdrDevice.prototype.getData = function() {
    return $.extend(new Object(), this.getDefaults(), this.data);
};

SdrDevice.prototype.getDefaults = function() {
    var defaults = {}
    $.each(this.getMappings(), function(k, v) {
        if (!v.includeInDefault) return;
        defaults[k] = 'initialValue' in v ? v['initialValue'] : false;
    });
    return defaults;
};

SdrDevice.prototype.getMappings = function() {
    return {
        "name": {
            constructor: TextInput,
            inputOptions: {
                label: "Name"
            },
            initialValue: "",
            includeInDefault: true
        },
        "type": {
            constructor: TextInput,
            inputOptions: {
                label: "Type"
            },
            initialValue: '',
            includeInDefault: true
        },
        "ppm": {
            constructor: NumberInput,
            inputOptions: {
                label: "PPM"
            },
            initialValue: 0
        },
        "profiles": {
            constructor: ProfileInput,
            inputOptions: {
                label: "Profiles"
            },
            initialValue: [],
            includeInDefault: true,
            position: 100
        },
        "scheduler": {
            constructor: SchedulerInput,
            inputOptions: {
                label: "Scheduler",
            },
            initialValue: {},
            position: 101
        },
        "rf_gain": {
            constructor: TextInput,
            inputOptions: {
                label: "Gain",
            },
            initialValue: 0
        }
    };
};

SdrDevice.prototype.getMapping = function(key) {
    var mappings = this.getMappings();
    return mappings[key];
};

SdrDevice.prototype.getInputClass = function(key) {
    var mapping = this.getMapping(key);
    return mapping && mapping.constructor || TextInput;
};

SdrDevice.prototype.getInitialValue = function(key) {
    var mapping = this.getMapping(key);
    return mapping && ('initialValue' in mapping) ? mapping['initialValue'] : false;
};

SdrDevice.prototype.getPosition = function(key) {
    var mapping = this.getMapping(key);
    return mapping && mapping.position || 10;
};

SdrDevice.prototype.getInputOptions = function(key) {
    var mapping = this.getMapping(key);
    return mapping && mapping.inputOptions || {};
};

SdrDevice.prototype.getLabel = function(key) {
    var options = this.getInputOptions(key);
    return options && options.label || key;
};

SdrDevice.prototype.render = function() {
    var self = this;
    self.el.empty();
    var data = this.getData();
    Object.keys(data).sort(function(a, b){
        return self.getPosition(a) - self.getPosition(b);
    }).forEach(function(key){
        var value = data[key];
        var inputClass = self.getInputClass(key);
        var input = new inputClass(key, value, self.getInputOptions(key));
        self.inputs[key] = input;
        self.el.append(input.render());
    });
    self.el.append(this.renderFieldSelector());
};

SdrDevice.prototype.renderFieldSelector = function() {
    var self = this;
    return '<div class="fieldselector">' +
        '<h3>Add new configuration options<h3>' +
        '<div class="form-group row">' +
            '<div class="col-3"><select class="form-control form-control-sm">' +
                Object.keys(self.getMappings()).filter(function(m){
                    return !(m in self.data);
                }).map(function(m) {
                    return '<option value="' + m + '">' + self.getLabel(m) + '</option>';
                }).join('') +
            '</select></div>' +
            '<div class="col-2">' +
                '<div class="btn btn-primary">Add to config</div>' +
            '</div>' +
        '</div>' +
    '</div>';
};

RtlSdrDevice = function() {
    SdrDevice.apply(this, arguments);
};

RtlSdrDevice.prototype = Object.create(SdrDevice.prototype);
RtlSdrDevice.prototype.constructor = RtlSdrDevice;

RtlSdrDevice.prototype.getMappings = function() {
    var mappings = SdrDevice.prototype.getMappings.apply(this, arguments);
    return $.extend(new Object(), mappings, {
        "device": {
            constructor: TextInput,
            inputOptions:{
                label: "Serial number"
            },
            initialValue: ""
        }
    });
};

SoapySdrDevice = function() {
    SdrDevice.apply(this, arguments);
};

SoapySdrDevice.prototype = Object.create(SdrDevice.prototype);
SoapySdrDevice.prototype.constructor = SoapySdrDevice;

SoapySdrDevice.prototype.getMappings = function() {
    var mappings = SdrDevice.prototype.getMappings.apply(this, arguments);
    return $.extend(new Object(), mappings, {
        "device": {
            constructor: TextInput,
            inputOptions:{
                label: "Soapy device selector"
            },
            initialValue: ""
        },
        "rf_gain": {
            constructor: SoapyGainInput,
            initialValue: 0,
            inputOptions: {
                label: "Gain",
                gains: this.getGains()
            }
        }
    });
};

SoapySdrDevice.prototype.getGains = function() {
    return [];
};

SdrplaySdrDevice = function() {
    SoapySdrDevice.apply(this, arguments);
};

SdrplaySdrDevice.prototype = Object.create(SoapySdrDevice.prototype);
SdrplaySdrDevice.prototype.constructor = SdrplaySdrDevice;

SdrplaySdrDevice.prototype.getGains = function() {
    return ['RFGR', 'IFGR'];
};

AirspyHfSdrDevice = function() {
    SoapySdrDevice.apply(this, arguments);
};

AirspyHfSdrDevice.prototype = Object.create(SoapySdrDevice.prototype);
AirspyHfSdrDevice.prototype.constructor = AirspyHfSdrDevice;

AirspyHfSdrDevice.prototype.getGains = function() {
    return ['RF', 'VGA'];
};

HackRfSdrDevice = function() {
    SoapySdrDevice.apply(this, arguments);
};

HackRfSdrDevice.prototype = Object.create(SoapySdrDevice.prototype);
HackRfSdrDevice.prototype.constructor = HackRfSdrDevice;

HackRfSdrDevice.prototype.getGains = function() {
    return ['LNA', 'VGA', 'AMP'];
};

SdrDevice.types = {
    'rtl_sdr': RtlSdrDevice,
    'sdrplay': SdrplaySdrDevice,
    'airspyhf': AirspyHfSdrDevice,
    'hackrf': HackRfSdrDevice
};

$.fn.sdrdevice = function() {
    return this.map(function(){
        var el = $(this);
        if (!el.data('sdrdevice')) {
            el.data('sdrdevice', SdrDevice.create(el));
        }
        return el.data('sdrdevice');
    });
};
