function Filter(demodulator) {
    this.demodulator = demodulator;
    this.min_passband = 100;
}

Filter.prototype.getLimits = function() {
    var max_bw;
    if (['pocsag', 'packet'].indexOf(this.demodulator.get_secondary_demod()) >= 0) {
        max_bw = 12500;
    } else if (['dmr', 'dstar', 'nxdn', 'ysf', 'm17'].indexOf(this.demodulator.get_modulation()) >= 0) {
        max_bw = 6250;
    } else if (this.demodulator.get_modulation() === 'wfm') {
        max_bw = 100000;
    } else if (this.demodulator.get_modulation() === 'drm') {
        max_bw = 50000;
    } else if (this.demodulator.get_modulation() === "freedv") {
        max_bw = 4000;
    } else if (this.demodulator.get_secondary_demod() === "ism") {
        max_bw = 600000;
    } else {
        max_bw = (audioEngine.getOutputRate() / 2) - 1;
    }
    return {
        high: max_bw,
        low: -max_bw
    };
};

function Envelope(demodulator) {
    this.demodulator = demodulator;
    this.dragged_range = Demodulator.draggable_ranges.none;
}

Envelope.prototype.draw = function(visible_range){
    this.visible_range = visible_range;
    var line = center_freq + this.demodulator.offset_frequency;

    //                                               ____
    // Draws a standard filter envelope like this: _/    \_
    // Parameters are given in offset frequency (Hz).
    // Envelope is drawn on the scale canvas.
    // A "drag range" object is returned, containing information about the draggable areas of the envelope
    // (beginning, ending and the line showing the offset frequency).
    var env_bounding_line_w = 5;   //
    var env_att_w = 5;             //     _______   ___env_h2 in px   ___|_____
    var env_h1 = 17;               //   _/|      \_ ___env_h1 in px _/   |_    \_
    var env_h2 = 5;                //   |||env_att_line_w                |_env_lineplus
    var env_lineplus = 1;          //   ||env_bounding_line_w
    var env_line_click_area = 6;
    //range=get_visible_freq_range();

    var from = center_freq + this.demodulator.offset_frequency;
    var to = center_freq + this.demodulator.offset_frequency;
    var fake_indicator = typeof(this.demodulator.low_cut) !== 'number' || typeof(this.demodulator.high_cut) !== 'number';
    if (fake_indicator) {
        // fake values just so that the tuning indicator shows up
        var fixedBw = 100000
        // if we know the if rate, we can display that
        if (this.demodulator.ifRate) {
            fixedBw = this.demodulator.ifRate / 2;
        }
        from -= fixedBw;
        to += fixedBw;
    } else {
        from += this.demodulator.low_cut;
        to += this.demodulator.high_cut;
    }
    var from_px = scale_px_from_freq(from, range);
    var to_px = scale_px_from_freq(to, range);
    if (to_px < from_px) /* swap'em */ {
        var temp_px = to_px;
        to_px = from_px;
        from_px = temp_px;
    }

    from_px -= (env_att_w + env_bounding_line_w);
    to_px += (env_att_w + env_bounding_line_w);
    // do drawing:
    var color = this.color || '#ffff00'; // yellow
    scale_ctx.strokeStyle = color;
    scale_ctx.fillStyle = color;
    var drag_ranges = {envelope_on_screen: false, line_on_screen: false};
    if (!(to_px < 0 || from_px > window.innerWidth)) // out of screen?
    {
        if (fake_indicator) {
            scale_ctx.setLineDash([10, 5]);
        } else {
            drag_ranges.beginning = {x1: from_px, x2: from_px + env_bounding_line_w + env_att_w};
            drag_ranges.ending = {x1: to_px - env_bounding_line_w - env_att_w, x2: to_px};
            drag_ranges.whole_envelope = {x1: from_px, x2: to_px};
            drag_ranges.envelope_on_screen = true;
        }

        scale_ctx.beginPath();
        scale_ctx.lineWidth = 3;

        scale_ctx.moveTo(from_px, env_h1);
        scale_ctx.lineTo(from_px + env_bounding_line_w, env_h1);
        scale_ctx.lineTo(from_px + env_bounding_line_w + env_att_w, env_h2);
        scale_ctx.lineTo(to_px - env_bounding_line_w - env_att_w, env_h2);
        scale_ctx.lineTo(to_px - env_bounding_line_w, env_h1);
        scale_ctx.lineTo(to_px, env_h1);
        scale_ctx.globalAlpha = 0.3;
        scale_ctx.fill();
        scale_ctx.globalAlpha = 1;
        scale_ctx.stroke();
        scale_ctx.setLineDash([]);

        scale_ctx.lineWidth = 1;
        scale_ctx.font = "bold 11px sans-serif";
        scale_ctx.textBaseline = "top";
        scale_ctx.textAlign = "left";
        if (typeof(this.demodulator.high_cut) === 'number') {
            scale_ctx.fillText(this.demodulator.high_cut.toString(), to_px + env_att_w, env_h2);
        }
        scale_ctx.textAlign = "right";
        if (typeof(this.demodulator.low_cut) === 'number') {
            scale_ctx.fillText(this.demodulator.low_cut.toString(), from_px - env_att_w, env_h2);
        }
    }
    if (typeof line !== "undefined") // out of screen?
    {
        var line_px = scale_px_from_freq(line, range);
        if (!(line_px < 0 || line_px > window.innerWidth)) {
            drag_ranges.line = {x1: line_px - env_line_click_area / 2, x2: line_px + env_line_click_area / 2};
            drag_ranges.line_on_screen = true;
            scale_ctx.beginPath();
            scale_ctx.moveTo(line_px, env_h1 + env_lineplus);
            scale_ctx.lineTo(line_px, env_h2 - env_lineplus);
            scale_ctx.lineWidth = 3;
            scale_ctx.stroke();
        }
    }
    this.drag_ranges = drag_ranges;
};

Envelope.prototype.drag_start = function(x, key_modifiers){
    this.key_modifiers = key_modifiers;
    this.dragged_range = this.where_clicked(x, this.drag_ranges, key_modifiers);
    this.drag_origin = {
        x: x,
        low_cut: this.demodulator.low_cut,
        high_cut: this.demodulator.high_cut,
        offset_frequency: this.demodulator.offset_frequency
    };
    return this.dragged_range !== Demodulator.draggable_ranges.none;
};

Envelope.prototype.where_clicked = function(x, drag_ranges, key_modifiers) {  // Check exactly what the user has clicked based on ranges returned by envelope_draw().
    var in_range = function (x, range) {
        return range.x1 <= x && range.x2 >= x;
    };
    var dr = Demodulator.draggable_ranges;

    if (key_modifiers.shiftKey) {
        //Check first: shift + center drag emulates BFO knob
        if (drag_ranges.line_on_screen && in_range(x, drag_ranges.line)) return dr.bfo;
        //Check second: shift + envelope drag emulates PBF knob
        if (drag_ranges.envelope_on_screen && in_range(x, drag_ranges.whole_envelope)) return dr.pbs;
    }
    if (drag_ranges.envelope_on_screen) {
        // For low and high cut:
        if (in_range(x, drag_ranges.beginning)) return dr.beginning;
        if (in_range(x, drag_ranges.ending)) return dr.ending;
        // Last priority: having clicked anything else on the envelope, without holding the shift key
        if (in_range(x, drag_ranges.whole_envelope)) return dr.anything_else;
    }
    return dr.none; //User doesn't drag the envelope for this demodulator
};


Envelope.prototype.drag_move = function(x) {
    var dr = Demodulator.draggable_ranges;
    var new_value;
    if (this.dragged_range === dr.none) return false; // we return if user is not dragging (us) at all
    var freq_change = Math.round(this.visible_range.hps * (x - this.drag_origin.x));

    //dragging the line in the middle of the filter envelope while holding Shift does emulate
    //the BFO knob on radio equipment: moving offset frequency, while passband remains unchanged
    //Filter passband moves in the opposite direction than dragged, hence the minus below.
    var minus = (this.dragged_range === dr.bfo) ? -1 : 1;
    //dragging any other parts of the filter envelope while holding Shift does emulate the PBS knob
    //(PassBand Shift) on radio equipment: PBS does move the whole passband without moving the offset
    //frequency.
    if (this.dragged_range === dr.beginning || this.dragged_range === dr.bfo || this.dragged_range === dr.pbs) {
        //we don't let low_cut go beyond its limits
        if ((new_value = this.drag_origin.low_cut + minus * freq_change) < this.demodulator.filter.getLimits().low) {
            new_value = this.demodulator.filter.getLimits().low;
        }
        //nor the filter passband be too small
        if (this.demodulator.high_cut - new_value < this.demodulator.filter.min_passband) {
            new_value = this.demodulator.high_cut - this.demodulator.filter.min_passband;
        }
        //sanity check to prevent GNU Radio "firdes check failed: fa <= fb"
        if (new_value >= this.demodulator.high_cut) return true;
        this.demodulator.setLowCut(new_value);
    }
    if (this.dragged_range === dr.ending || this.dragged_range === dr.bfo || this.dragged_range === dr.pbs) {
        //we don't let high_cut go beyond its limits
        if ((new_value = this.drag_origin.high_cut + minus * freq_change) > this.demodulator.filter.getLimits().high) {
            new_value = this.demodulator.filter.getLimits().high;
        }
        //nor the filter passband be too small
        if (new_value - this.demodulator.low_cut < this.demodulator.filter.min_passband) {
            new_value = this.demodulator.low_cut + this.demodulator.filter.min_passband;
        }
        //sanity check to prevent GNU Radio "firdes check failed: fa <= fb"
        if (new_value <= this.demodulator.low_cut) return true;
        this.demodulator.setHighCut(new_value);
    }
    if (this.dragged_range === dr.anything_else || this.dragged_range === dr.bfo) {
        //when any other part of the envelope is dragged, the offset frequency is changed (whole passband also moves with it)
        new_value = this.drag_origin.offset_frequency + freq_change;
        if (new_value > bandwidth / 2 || new_value < -bandwidth / 2) return true; //we don't allow tuning above Nyquist frequency :-)
        this.demodulator.set_offset_frequency(new_value);
    }
    //now do the actual modifications:
    //mkenvelopes(this.visible_range);
    //this.demodulator.set();
    return true;
};

Envelope.prototype.drag_end = function(){
    var to_return = this.dragged_range !== Demodulator.draggable_ranges.none; //this part is required for cliking anywhere on the scale to set offset
    this.dragged_range = Demodulator.draggable_ranges.none;
    return to_return;
};


//******* class Demodulator_default_analog *******
// This can be used as a base for basic audio demodulators.
// It already supports most basic modulations used for ham radio and commercial services: AM/FM/LSB/USB

function Demodulator(offset_frequency, modulation) {
    this.offset_frequency = offset_frequency;
    this.envelope = new Envelope(this);
    this.color = Demodulator.get_next_color();
    this.modulation = modulation;
    this.filter = new Filter(this);
    this.squelch_level = -150;
    this.dmr_filter = 3;
    this.audio_service_id = 0;
    this.started = false;
    this.state = {};
    this.secondary_demod = false;
    var mode = Modes.findByModulation(modulation);
    this.low_cut = mode && mode.bandpass && mode.bandpass.low_cut || null;
    this.high_cut = mode && mode.bandpass && mode.bandpass.high_cut || null;
    this.ifRate = mode && mode.ifRate;
    this.listeners = {
        "frequencychange": [],
        "squelchchange": []
    };
}

//ranges on filter envelope that can be dragged:
Demodulator.draggable_ranges = {
    none: 0,
    beginning: 1 /*from*/,
    ending: 2 /*to*/,
    anything_else: 3,
    bfo: 4 /*line (while holding shift)*/,
    pbs: 5
}; //to which parameter these correspond in envelope_draw()

Demodulator.color_index = 0;
Demodulator.colors = ["#ffff00", "#00ff00", "#00ffff", "#058cff", "#ff9600", "#a1ff39", "#ff4e39", "#ff5dbd"];

Demodulator.get_next_color = function() {
    if (this.color_index >= this.colors.length) this.color_index = 0;
    return (this.colors[this.color_index++]);
}



Demodulator.prototype.on = function(event, handler) {
    this.listeners[event].push(handler);
};

Demodulator.prototype.emit = function(event, params) {
    this.listeners[event].forEach(function(fn) {
        fn(params);
    });
};

Demodulator.prototype.set_offset_frequency = function(to_what) {
    if (typeof(to_what) == 'undefined' || to_what > bandwidth / 2 || to_what < -bandwidth / 2) return;
    to_what = Math.round(to_what);
    if (this.offset_frequency === to_what) {
        return;
    }
    this.offset_frequency = to_what;
    this.set();
    this.emit("frequencychange", to_what);
    mkenvelopes(get_visible_freq_range());
};

Demodulator.prototype.get_offset_frequency = function() {
    return this.offset_frequency;
};

Demodulator.prototype.get_modulation = function() {
    return this.modulation;
};

Demodulator.prototype.start = function() {
    this.started = true;
    this.set();
    ws.send(JSON.stringify({
        "type": "dspcontrol",
        "action": "start"
    }));
};

// TODO check if this is actually used
Demodulator.prototype.stop = function() {
};

Demodulator.prototype.send = function(params) {
    ws.send(JSON.stringify({"type": "dspcontrol", "params": params}));
}

Demodulator.prototype.set = function () {  //this function sends demodulator parameters to the server
    if (!this.started) return;
    var params = {
        "low_cut": this.low_cut,
        "high_cut": this.high_cut,
        "offset_freq": this.offset_frequency,
        "mod": this.modulation,
        "dmr_filter": this.dmr_filter,
        "audio_service_id": this.audio_service_id,
        "squelch_level": this.squelch_level,
        "secondary_mod": this.secondary_demod,
        "secondary_offset_freq": this.secondary_offset_freq
    };
    var to_send = {};
    for (var key in params) {
        if (!(key in this.state) || params[key] !== this.state[key]) {
            to_send[key] = params[key];
        }
    }
    if (Object.keys(to_send).length > 0) {
        this.send(to_send);
        for (var key in to_send) {
            this.state[key] = to_send[key];
        }
    }
    mkenvelopes(get_visible_freq_range());
};

Demodulator.prototype.setSquelch = function(squelch) {
    if (this.squelch_level == squelch) {
        return;
    }
    this.squelch_level = squelch;
    this.set();
    this.emit("squelchchange", squelch);
};

Demodulator.prototype.getSquelch = function() {
    return this.squelch_level;
};

Demodulator.prototype.setDmrFilter = function(dmr_filter) {
    this.dmr_filter = dmr_filter;
    this.set();
};

Demodulator.prototype.setAudioServiceId = function(audio_service_id) {
    this.audio_service_id = audio_service_id;
    this.set();
}

Demodulator.prototype.setBandpass = function(bandpass) {
    this.bandpass = bandpass;
    this.low_cut = bandpass.low_cut;
    this.high_cut = bandpass.high_cut;
    this.set();
};

Demodulator.prototype.disableBandpass = function() {
    delete this.bandpass;
    this.low_cut = null;
    this.high_cut = null;
    this.set()
}

Demodulator.prototype.setLowCut = function(low_cut) {
    this.low_cut = low_cut;
    this.set();
};

Demodulator.prototype.setHighCut = function(high_cut) {
    this.high_cut = high_cut;
    this.set();
};

Demodulator.prototype.getBandpass = function() {
    return {
        low_cut: this.low_cut,
        high_cut: this.high_cut
    };
};

Demodulator.prototype.setIfRate = function(ifRate) {
    this.ifRate = ifRate;
};

Demodulator.prototype.set_secondary_demod = function(secondary_demod) {
    if (this.secondary_demod === secondary_demod) {
        return;
    }
    this.secondary_demod = secondary_demod;
    this.set();
};

Demodulator.prototype.get_secondary_demod = function() {
    return this.secondary_demod;
};

Demodulator.prototype.set_secondary_offset_freq = function(secondary_offset) {
    if (this.secondary_offset_freq === secondary_offset) {
        return;
    }
    this.secondary_offset_freq = secondary_offset;
    this.set();
};
