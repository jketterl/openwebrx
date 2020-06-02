function DemodulatorPanel(el) {
    var self = this;
    self.el = el;
    self.demodulator = null;
    self.mode = null;

    var displayEl = el.find('.webrx-actual-freq')
    this.tuneableFrequencyDisplay = displayEl.tuneableFrequencyDisplay();
    displayEl.on('frequencychange', function(event, freq) {
        self.getDemodulator().set_offset_frequency(freq - self.center_freq);
    });

    Modes.registerModePanel(this);
    el.on('click', '.openwebrx-demodulator-button', function() {
        var modulation = $(this).data('modulation');
        if (modulation) {
            self.setMode(modulation);
        } else {
            self.disableDigiMode();
        }
    });
    el.on('change', '.openwebrx-secondary-demod-listbox', function() {
        var value = $(this).val();
        if (value === 'none') {
            self.disableDigiMode();
        } else {
            self.setMode(value);
        }
    });
    el.on('click', '.openwebrx-squelch-default', function() {
        if (!self.squelchAvailable()) return;
        el.find('.openwebrx-squelch-slider').val(getLogSmeterValue(smeter_level) + 10);
        self.updateSquelch();
    });
    el.on('change', '.openwebrx-squelch-slider', function() {
        self.updateSquelch();
    });
    window.addEventListener('hashchange', function() {
        self.onHashChange();
    });
};

DemodulatorPanel.prototype.render = function() {
    var available = Modes.getModes().filter(function(m){ return m.isAvailable(); });
    var normalModes = available.filter(function(m){ return m.type === 'analog'; });
    var digiModes = available.filter(function(m){ return m.type === 'digimode'; });

    var html = []

    var buttons = normalModes.map(function(m){
        return $(
            '<div ' +
                'class="openwebrx-button openwebrx-demodulator-button" ' +
                'data-modulation="' + m.modulation + '" ' +
                'id="openwebrx-button-' + m.modulation + '" r' +
            '>' + m.name + '</div>'
        );
    });

    var index = 0;
    var arrayLength = buttons.length;
    var chunks = [];

    for (index = 0; index < arrayLength; index += 5) {
        chunks.push(buttons.slice(index, index + 5));
    }

    html.push.apply(html, chunks.map(function(chunk){
        $line = $('<div class="openwebrx-panel-line openwebrx-panel-flex-line"></div>');
        $line.append.apply($line, chunk);
        return $line
    }));

    html.push($(
        '<div class="openwebrx-panel-line openwebrx-panel-flex-line">' +
            '<div class="openwebrx-button openwebrx-demodulator-button openwebrx-button-dig">DIG</div>' +
            '<select class="openwebrx-secondary-demod-listbox">' +
                '<option value="none"></option>' +
                digiModes.map(function(m){
                    return '<option value="' + m.modulation + '">' + m.name + '</option>';
                }).join('') +
            '</select>' +
        '</div>'
    ));

    this.el.find(".openwebrx-modes").html(html);
};

DemodulatorPanel.prototype.setMode = function(requestedModulation) {
    var mode = Modes.findByModulation(requestedModulation);
    if (!mode) {
        return;
    }
    if (this.mode === mode) {
        return;
    }
    if (!mode.isAvailable()) {
        divlog('Modulation "' + mode.name + '" not supported. Please check requirements', true);
        return;
    }

    if (mode.type === 'digimode') {
        modulation = mode.underlying[0];
    } else {
        if (this.mode && this.mode.type === 'digimode' && this.mode.underlying.indexOf(requestedModulation) >= 0) {
            // keep the mode, just switch underlying modulation
            mode = this.mode;
            modulation = requestedModulation;
        } else {
            modulation = mode.modulation;
        }
    }

    var current = this.collectParams();
    if (this.demodulator) {
        current.offset_frequency = this.demodulator.get_offset_frequency();
        current.squelch_level = this.demodulator.getSquelch();
    }

    this.stopDemodulator();
    this.demodulator = new Demodulator(current.offset_frequency, modulation);
    this.demodulator.setSquelch(current.squelch_level);

    var self = this;
    var updateFrequency = function(freq) {
        self.tuneableFrequencyDisplay.setFrequency(self.center_freq + freq);
        self.updateHash();
    };
    this.demodulator.on("frequencychange", updateFrequency);
    updateFrequency(this.demodulator.get_offset_frequency());
    var updateSquelch = function(squelch) {
        self.el.find('.openwebrx-squelch-slider').val(squelch);
        self.updateHash();
    };
    this.demodulator.on('squelchchange', updateSquelch);
    updateSquelch(this.demodulator.getSquelch());

    if (mode.type === 'digimode') {
        this.demodulator.set_secondary_demod(mode.modulation);
        if (mode.bandpass) {
            this.demodulator.setBandpass(mode.bandpass);
        }
    } else {
        this.demodulator.set_secondary_demod(false);
    }

    this.demodulator.start();
    this.mode = mode;

    this.updateButtons();
    this.updatePanels();
    this.updateHash();
};

DemodulatorPanel.prototype.disableDigiMode = function() {
    // just a little trick to get out of the digimode
    delete this.mode;
    this.setMode(this.getDemodulator().get_modulation());
};

DemodulatorPanel.prototype.updatePanels = function() {
    var modulation = this.getDemodulator().get_secondary_demod();
    $('#openwebrx-panel-digimodes').attr('data-mode', modulation);
    toggle_panel("openwebrx-panel-digimodes", !!modulation);
    toggle_panel("openwebrx-panel-wsjt-message", ['ft8', 'wspr', 'jt65', 'jt9', 'ft4'].indexOf(modulation) >= 0);
    toggle_panel("openwebrx-panel-js8-message", modulation == "js8");
    toggle_panel("openwebrx-panel-packet-message", modulation === "packet");
    toggle_panel("openwebrx-panel-pocsag-message", modulation === "pocsag");

    modulation = this.getDemodulator().get_modulation();
    var showing = 'openwebrx-panel-metadata-' + modulation;
    $(".openwebrx-meta-panel").each(function (_, p) {
        toggle_panel(p.id, p.id === showing);
    });
    clear_metadata();
};

DemodulatorPanel.prototype.getDemodulator = function() {
    return this.demodulator;
};

DemodulatorPanel.prototype.collectParams = function() {
    var defaults = {
        offset_frequency: 0,
        squelch_level: -150,
        mod: 'nfm'
    }
    return $.extend(new Object(), defaults, this.initialParams || {}, this.transformHashParams(this.parseHash()));
};

DemodulatorPanel.prototype.startDemodulator = function() {
    if (!Modes.initComplete()) return;
    var params = this.collectParams();
    this._apply(params);
};

DemodulatorPanel.prototype.stopDemodulator = function() {
    if (!this.demodulator) {
        return;
    }
    this.demodulator.stop();
    this.demodulator = null;
    this.mode = null;
}

DemodulatorPanel.prototype._apply = function(params) {
    this.setMode(params.mod);
    this.getDemodulator().set_offset_frequency(params.offset_frequency);
    this.getDemodulator().setSquelch(params.squelch_level);
    this.updateButtons();
};

DemodulatorPanel.prototype.setInitialParams = function(params) {
    this.initialParams = params;
};

DemodulatorPanel.prototype.onHashChange = function() {
    this._apply(this.transformHashParams(this.parseHash()));
};

DemodulatorPanel.prototype.transformHashParams = function(params) {
    var ret = {
        mod: params.secondary_mod || params.mod
    };
    if (typeof(params.offset_frequency) !== 'undefined') ret.offset_frequency = params.offset_frequency;
    if (typeof(params.sql) !== 'undefined') ret.squelch_level = parseInt(params.sql);
    return ret;
};

DemodulatorPanel.prototype.squelchAvailable = function () {
    return this.mode && this.mode.squelch;
}

DemodulatorPanel.prototype.updateButtons = function() {
    var $buttons = this.el.find(".openwebrx-demodulator-button");
    $buttons.removeClass("highlighted").removeClass('same-mod');
    var demod = this.getDemodulator()
    if (!demod) return;
    this.el.find('[data-modulation=' + demod.get_modulation() + ']').addClass("highlighted");
    var secondary_demod = demod.get_secondary_demod()
    if (secondary_demod) {
        this.el.find(".openwebrx-button-dig").addClass("highlighted");
        this.el.find('.openwebrx-secondary-demod-listbox').val(secondary_demod);
        var mode = Modes.findByModulation(secondary_demod);
        if (mode) {
            var self = this;
            mode.underlying.filter(function(m) {
                return m !== demod.get_modulation();
            }).forEach(function(m) {
                self.el.find('[data-modulation=' + m + ']').addClass('same-mod')
            });
        }
    } else {
        this.el.find('.openwebrx-secondary-demod-listbox').val('none');
    }
    var squelch_disabled = !this.squelchAvailable();
    this.el.find('.openwebrx-squelch-slider').prop('disabled', squelch_disabled);
    this.el.find('.openwebrx-squelch-default')[squelch_disabled ? 'addClass' : 'removeClass']('disabled');
}

DemodulatorPanel.prototype.setCenterFrequency = function(center_freq) {
    if (this.center_freq === center_freq) {
        return;
    }
    this.stopDemodulator();
    this.center_freq = center_freq;
    this.startDemodulator();
};

DemodulatorPanel.prototype.parseHash = function() {
    if (!window.location.hash) {
        return {};
    }
    var params = window.location.hash.substring(1).split(",").map(function(x) {
        var harr = x.split('=');
        return [harr[0], harr.slice(1).join('=')];
    }).reduce(function(params, p){
        params[p[0]] = p[1];
        return params;
    }, {});

    return this.validateHash(params);
};

DemodulatorPanel.prototype.validateHash = function(params) {
    var self = this;
    params = Object.keys(params).filter(function(key) {
        if (key == 'freq' || key == 'mod' || key == 'secondary_mod' || key == 'sql') {
            return params.freq && Math.abs(params.freq - self.center_freq) < bandwidth;
        }
        return true;
    }).reduce(function(p, key) {
        p[key] = params[key];
        return p;
    }, {});

    if (params['freq']) {
        params['offset_frequency'] = params['freq'] - self.center_freq;
        delete params['freq'];
    }

    return params;
};

DemodulatorPanel.prototype.updateHash = function() {
    var demod = this.getDemodulator();
    if (!demod) return;
    var self = this;
    window.location.hash = $.map({
        freq: demod.get_offset_frequency() + self.center_freq,
        mod: demod.get_modulation(),
        secondary_mod: demod.get_secondary_demod(),
        sql: demod.getSquelch(),
    }, function(value, key){
        if (typeof(value) === 'undefined' || value === false) return undefined;
        return key + '=' + value;
    }).filter(function(v) {
        return !!v;
    }).join(',');
};

DemodulatorPanel.prototype.updateSquelch = function() {
    var sliderValue = parseInt(this.el.find(".openwebrx-squelch-slider").val());
    var demod = this.getDemodulator();
    if (demod) demod.setSquelch(sliderValue);
};

$.fn.demodulatorPanel = function(){
    if (!this.data('panel')) {
        this.data('panel', new DemodulatorPanel(this));
    };
    return this.data('panel');
};