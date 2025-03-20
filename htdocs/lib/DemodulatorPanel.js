function DemodulatorPanel(el) {
    var self = this;
    self.el = el;
    self.demodulator = null;
    self.mode = null;
    self.squelchMargin = 10;
    self.initialParams = {};

    var displayEl = el.find('.webrx-actual-freq')
    this.tuneableFrequencyDisplay = displayEl.tuneableFrequencyDisplay();
    displayEl.on('frequencychange', function(event, freq) {
        self.getDemodulator().set_offset_frequency(freq - self.center_freq);
    });

    this.mouseFrequencyDisplay = el.find('.webrx-mouse-freq').frequencyDisplay();

    Modes.registerModePanel(this);
    el.on('click', '.openwebrx-demodulator-button', function() {
        var modulation = $(this).data('modulation');
        if (modulation) {
            if (self.mode && self.mode.type === 'digimode' && self.mode.underlying.indexOf(modulation) >= 0) {
                // keep the mode, just switch underlying modulation
                self.setMode(self.mode.modulation, modulation)
            } else {
                self.setMode(modulation);
            }
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
    el.on('click', '.openwebrx-squelch-auto', function() {
        if (!self.squelchAvailable()) return;
        el.find('.openwebrx-squelch-slider').val(getLogSmeterValue(smeter_level) + self.getSquelchMargin());
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

    var $modegrid = $('<div class="openwebrx-modes-grid"></div>');
    $modegrid.append.apply($modegrid, buttons);
    html.push($modegrid);

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

DemodulatorPanel.prototype.setMode = function(requestedModulation, underlyingModulation) {
    var mode = Modes.findByModulation(requestedModulation);
    if (!mode) {
        return;
    }

    if (this.mode === mode && this.underlyingModulation === underlyingModulation) {
        return;
    }
    if (!mode.isAvailable()) {
        divlog('Modulation "' + mode.name + '" not supported. Please check the feature report', true);
        return;
    }

    var modulation;
    if (mode.type === 'digimode') {
        modulation = underlyingModulation = underlyingModulation || mode.underlying[0];
    } else {
        underlyingModulation = undefined;
        modulation = mode.modulation;
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
        self.el.find('.openwebrx-squelch-slider')
            .val(squelch)
            .attr('title', 'Squelch (' + squelch + ' dB)');
        self.updateHash();
    };
    this.demodulator.on('squelchchange', updateSquelch);
    updateSquelch(this.demodulator.getSquelch());

    if (mode.type === 'digimode') {
        this.demodulator.set_secondary_demod(mode.modulation);
        var uMode = Modes.findByModulation(underlyingModulation);
        var bandpass = mode.bandpass || (uMode && uMode.bandpass);
        if (bandpass) {
            this.demodulator.setBandpass(bandpass);
        } else {
            this.demodulator.disableBandpass();
        }
        var ifRate = mode.ifRate || (uMode && uMode.ifRate);
        this.demodulator.setIfRate(ifRate);
    } else {
        this.demodulator.set_secondary_demod(false);
    }

    this.demodulator.start();
    this.mode = mode;
    this.underlyingModulation = underlyingModulation;

    this.updateButtons();
    this.updatePanels();
    this.updateHash();
};

DemodulatorPanel.prototype.disableDigiMode = function() {
    this.setMode(this.getDemodulator().get_modulation());
};

DemodulatorPanel.prototype.updatePanels = function() {
    var modulation = this.getDemodulator().get_secondary_demod();
    $('#openwebrx-panel-digimodes').attr('data-mode', modulation);
    var mode = Modes.findByModulation(modulation);
    toggle_panel("openwebrx-panel-digimodes", modulation && (!mode || mode.secondaryFft));
    // WSJT-X modes share the same panel
    toggle_panel("openwebrx-panel-wsjt-message", ['ft8', 'wspr', 'jt65', 'jt9', 'jt4', 'ft4', 'fst4', 'fst4w', "q65", "msk144"].indexOf(modulation) >= 0);
    // these modes come with their own
    ['js8', 'packet', 'pocsag', 'adsb', 'ism', 'hfdl', 'vdl2'].forEach(function(m) {
        toggle_panel('openwebrx-panel-' + m + '-message', modulation === m);
    });

    modulation = this.getDemodulator().get_modulation();
    var showing = 'openwebrx-panel-metadata-' + modulation;
    var metaPanels = $(".openwebrx-meta-panel");
    metaPanels.each(function (_, p) {
        toggle_panel(p.id, p.id === showing && !p.classList.contains('disabled'));
    });
    metaPanels.metaPanel().each(function() {
        this.clear();
    });
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
    return $.extend(new Object(), defaults, this.validateInitialParams(this.initialParams), this.transformHashParams(this.parseHash()));
};

DemodulatorPanel.prototype.startDemodulator = function() {
    if (!Modes.initComplete() || !this.center_freq) return;
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
    if (params.secondary_mod) {
        this.setMode(params.secondary_mod, params.mod)
    } else {
        this.setMode(params.mod);
    }
    this.getDemodulator().set_offset_frequency(params.offset_frequency);
    this.getDemodulator().setSquelch(params.squelch_level);
    this.updateButtons();
};

DemodulatorPanel.prototype.setInitialParams = function(params) {
    $.extend(this.initialParams, params);
};

DemodulatorPanel.prototype.resetInitialParams = function() {
    this.initialParams = {};
};

DemodulatorPanel.prototype.onHashChange = function() {
    this._apply(this.transformHashParams(this.parseHash()));
};

DemodulatorPanel.prototype.transformHashParams = function(params) {
    var ret = {
        mod: params.mod
    };
    if (typeof(params.secondary_mod) !== 'undefined') ret.secondary_mod = params.secondary_mod;
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
    this.el.find('.openwebrx-squelch-auto')[squelch_disabled ? 'addClass' : 'removeClass']('disabled');
}

DemodulatorPanel.prototype.setCenterFrequency = function(center_freq) {
    var me = this;
    if (me.centerFreqTimeout) {
        clearTimeout(me.centerFreqTimeout);
        me.centerFreqTimeout = false;
    }
    this.centerFreqTimeout = setTimeout(function() {
        me.stopDemodulator();
        me.center_freq = center_freq;
        me.startDemodulator();
        me.centerFreqTimeout = false;
    }, 50);
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
            return params.freq && Math.abs(params.freq - self.center_freq) <= bandwidth / 2;
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

DemodulatorPanel.prototype.validateInitialParams = function(params) {
    return Object.fromEntries(
        Object.entries(params).filter(function(a) {
            if (a[0] == "offset_frequency") {
                return Math.abs(a[1]) <= bandwidth / 2;
            }
            return true;
        })
    );
};

DemodulatorPanel.prototype.updateHash = function() {
    var demod = this.getDemodulator();
    if (!demod) return;
    var self = this;
    window.location.hash = $.map({
        freq: demod.get_offset_frequency() + self.center_freq,
        mod: demod.get_modulation(),
        secondary_mod: demod.get_secondary_demod(),
        sql: demod.getSquelch()
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

DemodulatorPanel.prototype.setSquelchMargin = function(margin) {
    if (typeof(margin) === 'undefined' || this.squelchMargin == margin) return;
    this.squelchMargin = margin;
};

DemodulatorPanel.prototype.getSquelchMargin = function() {
    return this.squelchMargin;
};

DemodulatorPanel.prototype.setMouseFrequency = function(freq) {
    this.mouseFrequencyDisplay.setFrequency(freq);
};

DemodulatorPanel.prototype.setTuningPrecision = function(precision) {
    this.tuneableFrequencyDisplay.setTuningPrecision(precision);
    this.mouseFrequencyDisplay.setTuningPrecision(precision);
};

$.fn.demodulatorPanel = function(){
    if (!this.data('panel')) {
        this.data('panel', new DemodulatorPanel(this));
    }
    return this.data('panel');
};
