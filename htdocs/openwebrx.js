/*

	This file is part of OpenWebRX,
	an open-source SDR receiver software with a web UI.
	Copyright (c) 2013-2015 by Andras Retzler <randras@sdr.hu>
	Copyright (c) 2019 by Jakob Ketterl <dd5jfk@darc.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

*/
var base_url = window.location.origin;
//console.log(base_url);
var act_freq=0;

is_firefox = navigator.userAgent.indexOf("Firefox") >= 0;

var bandwidth;
var center_freq;
var fft_size;
var fft_fps;
var fft_compression = "none";
var fft_codec = new sdrjs.ImaAdpcm();
var waterfall_setup_done = 0;
var secondary_fft_size;
var rx_photo_state = 1;

function e(what) {
    return document.getElementById(what);
}

var rx_photo_height;

function init_rx_photo() {
    var clip = e("webrx-top-photo-clip");
    rx_photo_height = clip.clientHeight;
    clip.style.maxHeight = rx_photo_height + "px";

    $.extend($.easing, {
        easeOutCubic:function(x) {
            return 1 - Math.pow( 1 - x, 3 );
        }
    });

    window.setTimeout(function () {
        $('#webrx-rx-photo-title').animate({opacity: 0}, 500);
    }, 1000);
    window.setTimeout(function () {
        $('#webrx-rx-photo-desc').animate({opacity: 0}, 500);
    }, 1500);
    window.setTimeout(function () {
        close_rx_photo()
    }, 2500);
    $('#webrx-top-container').find('.openwebrx-photo-trigger').click(toggle_rx_photo);
}

var dont_toggle_rx_photo_flag = 0;

function dont_toggle_rx_photo() {
    dont_toggle_rx_photo_flag = 1;
}

function toggle_rx_photo() {
    if (dont_toggle_rx_photo_flag) {
        dont_toggle_rx_photo_flag = 0;
        return;
    }
    if (rx_photo_state) close_rx_photo();
    else open_rx_photo()
}

function close_rx_photo() {
    rx_photo_state = 0;
    $('#webrx-top-photo-clip').animate({maxHeight: 67}, {duration: 1000, easing: 'easeOutCubic'});
    e("openwebrx-rx-details-arrow-down").style.display = "block";
    e("openwebrx-rx-details-arrow-up").style.display = "none";
}

function open_rx_photo() {
    rx_photo_state = 1;
    e("webrx-rx-photo-desc").style.opacity = 1;
    e("webrx-rx-photo-title").style.opacity = 1;
    $('#webrx-top-photo-clip').animate({maxHeight: rx_photo_height}, {duration: 1000, easing: 'easeOutCubic'});
    e("openwebrx-rx-details-arrow-down").style.display = "none";
    e("openwebrx-rx-details-arrow-up").style.display = "block";
}

function updateVolume() {
    audioEngine.setVolume(parseFloat(e("openwebrx-panel-volume").value) / 100);
}

function freqstep(sel){

	stepsize = 0;

	switch(sel) {
    case 0:
        stepsize = -5000;
        break;
    case 1:
        stepsize = -100;
        break;
    case 2:
        stepsize = -10;
        break;
    case 3:
        stepsize = 10;
        break;
    case 4:
        stepsize = 100;
        break;
    case 5:
        stepsize = 5000;
        break;
    default:
        stepsize = 0;
} 

	offset_frequency = parseInt(act_freq)-center_freq;
	new_offset= offset_frequency + stepsize;
	new_qrg = act_freq + stepsize;
	demodulator_set_offset_frequency(0, new_offset);
	e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",new_qrg,1e6,5);
	updateShareLink(new_qrg);
	act_freq = new_qrg;
	}

function updateShareLink(freq){
	//console.log(freq);
	var sqlSliderValue=parseInt(e("openwebrx-panel-squelch").value);
	e("id-freq-link").innerHTML='<a href="'+base_url+'/#freq='+freq+',mod='+last_analog_demodulator_subtype+',sql='+sqlSliderValue+'" target="_blank" title="Share Settings"><img src="icons/link.png"></a>';

}



function toggleMute() {
    if (mute) {
        mute = false;
        e("openwebrx-mute-on").id = "openwebrx-mute-off";
        e("openwebrx-mute-img").src = "static/gfx/openwebrx-speaker.png";
        e("openwebrx-panel-volume").disabled = false;
        e("openwebrx-panel-volume").style.opacity = 1.0;
        e("openwebrx-panel-volume").value = volumeBeforeMute;
    } else {
        mute = true;
        e("openwebrx-mute-off").id = "openwebrx-mute-on";
        e("openwebrx-mute-img").src = "static/gfx/openwebrx-speaker-muted.png";
        e("openwebrx-panel-volume").disabled = true;
        e("openwebrx-panel-volume").style.opacity = 0.5;
        volumeBeforeMute = e("openwebrx-panel-volume").value;
        e("openwebrx-panel-volume").value = 0;
    }

    updateVolume();
}

function zoomInOneStep() {
    zoom_set(zoom_level + 1);
}

function zoomOutOneStep() {
    zoom_set(zoom_level - 1);
}

function zoomInTotal() {
    zoom_set(zoom_levels.length - 1);
}

function zoomOutTotal() {
    zoom_set(0);
}

function setSquelchToAuto() {
    e("openwebrx-panel-squelch").value = (getLogSmeterValue(smeter_level) + 10).toString();
    updateSquelch();
}

function updateSquelch() {
    var sliderValue = parseInt($("#openwebrx-panel-squelch").val());
    ws.send(JSON.stringify({"type": "dspcontrol", "params": {"squelch_level": sliderValue}}));
	updateShareLink(act_freq);
}

var waterfall_min_level;
var waterfall_max_level;
var waterfall_min_level_default;
var waterfall_max_level_default;
var waterfall_colors;
var waterfall_auto_level_margin;

function updateWaterfallColors(which) {
    var wfmax = e("openwebrx-waterfall-color-max");
    var wfmin = e("openwebrx-waterfall-color-min");
    if (parseInt(wfmin.value) >= parseInt(wfmax.value)) {
        if (!which) wfmin.value = (parseInt(wfmax.value) - 1).toString();
        else wfmax.value = (parseInt(wfmin.value) + 1).toString();
    }
    waterfall_min_level = parseInt(wfmin.value);
    waterfall_max_level = parseInt(wfmax.value);
}

function waterfallColorsDefault() {
    waterfall_min_level = waterfall_min_level_default;
    waterfall_max_level = waterfall_max_level_default;
    e("openwebrx-waterfall-color-min").value = waterfall_min_level.toString();
    e("openwebrx-waterfall-color-max").value = waterfall_max_level.toString();
}

function waterfallColorsAuto() {
    e("openwebrx-waterfall-color-min").value = (waterfall_measure_minmax_min - waterfall_auto_level_margin[0]).toString();
    e("openwebrx-waterfall-color-max").value = (waterfall_measure_minmax_max + waterfall_auto_level_margin[1]).toString();
    updateWaterfallColors(0);
}

function setSmeterRelativeValue(value) {
    if (value < 0) value = 0;
    if (value > 1.0) value = 1.0;
    var bar = e("openwebrx-smeter-bar");
    var outer = e("openwebrx-smeter-outer");
    bar.style.width = (outer.offsetWidth * value).toString() + "px";
    var bgRed = "linear-gradient(to top, #ff5939 , #961700)";
    var bgGreen = "linear-gradient(to top, #22ff2f , #008908)";
    var bgYellow = "linear-gradient(to top, #fff720 , #a49f00)";
    bar.style.background = (value > 0.9) ? bgRed : ((value > 0.7) ? bgYellow : bgGreen);
}

function setSquelchSliderBackground(val) {
    var $slider = $('#openwebrx-panel-squelch');
    var min = Number($slider.attr('min'));
    var max = Number($slider.attr('max'));
    var sliderPosition = $slider.val();
    var relative = (val - min) / (max - min);
    // use a brighter color when squelch is open
    var color = val >= sliderPosition ? '#22ff2f' : '#008908';
    // we don't use the gradient, but separate the colors discretely using css tricks
    var style = 'linear-gradient(90deg, ' + color + ', ' + color + ' ' + relative * 100 + '%, #B6B6B6 ' + relative * 100 + '%)';
    $slider.css('--track-background', style);
}

function getLogSmeterValue(value) {
    return 10 * Math.log10(value);
}

function getLinearSmeterValue(db_value) {
    return Math.pow(10, db_value / 10);
}

function setSmeterAbsoluteValue(value) //the value that comes from `csdr squelch_and_smeter_cc`
{
    var logValue = getLogSmeterValue(value);
    setSquelchSliderBackground(logValue);
    var lowLevel = waterfall_min_level - 20;
    var highLevel = waterfall_max_level + 20;
    var percent = (logValue - lowLevel) / (highLevel - lowLevel);
    setSmeterRelativeValue(percent);
    e("openwebrx-smeter-db").innerHTML = logValue.toFixed(1) + " dB";
}

function typeInAnimation(element, timeout, what, onFinish) {
    if (!what) {
        onFinish();
        return;
    }
    element.innerHTML += what[0];
    window.setTimeout(function () {
        typeInAnimation(element, timeout, what.substring(1), onFinish);
    }, timeout);
}


// ========================================================
// ================  DEMODULATOR ROUTINES  ================
// ========================================================

demodulators = [];

var demodulator_color_index = 0;
var demodulator_colors = ["#ffff00", "#00ff00", "#00ffff", "#058cff", "#ff9600", "#a1ff39", "#ff4e39", "#ff5dbd"];

function demodulators_get_next_color() {
    if (demodulator_color_index >= demodulator_colors.length) demodulator_color_index = 0;
    return (demodulator_colors[demodulator_color_index++]);
}

function demod_envelope_draw(range, from, to, color, line) {  //                                               ____
    // Draws a standard filter envelope like this: _/    \_
    // Parameters are given in offset frequency (Hz).
    // Envelope is drawn on the scale canvas.
    // A "drag range" object is returned, containing information about the draggable areas of the envelope
    // (beginning, ending and the line showing the offset frequency).
    if (typeof color === "undefined") color = "#ffff00"; //yellow
    var env_bounding_line_w = 5;   //
    var env_att_w = 5;             //     _______   ___env_h2 in px   ___|_____
    var env_h1 = 17;               //   _/|      \_ ___env_h1 in px _/   |_    \_
    var env_h2 = 5;                //   |||env_att_line_w                |_env_lineplus
    var env_lineplus = 1;          //   ||env_bounding_line_w
    var env_line_click_area = 6;
    //range=get_visible_freq_range();
    var from_px = scale_px_from_freq(from, range);
    var to_px = scale_px_from_freq(to, range);
    if (to_px < from_px) /* swap'em */ {
        var temp_px = to_px;
        to_px = from_px;
        from_px = temp_px;
    }

    /*from_px-=env_bounding_line_w/2;
	to_px+=env_bounding_line_w/2;*/
    from_px -= (env_att_w + env_bounding_line_w);
    to_px += (env_att_w + env_bounding_line_w);
    // do drawing:
    scale_ctx.lineWidth = 3;
    scale_ctx.strokeStyle = color;
    scale_ctx.fillStyle = color;
    var drag_ranges = {envelope_on_screen: false, line_on_screen: false};
    if (!(to_px < 0 || from_px > window.innerWidth)) // out of screen?
    {
        drag_ranges.beginning = {x1: from_px, x2: from_px + env_bounding_line_w + env_att_w};
        drag_ranges.ending = {x1: to_px - env_bounding_line_w - env_att_w, x2: to_px};
        drag_ranges.whole_envelope = {x1: from_px, x2: to_px};
        drag_ranges.envelope_on_screen = true;
        scale_ctx.beginPath();
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
    }
    if (typeof line !== "undefined") // out of screen?
    {
        var line_px = scale_px_from_freq(line, range);
        if (!(line_px < 0 || line_px > window.innerWidth)) {
            drag_ranges.line = {x1: line_px - env_line_click_area / 2, x2: line_px + env_line_click_area / 2};
            drag_ranges.line_on_screen = true;
            scale_ctx.moveTo(line_px, env_h1 + env_lineplus);
            scale_ctx.lineTo(line_px, env_h2 - env_lineplus);
            scale_ctx.stroke();
        }
    }
    return drag_ranges;
}

function demod_envelope_where_clicked(x, drag_ranges, key_modifiers) {  // Check exactly what the user has clicked based on ranges returned by demod_envelope_draw().
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
}

//******* class Demodulator *******
// this can be used as a base class for ANY demodulator
Demodulator = function (offset_frequency) {
    //console.log("this too");
    this.offset_frequency = offset_frequency;
    this.envelope = {};
    this.color = demodulators_get_next_color();
    this.stop = function () {
    };
};
//ranges on filter envelope that can be dragged:
Demodulator.draggable_ranges = {
    none: 0,
    beginning: 1 /*from*/,
    ending: 2 /*to*/,
    anything_else: 3,
    bfo: 4 /*line (while holding shift)*/,
    pbs: 5
}; //to which parameter these correspond in demod_envelope_draw()

//******* class Demodulator_default_analog *******
// This can be used as a base for basic audio demodulators.
// It already supports most basic modulations used for ham radio and commercial services: AM/FM/LSB/USB

demodulator_response_time = 50;

//in ms; if we don't limit the number of SETs sent to the server, audio will underrun (possibly output buffer is cleared on SETs in GNU Radio

function Demodulator_default_analog(offset_frequency, subtype) {
    //console.log("hopefully this happens");
    //http://stackoverflow.com/questions/4152931/javascript-inheritance-call-super-constructor-or-use-prototype-chain
    Demodulator.call(this, offset_frequency);
    this.subtype = subtype;
    this.filter = {
        min_passband: 100,
        high_cut_limit: (audioEngine.getOutputRate() / 2) - 1,
        low_cut_limit: (-audioEngine.getOutputRate() / 2) + 1
    };
    //Subtypes only define some filter parameters and the mod string sent to server,
    //so you may set these parameters in your custom child class.
    //Why? As of demodulation is done on the server, difference is mainly on the server side.
    this.server_mod = subtype;
    if (subtype === "lsb") {
        this.low_cut = -3000;
        this.high_cut = -300;
        this.server_mod = "ssb";
    }
    else if (subtype === "usb") {
        this.low_cut = 300;
        this.high_cut = 3000;
        this.server_mod = "ssb";
    }
    else if (subtype === "cw") {
        this.low_cut = 700;
        this.high_cut = 900;
        this.server_mod = "ssb";
    }
    else if (subtype === "nfm") {
        this.low_cut = -4000;
        this.high_cut = 4000;
    }
    else if (subtype === "dmr" || subtype === "ysf") {
        this.low_cut = -4000;
        this.high_cut = 4000;
    }
    else if (subtype === "dstar" || subtype === "nxdn") {
        this.low_cut = -3250;
        this.high_cut = 3250;
    }
    else if (subtype === "am") {
        this.low_cut = -4000;
        this.high_cut = 4000;
    }

    this.wait_for_timer = false;
    this.set_after = false;
    this.set = function () { //set() is a wrapper to call doset(), but it ensures that doset won't execute more frequently than demodulator_response_time.
        if (!this.wait_for_timer) {
            this.doset(false);
            this.set_after = false;
            this.wait_for_timer = true;
            var timeout_this = this; //http://stackoverflow.com/a/2130411
            window.setTimeout(function () {
                timeout_this.wait_for_timer = false;
                if (timeout_this.set_after) timeout_this.set();
            }, demodulator_response_time);
        }
        else {
            this.set_after = true;
        }
    };

    this.doset = function (first_time) {  //this function sends demodulator parameters to the server
        var params = {
            "low_cut": this.low_cut,
            "high_cut": this.high_cut,
            "offset_freq": this.offset_frequency
        };
        if (first_time) params.mod = this.server_mod;
        ws.send(JSON.stringify({"type": "dspcontrol", "params": params}));
    };
    this.doset(true); //we set parameters on object creation

    //******* envelope object *******
    // for drawing the filter envelope above scale
    this.envelope.parent = this;

    this.envelope.draw = function (visible_range) {
        this.visible_range = visible_range;
        this.drag_ranges = demod_envelope_draw(range,
            center_freq + this.parent.offset_frequency + this.parent.low_cut,
            center_freq + this.parent.offset_frequency + this.parent.high_cut,
            this.color, center_freq + this.parent.offset_frequency);
    };

    this.envelope.dragged_range = Demodulator.draggable_ranges.none;

    // event handlers
    this.envelope.drag_start = function (x, key_modifiers) {
        this.key_modifiers = key_modifiers;
        this.dragged_range = demod_envelope_where_clicked(x, this.drag_ranges, key_modifiers);
        this.drag_origin = {
            x: x,
            low_cut: this.parent.low_cut,
            high_cut: this.parent.high_cut,
            offset_frequency: this.parent.offset_frequency
        };
        return this.dragged_range !== Demodulator.draggable_ranges.none;
    };

    this.envelope.drag_move = function (x) {
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
            if ((new_value = this.drag_origin.low_cut + minus * freq_change) < this.parent.filter.low_cut_limit) return true;
            //nor the filter passband be too small
            if (this.parent.high_cut - new_value < this.parent.filter.min_passband) return true;
            //sanity check to prevent GNU Radio "firdes check failed: fa <= fb"
            if (new_value >= this.parent.high_cut) return true;
            this.parent.low_cut = new_value;
        }
        if (this.dragged_range === dr.ending || this.dragged_range === dr.bfo || this.dragged_range === dr.pbs) {
            //we don't let high_cut go beyond its limits
            if ((new_value = this.drag_origin.high_cut + minus * freq_change) > this.parent.filter.high_cut_limit) return true;
            //nor the filter passband be too small
            if (new_value - this.parent.low_cut < this.parent.filter.min_passband) return true;
            //sanity check to prevent GNU Radio "firdes check failed: fa <= fb"
            if (new_value <= this.parent.low_cut) return true;
            this.parent.high_cut = new_value;
        }
        if (this.dragged_range === dr.anything_else || this.dragged_range === dr.bfo) {
            //when any other part of the envelope is dragged, the offset frequency is changed (whole passband also moves with it)
            new_value = this.drag_origin.offset_frequency + freq_change;
            if (new_value > bandwidth / 2 || new_value < -bandwidth / 2) return true; //we don't allow tuning above Nyquist frequency :-)
            this.parent.offset_frequency = new_value;
        }
        //now do the actual modifications:
        mkenvelopes(this.visible_range);
        this.parent.set();
        //will have to change this when changing to multi-demodulator mode:
        //e("webrx-actual-freq").innerHTML = format_frequency("{x} MHz", center_freq + this.parent.offset_frequency, 1e6, 4);
		e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",center_freq+this.parent.offset_frequency,1e6,5);
		act_freq=center_freq+this.parent.offset_frequency;
		updateShareLink(act_freq);		
        return true;
    };

    this.envelope.drag_end = function () { //in this demodulator we've already changed values in the drag_move() function so we shouldn't do too much here.
        demodulator_buttons_update();
        var to_return = this.dragged_range !== Demodulator.draggable_ranges.none; //this part is required for cliking anywhere on the scale to set offset
        this.dragged_range = Demodulator.draggable_ranges.none;
        return to_return;
    };

}

Demodulator_default_analog.prototype = new Demodulator();

function mkenvelopes(visible_range) //called from mkscale
{
    scale_ctx.clearRect(0, 0, scale_ctx.canvas.width, 22); //clear the upper part of the canvas (where filter envelopes reside)
    for (var i = 0; i < demodulators.length; i++) {
        demodulators[i].envelope.draw(visible_range);
    }
    if (demodulators.length) secondary_demod_waterfall_set_zoom(demodulators[0].low_cut, demodulators[0].high_cut);
}

function demodulator_remove(which) {
    demodulators[which].stop();
    demodulators.splice(which, 1);
}

function demodulator_add(what) {
    demodulators.push(what);
    mkenvelopes(get_visible_freq_range());
}

var last_analog_demodulator_subtype = 'nfm';
var last_digital_demodulator_subtype = 'bpsk31';

function demodulator_analog_replace(subtype, for_digital) { //this function should only exist until the multi-demodulator capability is added
    if (!(typeof for_digital !== "undefined" && for_digital && secondary_demod)) {
        secondary_demod_close_window();
        secondary_demod_listbox_update();
    }
    last_analog_demodulator_subtype = subtype;
    var temp_offset = 0;
    if (demodulators.length) {
        temp_offset = demodulators[0].offset_frequency;
        demodulator_remove(0);
    }
    demodulator_add(new Demodulator_default_analog(temp_offset, subtype));
    demodulator_buttons_update();
	updateShareLink(act_freq);
    update_digitalvoice_panels("openwebrx-panel-metadata-" + subtype);
}

function demodulator_set_offset_frequency(which, to_what) {
    if (to_what > bandwidth / 2 || to_what < -bandwidth / 2) return;
    demodulators[0].offset_frequency = Math.round(to_what);
    demodulators[0].set();
    mkenvelopes(get_visible_freq_range());
    $("#webrx-actual-freq").html(format_frequency("{x} MHz", center_freq + to_what, 1e6, 4));
}

function waterfallWidth() {
    return $('body').width();
}


// ========================================================
// ===================  SCALE ROUTINES  ===================
// ========================================================

var scale_ctx;
var scale_canvas;

function scale_setup() {
//    e("webrx-actual-freq").innerHTML = format_frequency("{x} MHz", canvas_get_frequency(window.innerWidth / 2), 1e6, 4);
	act_freq=center_freq;
	e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",act_freq,1e6,5);
	updateShareLink(act_freq);
	
    scale_canvas = e("openwebrx-scale-canvas");
    scale_ctx = scale_canvas.getContext("2d");
    scale_canvas.addEventListener("mousedown", scale_canvas_mousedown, false);
    scale_canvas.addEventListener("mousemove", scale_canvas_mousemove, false);
    scale_canvas.addEventListener("mouseup", scale_canvas_mouseup, false);
	scale_canvas.addEventListener("wheel",scale_canvas_mousewheel, false);
    resize_scale();
    var frequency_container = e("openwebrx-frequency-container");
    frequency_container.addEventListener("mousemove", frequency_container_mousemove, false);
}

var scale_canvas_scroll_params={
	key_modifiers: {shiftKey:false, altKey: false, ctrlKey: false}
};


function scale_canvas_mousewheel(evt)
{
	//if(!waterfall_setup_done) return;

	var relativeX=(evt.offsetX)?evt.offsetX:evt.layerX;
	var dir=(evt.deltaY/Math.abs(evt.deltaY))>0;
	if (dir){ // scroll down on scale

		if (evt.shiftKey){ // shift pressed
			stepsize = -5000;
		} else {
			stepsize = -100; 
		}
	} else { // scroll up on scale
		if (evt.shiftKey){ // shift pressed
			stepsize = 5000;
		} else {
			stepsize = 100; 
		}
	}
	//console.log(act_freq);
	offset_frequency = parseInt(act_freq)-center_freq;
	new_offset= offset_frequency + stepsize;
	//console.log(new_offset);
	if (Math.abs(new_offset) < bandwidth/2){ // don't tune out of range

		new_qrg = act_freq + stepsize
		demodulator_set_offset_frequency(0, new_offset);
		e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",new_qrg,1e6,5);
		updateShareLink(new_qrg);
		act_freq = new_qrg;
	}
	evt.preventDefault(); 
}


var scale_canvas_drag_params = {
    mouse_down: false,
    drag: false,
    start_x: 0,
    key_modifiers: {shiftKey: false, altKey: false, ctrlKey: false}
};

function scale_canvas_mousedown(evt) {
    scale_canvas_drag_params.mouse_down = true;
    scale_canvas_drag_params.drag = false;
    scale_canvas_drag_params.start_x = evt.pageX;
    scale_canvas_drag_params.key_modifiers.shiftKey = evt.shiftKey;
    scale_canvas_drag_params.key_modifiers.altKey = evt.altKey;
    scale_canvas_drag_params.key_modifiers.ctrlKey = evt.ctrlKey;
    evt.preventDefault();
}

function scale_offset_freq_from_px(x, visible_range) {
    if (typeof visible_range === "undefined") visible_range = get_visible_freq_range();
    return (visible_range.start + visible_range.bw * (x / waterfallWidth())) - center_freq;
}

function scale_canvas_mousemove(evt) {
    var event_handled = false;
    var i;
    if (scale_canvas_drag_params.mouse_down && !scale_canvas_drag_params.drag && Math.abs(evt.pageX - scale_canvas_drag_params.start_x) > canvas_drag_min_delta)
    //we can use the main drag_min_delta thing of the main canvas
    {
        scale_canvas_drag_params.drag = true;
        //call the drag_start for all demodulators (and they will decide if they're dragged, based on X coordinate)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_start(evt.pageX, scale_canvas_drag_params.key_modifiers);
        scale_canvas.style.cursor = "move";
    }
    else if (scale_canvas_drag_params.drag) {
        //call the drag_move for all demodulators (and they will decide if they're dragged)
        for (i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_move(evt.pageX);
        if (!event_handled) demodulator_set_offset_frequency(0, scale_offset_freq_from_px(evt.pageX));
    }
	else
	{
		relativeX=(evt.offsetX)?evt.offsetX:evt.layerX; 
		e("webrx-mouse-freq").innerHTML=format_frequency("{x} MHz",canvas_get_frequency(relativeX),1e6,4);
	}
}

function frequency_container_mousemove(evt) {
    var frequency = center_freq + scale_offset_freq_from_px(evt.pageX);
    e("webrx-mouse-freq").innerHTML = format_frequency("{x} MHz", frequency, 1e6, 4);
}

function scale_canvas_end_drag(x) {
    scale_canvas.style.cursor = "default";
    scale_canvas_drag_params.drag = false;
    scale_canvas_drag_params.mouse_down = false;
    var event_handled = false;
    for (var i = 0; i < demodulators.length; i++) event_handled |= demodulators[i].envelope.drag_end();
    //if (!event_handled) demodulator_set_offset_frequency(0, scale_offset_freq_from_px(x));
	if (!event_handled) {
		demodulator_set_offset_frequency(0,scale_offset_freq_from_px(x));
		new_qrg = parseInt(center_freq + scale_offset_freq_from_px(x));
		e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",new_qrg,1e6,5);
		updateShareLink(new_qrg);
		act_freq = new_qrg;
	}	
}

function scale_canvas_mouseup(evt) {
    scale_canvas_end_drag(evt.pageX);
}

function scale_px_from_freq(f, range) {
    return Math.round(((f - range.start) / range.bw) * waterfallWidth());
}

function get_visible_freq_range() {
    var out = {};
    var fcalc = function (x) {
        var canvasWidth = waterfallWidth() * zoom_levels[zoom_level];
        return Math.round(((-zoom_offset_px + x) / canvasWidth) * bandwidth) + (center_freq - bandwidth / 2);
    };
    out.start = fcalc(0);
    out.center = fcalc(waterfallWidth() / 2);
    out.end = fcalc(waterfallWidth());
    out.bw = out.end - out.start;
    out.hps = out.bw / waterfallWidth();
    return out;
}

var scale_markers_levels = [
    {
        "large_marker_per_hz": 10000000, //large
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 5000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 1000000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 0
    },
    {
        "large_marker_per_hz": 500000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 100000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    },
    {
        "large_marker_per_hz": 50000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 10000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 2
    },
    {
        "large_marker_per_hz": 5000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 3
    },
    {
        "large_marker_per_hz": 1000,
        "estimated_text_width": 70,
        "format": "{x} MHz",
        "pre_divide": 1000000,
        "decimals": 1
    }
];
var scale_min_space_bw_texts = 50;
var scale_min_space_bw_small_markers = 7;

function get_scale_mark_spacing(range) {
    var out = {};
    var fcalc = function (freq) {
        out.numlarge = (range.bw / freq);
        out.large = waterfallWidth() / out.numlarge; 	//distance between large markers (these have text)
        out.ratio = 5; 														//(ratio-1) small markers exist per large marker
        out.small = out.large / out.ratio; 								//distance between small markers
        if (out.small < scale_min_space_bw_small_markers) return false;
        if (out.small / 2 >= scale_min_space_bw_small_markers && freq.toString()[0] !== "5") {
            out.small /= 2;
            out.ratio *= 2;
        }
        out.smallbw = freq / out.ratio;
        return true;
    };
    for (var i = scale_markers_levels.length - 1; i >= 0; i--) {
        var mp = scale_markers_levels[i];
        if (!fcalc(mp.large_marker_per_hz)) continue;
        //console.log(mp.large_marker_per_hz);
        //console.log(out);
        if (out.large - mp.estimated_text_width > scale_min_space_bw_texts) break;
    }
    out.params = mp;
    return out;
}

var range;

function mkscale() {
    //clear the lower part of the canvas (where frequency scale resides; the upper part is used by filter envelopes):
    range = get_visible_freq_range();
    mkenvelopes(range); //when scale changes we will always have to redraw filter envelopes, too
    scale_ctx.clearRect(0, 22, scale_ctx.canvas.width, scale_ctx.canvas.height - 22);
    scale_ctx.strokeStyle = "#fff";
    scale_ctx.font = "bold 11px sans-serif";
    scale_ctx.textBaseline = "top";
    scale_ctx.fillStyle = "#fff";
    var spacing = get_scale_mark_spacing(range);
    //console.log(spacing);
    var marker_hz = Math.ceil(range.start / spacing.smallbw) * spacing.smallbw;
    var text_h_pos = 22 + 10 + ((is_firefox) ? 3 : 0);
    var text_to_draw = '';
    var ftext = function (f) {
        text_to_draw = format_frequency(spacing.params.format, f, spacing.params.pre_divide, spacing.params.decimals);
    };
    var last_large;
    var x;
    for (; ;) {
        x = scale_px_from_freq(marker_hz, range);
        if (x > window.innerWidth) break;
        scale_ctx.beginPath();
        scale_ctx.moveTo(x, 22);
        if (marker_hz % spacing.params.large_marker_per_hz === 0) {  //large marker
            if (typeof first_large === "undefined") var first_large = marker_hz;
            last_large = marker_hz;
            scale_ctx.lineWidth = 3.5;
            scale_ctx.lineTo(x, 22 + 11);
            ftext(marker_hz);
            var text_measured = scale_ctx.measureText(text_to_draw);
            scale_ctx.textAlign = "center";
            //advanced text drawing begins
            if (zoom_level === 0 && (range.start + spacing.smallbw * spacing.ratio > marker_hz) && (x < text_measured.width / 2)) { //if this is the first overall marker when zoomed out...                  and if it would be clipped off the screen...
                if (scale_px_from_freq(marker_hz + spacing.smallbw * spacing.ratio, range) - text_measured.width >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "left";
                    scale_ctx.fillText(text_to_draw, 0, text_h_pos);
                }
            }
            else if (zoom_level === 0 && (range.end - spacing.smallbw * spacing.ratio < marker_hz) && (x > window.innerWidth - text_measured.width / 2)) { //     if this is the last overall marker when zoomed out...                 and if it would be clipped off the screen...
                if (window.innerWidth - text_measured.width - scale_px_from_freq(marker_hz - spacing.smallbw * spacing.ratio, range) >= scale_min_space_bw_texts) { //and if we have enough space to draw it correctly without clipping
                    scale_ctx.textAlign = "right";
                    scale_ctx.fillText(text_to_draw, window.innerWidth, text_h_pos);
                }
            }
            else scale_ctx.fillText(text_to_draw, x, text_h_pos); //draw text normally
        }
        else {  //small marker
            scale_ctx.lineWidth = 2;
            scale_ctx.lineTo(x, 22 + 8);
        }
        marker_hz += spacing.smallbw;
        scale_ctx.stroke();
    }
    if (zoom_level !== 0) { // if zoomed, we don't want the texts to disappear because their markers can't be seen
        // on the left side
        scale_ctx.textAlign = "center";
        var f = first_large - spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        var w = scale_ctx.measureText(text_to_draw).width;
        if (x + w / 2 > 0) scale_ctx.fillText(text_to_draw, x, 22 + 10);
        // on the right side
        f = last_large + spacing.smallbw * spacing.ratio;
        x = scale_px_from_freq(f, range);
        ftext(f);
        w = scale_ctx.measureText(text_to_draw).width;
        if (x - w / 2 < window.innerWidth) scale_ctx.fillText(text_to_draw, x, 22 + 10);
    }
}

function resize_scale() {
    var ratio = window.devicePixelRatio || 1;
    var w = window.innerWidth;
    var h = 47;
    scale_canvas.style.width = w + "px";
    scale_canvas.style.height = h + "px";
    w *= ratio;
    h *= ratio;
    scale_canvas.width = w;
    scale_canvas.height = h;
    scale_ctx.scale(ratio, ratio);
    mkscale();
    bookmarks.position();
}

function canvas_get_freq_offset(relativeX) {
    var rel = (relativeX / canvases[0].clientWidth);
    return Math.round((bandwidth * rel) - (bandwidth / 2));
}

function canvas_get_frequency(relativeX) {
    return center_freq + canvas_get_freq_offset(relativeX);
}


function format_frequency(format, freq_hz, pre_divide, decimals) {
    var out = format.replace("{x}", (freq_hz / pre_divide).toFixed(decimals));
    var at = out.indexOf(".") + 4;
    while (decimals > 3) {
        out = out.substr(0, at) + "," + out.substr(at);
        at += 4;
        decimals -= 3;
    }
    return out;
}

var canvas_drag = false;
var canvas_drag_min_delta = 1;
var canvas_mouse_down = false;
var canvas_drag_last_x;
var canvas_drag_last_y;
var canvas_drag_start_x;
var canvas_drag_start_y;

function canvas_mousedown(evt) {
    canvas_mouse_down = true;
    canvas_drag = false;
    canvas_drag_last_x = canvas_drag_start_x = evt.pageX;
    canvas_drag_last_y = canvas_drag_start_y = evt.pageY;
    evt.preventDefault(); //don't show text selection mouse pointer
}

function canvas_mousemove(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    if (canvas_mouse_down) {
        if (!canvas_drag && Math.abs(evt.pageX - canvas_drag_start_x) > canvas_drag_min_delta) {
            canvas_drag = true;
            canvas_container.style.cursor = "move";
        }
        if (canvas_drag) {
            var deltaX = canvas_drag_last_x - evt.pageX;
            var dpx = range.hps * deltaX;
            if (
                !(zoom_center_rel + dpx > (bandwidth / 2 - waterfallWidth() * (1 - zoom_center_where) * range.hps)) &&
                !(zoom_center_rel + dpx < -bandwidth / 2 + waterfallWidth() * zoom_center_where * range.hps)
            ) {
                zoom_center_rel += dpx;
            }
            resize_canvases(false);
            canvas_drag_last_x = evt.pageX;
            canvas_drag_last_y = evt.pageY;
            mkscale();
            bookmarks.position();
        }
    }
    else e("webrx-mouse-freq").innerHTML = format_frequency("{x} MHz", canvas_get_frequency(relativeX), 1e6, 4);
}

function canvas_container_mouseleave() {
    canvas_end_drag();
}

function canvas_mouseup(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);

    if (!canvas_drag) {
        demodulator_set_offset_frequency(0, canvas_get_freq_offset(relativeX));
		e("webrx-actual-freq").innerHTML=format_frequency("{x} MHz",canvas_get_frequency(relativeX),1e6,5);
		act_freq=canvas_get_frequency(relativeX);
		updateShareLink(act_freq);
    }
    else {
        canvas_end_drag();
    }
    canvas_mouse_down = false;
}

function canvas_end_drag() {
    canvas_container.style.cursor = "crosshair";
    canvas_mouse_down = false;
}

function zoom_center_where_calc(screenposX) {
    return screenposX / waterfallWidth();
}

function get_relative_x(evt) {
    var relativeX = evt.offsetX || evt.layerX;
    if ($(evt.target).closest(canvas_container).length) return relativeX;
    // compensate for the frequency scale, since that is not resized by the browser.
    var relatives = $(evt.target).closest('#openwebrx-frequency-container').map(function(){
        return evt.pageX - this.offsetLeft;
    });
    if (relatives.length) relativeX = relatives[0];

    return relativeX - zoom_offset_px;
}

function canvas_mousewheel(evt) {
    if (!waterfall_setup_done) return;
    var relativeX = get_relative_x(evt);
    var dir = (evt.deltaY / Math.abs(evt.deltaY)) > 0;
    zoom_step(dir, relativeX, zoom_center_where_calc(evt.pageX));
    evt.preventDefault();
}


var zoom_max_level_hps = 33; //Hz/pixel
var zoom_levels_count = 14;

function get_zoom_coeff_from_hps(hps) {
    var shown_bw = (window.innerWidth * hps);
    return bandwidth / shown_bw;
}

var zoom_levels = [1];
var zoom_level = 0;
var zoom_offset_px = 0;
var zoom_center_rel = 0;
var zoom_center_where = 0;

var smeter_level = 0;

function mkzoomlevels() {
    zoom_levels = [1];
    var maxc = get_zoom_coeff_from_hps(zoom_max_level_hps);
    if (maxc < 1) return;
    // logarithmic interpolation
    var zoom_ratio = Math.pow(maxc, 1 / zoom_levels_count);
    for (var i = 1; i < zoom_levels_count; i++)
        zoom_levels.push(Math.pow(zoom_ratio, i));
}

function zoom_step(out, where, onscreen) {
    if ((out && zoom_level === 0) || (!out && zoom_level >= zoom_levels_count - 1)) return;
    if (out) --zoom_level;
    else ++zoom_level;

    zoom_center_rel = canvas_get_freq_offset(where);
    //console.log("zoom_step || zlevel: "+zoom_level.toString()+" zlevel_val: "+zoom_levels[zoom_level].toString()+" zoom_center_rel: "+zoom_center_rel.toString());
    zoom_center_where = onscreen;
    //console.log(zoom_center_where, zoom_center_rel, where);
    resize_canvases(true);
    mkscale();
    bookmarks.position();
}

function zoom_set(level) {
    if (!(level >= 0 && level <= zoom_levels.length - 1)) return;
    level = parseInt(level);
    zoom_level = level;
    //zoom_center_rel=canvas_get_freq_offset(-canvases[0].offsetLeft+waterfallWidth()/2); //zoom to screen center instead of demod envelope
    zoom_center_rel = demodulators[0].offset_frequency;
    zoom_center_where = 0.5 + (zoom_center_rel / bandwidth); //this is a kind of hack
    resize_canvases(true);
    mkscale();
    bookmarks.position();
}

function zoom_calc() {
    var winsize = waterfallWidth();
    var canvases_new_width = winsize * zoom_levels[zoom_level];
    zoom_offset_px = -((canvases_new_width * (0.5 + zoom_center_rel / bandwidth)) - (winsize * zoom_center_where));
    if (zoom_offset_px > 0) zoom_offset_px = 0;
    if (zoom_offset_px < winsize - canvases_new_width)
        zoom_offset_px = winsize - canvases_new_width;
}

var networkSpeedMeasurement;
var currentprofile;

var COMPRESS_FFT_PAD_N = 10; //should be the same as in csdr.c

function on_ws_recv(evt) {
    if (typeof evt.data === 'string') {
        // text messages
        networkSpeedMeasurement.add(evt.data.length);

        if (evt.data.substr(0, 16) === "CLIENT DE SERVER") {
            divlog("Server acknowledged WebSocket connection.");
        } else {
            try {
                var json = JSON.parse(evt.data);
                switch (json.type) {
                    case "config":
                        var config = json['value'];
                        waterfall_colors = config['waterfall_colors'];
                        waterfall_min_level_default = config['waterfall_min_level'];
                        waterfall_max_level_default = config['waterfall_max_level'];
                        waterfall_auto_level_margin = config['waterfall_auto_level_margin'];
                        waterfallColorsDefault();

                        starting_mod = config['start_mod'];
                        starting_offset_frequency = config['start_offset_freq'];
                        bandwidth = config['samp_rate'];
                        center_freq = config['center_freq'];
                        fft_size = config['fft_size'];
                        fft_fps = config['fft_fps'];
                        var audio_compression = config['audio_compression'];
                        audioEngine.setCompression(audio_compression);
                        divlog("Audio stream is " + ((audio_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        fft_compression = config['fft_compression'];
                        divlog("FFT stream is " + ((fft_compression === "adpcm") ? "compressed" : "uncompressed") + ".");
                        clientProgressBar.setMaxClients(config['max_clients']);
                        mathbox_waterfall_colors = config['mathbox_waterfall_colors'];
                        mathbox_waterfall_frequency_resolution = config['mathbox_waterfall_frequency_resolution'];
                        mathbox_waterfall_history_length = config['mathbox_waterfall_history_length'];
                        var sql = Number.isInteger(config['initial_squelch_level']) ? config['initial_squelch_level'] : -150;
                        $("#openwebrx-panel-squelch").val(sql);
                        updateSquelch();

                        waterfall_init();
                        initialize_demodulator();
                        bookmarks.loadLocalBookmarks();

                        waterfall_clear();

                        currentprofile = config['sdr_id'] + '|' + config['profile_id'];
                        $('#openwebrx-sdr-profiles-listbox').val(currentprofile);

                        break;
                    case "secondary_config":
                        var s = json['value'];
                        window.secondary_fft_size = s['secondary_fft_size'];
                        window.secondary_bw = s['secondary_bw'];
                        window.if_samp_rate = s['if_samp_rate'];
                        secondary_demod_init_canvases();
                        break;
                    case "receiver_details":
                        var r = json['value'];
                        e('webrx-rx-title').innerHTML = r['receiver_name'];
                        e('webrx-rx-desc').innerHTML = r['receiver_location'] + ' | Loc: ' + r['locator'] + ', ASL: ' + r['receiver_asl'] + ' m, <a href="https://www.google.hu/maps/place/' + r['receiver_gps'][0] + ',' + r['receiver_gps'][1] + '" target="_blank" onclick="dont_toggle_rx_photo();">[maps]</a>';
                        e('webrx-rx-photo-title').innerHTML = r['photo_title'];
                        e('webrx-rx-photo-desc').innerHTML = r['photo_desc'];
                        break;
                    case "smeter":
                        smeter_level = json['value'];
                        setSmeterAbsoluteValue(smeter_level);
                        break;
                    case "cpuusage":
                        cpuProgressBar.setUsage(json['value']);
                        break;
                    case "clients":
                        clientProgressBar.setClients(json['value']);
                        break;
                    case "profiles":
                        var listbox = e("openwebrx-sdr-profiles-listbox");
                        listbox.innerHTML = json['value'].map(function (profile) {
                            return '<option value="' + profile['id'] + '">' + profile['name'] + "</option>";
                        }).join("");
                        if (currentprofile) {
                            $('#openwebrx-sdr-profiles-listbox').val(currentprofile);
                        }
                        break;
                    case "features":
                        var features = json['value'];
                        for (var feature in features) {
                            if (features.hasOwnProperty(feature)) {
                                $('[data-feature="' + feature + '"')[features[feature] ? "show" : "hide"]();
                            }
                        }
                        break;
                    case "metadata":
                        update_metadata(json['value']);
                        break;
                    case "wsjt_message":
                        update_wsjt_panel(json['value']);
                        break;
                    case "dial_frequencies":
                        var as_bookmarks = json['value'].map(function (d) {
                            return {
                                name: d['mode'].toUpperCase(),
                                digital_modulation: d['mode'],
                                frequency: d['frequency']
                            };
                        });
                        bookmarks.replace_bookmarks(as_bookmarks, 'dial_frequencies');
                        break;
                    case "aprs_data":
                        update_packet_panel(json['value']);
                        break;
                    case "bookmarks":
                        bookmarks.replace_bookmarks(json['value'], "server");
                        break;
                    case "sdr_error":
                        divlog(json['value'], true);
                        break;
                    case 'secondary_demod':
                        secondary_demod_push_data(json['value']);
                        break;
                    default:
                        console.warn('received message of unknown type: ' + json['type']);
                }
            } catch (e) {
                // don't lose exception
                console.error(e)
            }
        }
    } else if (evt.data instanceof ArrayBuffer) {
        // binary messages
        networkSpeedMeasurement.add(evt.data.byteLength);

        var type = new Uint8Array(evt.data, 0, 1)[0];
        var data = evt.data.slice(1);

        var waterfall_i16;
        var waterfall_f32;
        var i;

        switch (type) {
            case 1:
                // FFT data
                if (fft_compression === "none") {
                    waterfall_add(new Float32Array(data));
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                    waterfall_add(waterfall_f32);
                }
                break;
            case 2:
                // audio data
                audioEngine.pushAudio(data);
                break;
            case 3:
                // secondary FFT
                if (fft_compression === "none") {
                    secondary_demod_waterfall_add(new Float32Array(data));
                } else if (fft_compression === "adpcm") {
                    fft_codec.reset();

                    waterfall_i16 = fft_codec.decode(new Uint8Array(data));
                    waterfall_f32 = new Float32Array(waterfall_i16.length - COMPRESS_FFT_PAD_N);
                    for (i = 0; i < waterfall_i16.length; i++) waterfall_f32[i] = waterfall_i16[i + COMPRESS_FFT_PAD_N] / 100;
                    secondary_demod_waterfall_add(waterfall_f32);
                }
                break;
            default:
                console.warn('unknown type of binary message: ' + type)
        }
    }
}

function update_metadata(meta) {
    var el;
    if (meta['protocol']) switch (meta['protocol']) {
        case 'DMR':
            if (meta['slot']) {
                el = $("#openwebrx-panel-metadata-dmr").find(".openwebrx-dmr-timeslot-panel").get(meta['slot']);
                var id = "";
                var name = "";
                var target = "";
                var group = false;
                $(el)[meta['sync'] ? "addClass" : "removeClass"]("sync");
                if (meta['sync'] && meta['sync'] === "voice") {
                    id = (meta['additional'] && meta['additional']['callsign']) || meta['source'] || "";
                    name = (meta['additional'] && meta['additional']['fname']) || "";
                    if (meta['type'] === "group") {
                        target = "Talkgroup: ";
                        group = true;
                    }
                    if (meta['type'] === "direct") target = "Direct: ";
                    target += meta['target'] || "";
                    $(el).addClass("active");
                } else {
                    $(el).removeClass("active");
                }
                $(el).find(".openwebrx-dmr-id").text(id);
                $(el).find(".openwebrx-dmr-name").text(name);
                $(el).find(".openwebrx-dmr-target").text(target);
                $(el).find(".openwebrx-meta-user-image")[group ? "addClass" : "removeClass"]("group");
            } else {
                clear_metadata();
            }
            break;
        case 'YSF':
            el = $("#openwebrx-panel-metadata-ysf");

            var mode = " ";
            var source = "";
            var up = "";
            var down = "";
            if (meta['mode'] && meta['mode'] !== "") {
                mode = "Mode: " + meta['mode'];
                source = meta['source'] || "";
                if (meta['lat'] && meta['lon'] && meta['source']) {
                    source = "<a class=\"openwebrx-maps-pin\" href=\"/map?callsign=" + meta['source'] + "\" target=\"_blank\"></a>" + source;
                }
                up = meta['up'] ? "Up: " + meta['up'] : "";
                down = meta['down'] ? "Down: " + meta['down'] : "";
                $(el).find(".openwebrx-meta-slot").addClass("active");
            } else {
                $(el).find(".openwebrx-meta-slot").removeClass("active");
            }
            $(el).find(".openwebrx-ysf-mode").text(mode);
            $(el).find(".openwebrx-ysf-source").html(source);
            $(el).find(".openwebrx-ysf-up").text(up);
            $(el).find(".openwebrx-ysf-down").text(down);

            break;
    } else {
        clear_metadata();
    }

}

function html_escape(input) {
    return $('<div/>').text(input).html()
}

function update_wsjt_panel(msg) {
    var $b = $('#openwebrx-panel-wsjt-message').find('tbody');
    var t = new Date(msg['timestamp']);
    var pad = function (i) {
        return ('' + i).padStart(2, "0");
    };
    var linkedmsg = msg['msg'];
    var matches;
    if (['FT8', 'JT65', 'JT9', 'FT4'].indexOf(msg['mode']) >= 0) {
        matches = linkedmsg.match(/(.*\s[A-Z0-9]+\s)([A-R]{2}[0-9]{2})$/);
        if (matches && matches[2] !== 'RR73') {
            linkedmsg = html_escape(matches[1]) + '<a href="/map?locator=' + matches[2] + '" target="_blank">' + matches[2] + '</a>';
        } else {
            linkedmsg = html_escape(linkedmsg);
        }
    } else if (msg['mode'] === 'WSPR') {
        matches = linkedmsg.match(/([A-Z0-9]*\s)([A-R]{2}[0-9]{2})(\s[0-9]+)/);
        if (matches) {
            linkedmsg = html_escape(matches[1]) + '<a href="/map?locator=' + matches[2] + '" target="_blank">' + matches[2] + '</a>' + html_escape(matches[3]);
        } else {
            linkedmsg = html_escape(linkedmsg);
        }
    }
    $b.append($(
        '<tr data-timestamp="' + msg['timestamp'] + '">' +
        '<td>' + pad(t.getUTCHours()) + pad(t.getUTCMinutes()) + pad(t.getUTCSeconds()) + '</td>' +
        '<td class="decimal">' + msg['db'] + '</td>' +
        '<td class="decimal">' + msg['dt'] + '</td>' +
        '<td class="decimal freq">' + msg['freq'] + '</td>' +
        '<td class="message">' + linkedmsg + '</td>' +
        '</tr>'
    ));
    $b.scrollTop($b[0].scrollHeight);
}

var digital_removal_interval;

// remove old wsjt messages in fixed intervals
function init_digital_removal_timer() {
    if (digital_removal_interval) clearInterval(digital_removal_interval);
    digital_removal_interval = setInterval(function () {
        ['#openwebrx-panel-wsjt-message', '#openwebrx-panel-packet-message'].forEach(function (root) {
            var $elements = $(root + ' tbody tr');
            // limit to 1000 entries in the list since browsers get laggy at some point
            var toRemove = $elements.length - 1000;
            if (toRemove <= 0) return;
            $elements.slice(0, toRemove).remove();
        });
    }, 15000);
}

function update_packet_panel(msg) {
    var $b = $('#openwebrx-panel-packet-message').find('tbody');
    var pad = function (i) {
        return ('' + i).padStart(2, "0");
    };

    if (msg.type && msg.type === 'thirdparty' && msg.data) {
        msg = msg.data;
    }
    var source = msg.source;
    if (msg.type) {
        if (msg.type === 'item') {
            source = msg.item;
        }
        if (msg.type === 'object') {
            source = msg.object;
        }
    }

    var timestamp = '';
    if (msg.timestamp) {
        var t = new Date(msg.timestamp);
        timestamp = pad(t.getUTCHours()) + pad(t.getUTCMinutes()) + pad(t.getUTCSeconds())
    }

    var link = '';
    var classes = [];
    var styles = {};
    var overlay = '';
    var stylesToString = function (s) {
        return $.map(s, function (value, key) {
            return key + ':' + value + ';'
        }).join('')
    };
    if (msg.symbol) {
        classes.push('aprs-symbol');
        classes.push('aprs-symboltable-' + (msg.symbol.table === '/' ? 'normal' : 'alternate'));
        styles['background-position-x'] = -(msg.symbol.index % 16) * 15 + 'px';
        styles['background-position-y'] = -Math.floor(msg.symbol.index / 16) * 15 + 'px';
        if (msg.symbol.table !== '/' && msg.symbol.table !== '\\') {
            var s = {};
            s['background-position-x'] = -(msg.symbol.tableindex % 16) * 15 + 'px';
            s['background-position-y'] = -Math.floor(msg.symbol.tableindex / 16) * 15 + 'px';
            overlay = '<div class="aprs-symbol aprs-symboltable-overlay" style="' + stylesToString(s) + '"></div>';
        }
    } else if (msg.lat && msg.lon) {
        classes.push('openwebrx-maps-pin');
    }
    var attrs = [
        'class="' + classes.join(' ') + '"',
        'style="' + stylesToString(styles) + '"'
    ].join(' ');
    if (msg.lat && msg.lon) {
        link = '<a ' + attrs + ' href="/map?callsign=' + source + '" target="_blank">' + overlay + '</a>';
    } else {
        link = '<div ' + attrs + '>' + overlay + '</div>'
    }

    $b.append($(
        '<tr>' +
        '<td>' + timestamp + '</td>' +
        '<td class="callsign">' + source + '</td>' +
        '<td class="coord">' + link + '</td>' +
        '<td class="message">' + (msg.comment || msg.message || '') + '</td>' +
        '</tr>'
    ));
    $b.scrollTop($b[0].scrollHeight);
}

function update_digitalvoice_panels(showing) {
    $(".openwebrx-meta-panel").each(function (_, p) {
        toggle_panel(p.id, p.id === showing);
    });
    clear_metadata();
}

function clear_metadata() {
    $(".openwebrx-meta-panel .openwebrx-meta-autoclear").text("");
    $(".openwebrx-meta-slot").removeClass("active").removeClass("sync");
    $(".openwebrx-dmr-timeslot-panel").removeClass("muted");
}

var waterfall_measure_minmax = false;
var waterfall_measure_minmax_now = false;
var waterfall_measure_minmax_min = 1e100;
var waterfall_measure_minmax_max = -1e100;

function waterfall_measure_minmax_do(what) {
    waterfall_measure_minmax_min = Math.min(waterfall_measure_minmax_min, Math.min.apply(Math, what));
    waterfall_measure_minmax_max = Math.max(waterfall_measure_minmax_max, Math.max.apply(Math, what));
}

function on_ws_opened() {
    ws.send("SERVER DE CLIENT client=openwebrx.js type=receiver");
    divlog("WebSocket opened to " + ws.url);
    if (!networkSpeedMeasurement) {
        networkSpeedMeasurement = new Measurement();
        networkSpeedMeasurement.report(60000, 1000, function(rate){
            networkSpeedProgressBar.setSpeed(rate);
        });
    } else {
        networkSpeedMeasurement.reset();
    }
    reconnect_timeout = false;
    ws.send(JSON.stringify({
        "type": "dspcontrol",
        "action": "start",
        "params": {"output_rate": audioEngine.getOutputRate()}
    }));
}

var was_error = 0;

function divlog(what, is_error) {
    is_error = !!is_error;
    was_error |= is_error;
    if (is_error) {
        what = "<span class=\"webrx-error\">" + what + "</span>";
        toggle_panel("openwebrx-panel-log", true); //show panel if any error is present
    }
    e("openwebrx-debugdiv").innerHTML += what + "<br />";
    var nano = $('.nano');
    nano.nanoScroller();
    nano.nanoScroller({scroll: 'bottom'});
}

var volumeBeforeMute = 100.0;
var mute = false;

// Optimalise these if audio lags or is choppy:
var audio_buffer_maximal_length_sec = 1; //actual number of samples are calculated from sample rate

function webrx_set_param(what, value) {
    var params = {};
    params[what] = value;
    ws.send(JSON.stringify({"type": "dspcontrol", "params": params}));
}

var starting_offset_frequency;
var starting_mod;

function parseHash() {
    var h;
    if (h = window.location.hash) {
        h.substring(1).split(",").forEach(function (x) {
            var harr = x.split("=");
            if (harr[0] === "mute") toggleMute();
            else if (harr[0] === "mod") starting_mod = harr[1];
            else if (harr[0] === "sql") {
                e("openwebrx-panel-squelch").value = harr[1];
                updateSquelch();
            }
            else if (harr[0] === "freq") {
                console.log(parseInt(harr[1]));
                console.log(center_freq);
                starting_offset_frequency = parseInt(harr[1]) - center_freq;
            }
        });

    }
}

function onAudioStart(success, apiType){
    divlog('Web Audio API succesfully initialized, using ' + apiType  + ' API, sample rate: ' + audioEngine.getSampleRate() + " Hz");

    // canvas_container is set after waterfall_init() has been called. we cannot initialize before.
    if (canvas_container) initialize_demodulator();

    //hide log panel in a second (if user has not hidden it yet)
    window.setTimeout(function () {
        toggle_panel("openwebrx-panel-log", !!was_error);
    }, 2000);

    //Synchronise volume with slider
    updateVolume();
}

function initialize_demodulator() {
    demodulator_analog_replace(starting_mod);
    if (starting_offset_frequency) {
        demodulators[0].offset_frequency = starting_offset_frequency;
        e("webrx-actual-freq").innerHTML = format_frequency("{x} MHz", center_freq + starting_offset_frequency, 1e6, 4);
        demodulators[0].set();
        mkscale();
    }
}

var reconnect_timeout = false;

function on_ws_closed() {
    if (reconnect_timeout) {
        // max value: roundabout 8 and a half minutes
        reconnect_timeout = Math.min(reconnect_timeout * 2, 512000);
    } else {
        // initial value: 1s
        reconnect_timeout = 1000;
    }
    divlog("WebSocket has closed unexpectedly. Attempting to reconnect in " + reconnect_timeout / 1000 + " seconds...", 1);

    setTimeout(open_websocket, reconnect_timeout);
}

function on_ws_error() {
    divlog("WebSocket error.", 1);
}

String.prototype.startswith = function (str) {
    return this.indexOf(str) === 0;
}; //http://stackoverflow.com/questions/646628/how-to-check-if-a-string-startswith-another-string

var ws;

function open_websocket() {
    var protocol = 'ws';
    if (window.location.toString().startsWith('https://')) {
        protocol = 'wss';
    }

    var ws_url = protocol + "://" + (window.location.origin.split("://")[1]) + "/ws/"; //guess automatically -> now default behaviour
    if (!("WebSocket" in window))
        divlog("Your browser does not support WebSocket, which is required for WebRX to run. Please upgrade to a HTML5 compatible browser.");
    ws = new WebSocket(ws_url);
    ws.onopen = on_ws_opened;
    ws.onmessage = on_ws_recv;
    ws.onclose = on_ws_closed;
    ws.binaryType = "arraybuffer";
    window.onbeforeunload = function () { //http://stackoverflow.com/questions/4812686/closing-websocket-correctly-html5-javascript
        ws.onclose = function () {
        };
        ws.close();
    };
    ws.onerror = on_ws_error;
}

function waterfall_mkcolor(db_value, waterfall_colors_arg) {
    if (typeof waterfall_colors_arg === 'undefined') waterfall_colors_arg = waterfall_colors;
    if (db_value < waterfall_min_level) db_value = waterfall_min_level;
    if (db_value > waterfall_max_level) db_value = waterfall_max_level;
    var full_scale = waterfall_max_level - waterfall_min_level;
    var relative_value = db_value - waterfall_min_level;
    var value_percent = relative_value / full_scale;
    var percent_for_one_color = 1 / (waterfall_colors_arg.length - 1);
    var index = Math.floor(value_percent / percent_for_one_color);
    var remain = (value_percent - percent_for_one_color * index) / percent_for_one_color;
    return color_between(waterfall_colors_arg[index + 1], waterfall_colors_arg[index], remain);
}

function color_between(first, second, percent) {
    var output = 0;
    for (var i = 0; i < 4; i++) {
        var add = ((((first & (0xff << (i * 8))) >>> 0) * percent) + (((second & (0xff << (i * 8))) >>> 0) * (1 - percent))) & (0xff << (i * 8));
        output |= add >>> 0;
    }
    return output >>> 0;
}


var canvas_context;
var canvases = [];
var canvas_default_height = 200;
var canvas_container;
var canvas_actual_line;

function add_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = fft_size;
    new_canvas.height = canvas_default_height;
    canvas_actual_line = canvas_default_height - 1;
    new_canvas.openwebrx_top = (-canvas_default_height + 1);
    new_canvas.style.top = new_canvas.openwebrx_top.toString() + "px";
    canvas_context = new_canvas.getContext("2d");
    canvas_container.appendChild(new_canvas);
    canvases.push(new_canvas);
    while (canvas_container && canvas_container.clientHeight + canvas_default_height * 2 < canvases.length * canvas_default_height) {
        var c = canvases.shift();
        if (!c) break;
        canvas_container.removeChild(c);
    }
}


function init_canvas_container() {
    canvas_container = e("webrx-canvas-container");
    mathbox_container = e("openwebrx-mathbox-container");
    canvas_container.addEventListener("mouseleave", canvas_container_mouseleave, false);
    canvas_container.addEventListener("mousemove", canvas_mousemove, false);
    canvas_container.addEventListener("mouseup", canvas_mouseup, false);
    canvas_container.addEventListener("mousedown", canvas_mousedown, false);
    canvas_container.addEventListener("wheel", canvas_mousewheel, false);
    var frequency_container = e("openwebrx-frequency-container");
    frequency_container.addEventListener("wheel", canvas_mousewheel, false);
    add_canvas();
}

canvas_maxshift = 0;

function shift_canvases() {
    canvases.forEach(function (p) {
        p.style.top = (p.openwebrx_top++).toString() + "px";
    });
    canvas_maxshift++;
}

function resize_canvases(zoom) {
    if (typeof zoom === "undefined") zoom = false;
    if (!zoom) mkzoomlevels();
    zoom_calc();
    $('#webrx-canvas-container').css({
        width: waterfallWidth() * zoom_levels[zoom_level] + 'px',
        left: zoom_offset_px + "px"
    });
}

function waterfall_init() {
    init_canvas_container();
    resize_canvases();
    scale_setup();
    mkzoomlevels();
    waterfall_setup_done = 1;
}

var mathbox_shift = function () {
    if (mathbox_data_current_depth < mathbox_data_max_depth) mathbox_data_current_depth++;
    if (mathbox_data_index + 1 >= mathbox_data_max_depth) mathbox_data_index = 0;
    else mathbox_data_index++;
    mathbox_data_global_index++;
};

var mathbox_clear_data = function () {
    mathbox_data_index = 50;
    mathbox_data_current_depth = 0;
};

var mathbox_get_data_line = function (x) {
    return (mathbox_data_max_depth + mathbox_data_index + x - 1) % mathbox_data_max_depth;
};

var mathbox_data_index_valid = function (x) {
    return x > mathbox_data_max_depth - mathbox_data_current_depth;
};


function waterfall_add(data) {
    if (!waterfall_setup_done) return;
    var w = fft_size;

    if (waterfall_measure_minmax) waterfall_measure_minmax_do(data);
    if (waterfall_measure_minmax_now) {
        waterfall_measure_minmax_do(data);
        waterfall_measure_minmax_now = false;
        waterfallColorsAuto();
    }

    if (mathbox_mode === MATHBOX_MODES.WATERFALL) {
        //Handle mathbox
        for (var i = 0; i < fft_size; i++) mathbox_data[i + mathbox_data_index * fft_size] = data[i];
        mathbox_shift();
    } else {
        //Add line to waterfall image
        var oneline_image = canvas_context.createImageData(w, 1);
        for (var x = 0; x < w; x++) {
            var color = waterfall_mkcolor(data[x]);
            for (i = 0; i < 4; i++)
                oneline_image.data[x * 4 + i] = ((color >>> 0) >> ((3 - i) * 8)) & 0xff;
        }

        //Draw image
        canvas_context.putImageData(oneline_image, 0, canvas_actual_line--);
        shift_canvases();
        if (canvas_actual_line < 0) add_canvas();
    }


}

function check_top_bar_congestion() {
    var rmf = function (x) {
        return x.offsetLeft + x.offsetWidth;
    };
    var wet = e("webrx-rx-title");
    var wed = e("webrx-rx-desc");
    var tl = e("openwebrx-main-buttons");

    [wet, wed].map(function (what) {
        if (rmf(what) > tl.offsetLeft - 20) what.style.opacity = what.style.opacity = "0";
        else wet.style.opacity = wed.style.opacity = "1";
    });

}

var MATHBOX_MODES =
    {
        UNINITIALIZED: 0,
        NONE: 1,
        WATERFALL: 2,
        CONSTELLATION: 3
    };
var mathbox_mode = MATHBOX_MODES.UNINITIALIZED;
var mathbox;
var mathbox_element;
var mathbox_waterfall_colors;
var mathbox_waterfall_frequency_resolution;
var mathbox_waterfall_history_length;
var mathbox_correction_for_z;
var mathbox_data_max_depth;
var mathbox_data_current_depth;
var mathbox_data_index;
var mathbox_data;
var mathbox_data_global_index;
var mathbox_container;

function mathbox_init() {
    //mathbox_waterfall_history_length is defined in the config
    mathbox_data_max_depth = fft_fps * mathbox_waterfall_history_length; //how many lines can the buffer store
    mathbox_data_current_depth = 0; //how many lines are in the buffer currently
    mathbox_data_index = 0; //the index of the last empty line / the line to be overwritten
    mathbox_data = new Float32Array(fft_size * mathbox_data_max_depth);
    mathbox_data_global_index = 0;
    mathbox_correction_for_z = 0;

    mathbox = mathBox({
        plugins: ['core', 'controls', 'cursor', 'stats'],
        controls: {klass: THREE.OrbitControls}
    });
    var three = mathbox.three;
    if (typeof three === "undefined") divlog("3D waterfall cannot be initialized because WebGL is not supported in your browser.", true);

    three.renderer.setClearColor(new THREE.Color(0x808080), 1.0);
    mathbox_container.appendChild((mathbox_element = three.renderer.domElement));
    var view = mathbox
        .set({
            scale: 1080,
            focus: 3
        })
        .camera({
            proxy: true,
            position: [-2, 1, 3]
        })
        .cartesian({
            range: [[-1, 1], [0, 1], [0, 1]],
            scale: [2, 2 / 3, 1]
        });

    view.axis({
        axis: 1,
        width: 3,
        color: "#fff"
    });
    view.axis({
        axis: 2,
        width: 3,
        color: "#fff"
        //offset: [0, 0, 0],
    });
    view.axis({
        axis: 3,
        width: 3,
        color: "#fff"
    });

    view.grid({
        width: 2,
        opacity: 0.5,
        axes: [1, 3],
        zOrder: 1,
        color: "#fff"
    });

    var remap = function (x, z, t) {
        var currentTimePos = mathbox_data_global_index / (fft_fps * 1.0);
        var realZAdd = (-(t - currentTimePos) / mathbox_waterfall_history_length);
        var zAdd = realZAdd - mathbox_correction_for_z;
        if (zAdd < -0.2 || zAdd > 0.2) {
            mathbox_correction_for_z = realZAdd;
        }

        var xIndex = Math.trunc(((x + 1) / 2.0) * fft_size); //x: frequency
        var zIndex = Math.trunc(z * (mathbox_data_max_depth - 1)); //z: time
        var realZIndex = mathbox_get_data_line(zIndex);
        if (!mathbox_data_index_valid(zIndex)) return {y: undefined, dBValue: undefined, zAdd: 0};
        var index = Math.trunc(xIndex + realZIndex * fft_size);
        var dBValue = mathbox_data[index];
        var y;
        if (dBValue > waterfall_max_level) y = 1;
        else if (dBValue < waterfall_min_level) y = 0;
        else y = (dBValue - waterfall_min_level) / (waterfall_max_level - waterfall_min_level);
        if (!y) y = 0;
        return {y: y, dBValue: dBValue, zAdd: zAdd};
    };

    view.area({
        expr: function (emit, x, z, i, j, t) {
            var y;
            var remapResult = remap(x, z, t);
            if ((y = remapResult.y) === undefined) return;
            emit(x, y, z + remapResult.zAdd);
        },
        width: mathbox_waterfall_frequency_resolution,
        height: mathbox_data_max_depth - 1,
        channels: 3,
        axes: [1, 3]
    });

    view.area({
        expr: function (emit, x, z, i, j, t) {
            var dBValue;
            if ((dBValue = remap(x, z, t).dBValue) === undefined) return;
            var color = waterfall_mkcolor(dBValue, mathbox_waterfall_colors);
            var b = (color & 0xff) / 255.0;
            var g = ((color & 0xff00) >> 8) / 255.0;
            var r = ((color & 0xff0000) >> 16) / 255.0;
            emit(r, g, b, 1.0);
        },
        width: mathbox_waterfall_frequency_resolution,
        height: mathbox_data_max_depth - 1,
        channels: 4,
        axes: [1, 3]
    });

    view.surface({
        shaded: true,
        points: '<<',
        colors: '<',
        color: 0xFFFFFF
    });

    view.surface({
        fill: false,
        lineX: false,
        lineY: false,
        points: '<<',
        colors: '<',
        color: 0xFFFFFF,
        width: 2,
        blending: 'add',
        opacity: .25,
        zBias: 5
    });
    mathbox_mode = MATHBOX_MODES.NONE;

}

function mathbox_toggle() {

    if (mathbox_mode === MATHBOX_MODES.UNINITIALIZED) mathbox_init();
    mathbox_mode = (mathbox_mode === MATHBOX_MODES.NONE) ? MATHBOX_MODES.WATERFALL : MATHBOX_MODES.NONE;
    mathbox_container.style.display = (mathbox_mode === MATHBOX_MODES.WATERFALL) ? "block" : "none";
    mathbox_clear_data();
    waterfall_clear();
}

function waterfall_clear() {
    while (canvases.length) //delete all canvases
    {
        var x = canvases.shift();
        x.parentNode.removeChild(x);
    }
    add_canvas();
}

function openwebrx_resize() {
    resize_canvases();
    resize_scale();
    check_top_bar_congestion();
}

function init_header() {
    $('#openwebrx-main-buttons').find('li[data-toggle-panel]').click(function () {
        toggle_panel($(this).data('toggle-panel'));
    });
}

var audioBufferProgressBar;
var networkSpeedProgressBar;
var audioSpeedProgressBar;
var audioOutputProgressBar;
var clientProgressBar;
var cpuProgressBar;

function initProgressBars() {
    audioBufferProgressBar = new AudioBufferProgressBar($('#openwebrx-bar-audio-buffer'), audioEngine.getSampleRate());
    networkSpeedProgressBar = new NetworkSpeedProgressBar($('#openwebrx-bar-network-speed'));
    audioSpeedProgressBar = new AudioSpeedProgressBar($('#openwebrx-bar-audio-speed'));
    audioOutputProgressBar = new AudioOutputProgressBar($('#openwebrx-bar-audio-output'), audioEngine.getSampleRate());
    clientProgressBar = new ClientsProgressBar($('#openwebrx-bar-clients'));
    cpuProgressBar = new CpuProgressBar($('#openwebrx-bar-server-cpu'));
}

function audioReporter(stats) {
    if (typeof(stats.buffersize) !== 'undefined') {
        audioBufferProgressBar.setBuffersize(stats.buffersize);
    }

    if (typeof(stats.audioByteRate) !== 'undefined') {
        audioSpeedProgressBar.setSpeed(stats.audioByteRate * 8);
    }

    if (typeof(stats.audioRate) !== 'undefined') {
        audioOutputProgressBar.setAudioRate(stats.audioRate);
    }
}

var bookmarks;
var audioEngine;

function openwebrx_init() {
    audioEngine = new AudioEngine(audio_buffer_maximal_length_sec, audioReporter);
    $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.on('click', playButtonClick);
    if (!audioEngine.isAllowed()) {
        $overlay.show();
    } else {
        audioEngine.start(onAudioStart);
    }
    initProgressBars();
    init_rx_photo();
    open_websocket();
    secondary_demod_init();
    digimodes_init();
    initPanels();
    window.addEventListener("resize", openwebrx_resize);
    check_top_bar_congestion();
    init_header();
    bookmarks = new BookmarkBar();
    parseHash();
    initSliders();
	init_key_listener();
}

function init_key_listener(zEvent){
	//https://stackoverflow.com/questions/37557990/detecting-combination-keypresses-control-alt-shift
	document.addEventListener ("keydown", function (zEvent) {
    if (zEvent.ctrlKey  &&  zEvent.altKey  &&  zEvent.code === "KeyE") {
        console.log(zEvent);
    }

    // shift and +
    if ((zEvent.keyCode == "171" || zEvent.keyCode == "107") && zEvent.shiftKey){
		freqstep(4);
    }

    //shift and -
    if ((zEvent.keyCode == "109" || zEvent.keyCode == "173") && zEvent.shiftKey){
		freqstep(1);
    }

    // - and not shift
    if ((zEvent.keyCode == "109" || zEvent.keyCode == "173") &! zEvent.shiftKey){
		freqstep(2);
    }

    // + and not shift
    if ((zEvent.keyCode == "171" || zEvent.keyCode == "107") &! zEvent.shiftKey){
		freqstep(3);
    }

    //console.log(zEvent);
	} );
}

function initSliders() {
    $('#openwebrx-panel-receiver').on('wheel', 'input[type=range]', function(ev){
        var $slider = $(this);
        if (!$slider.attr('step')) return;
        var val = Number($slider.val());
        var step = Number($slider.attr('step'));
        if (ev.originalEvent.deltaY > 0) {
            step *= -1;
        }
        $slider.val(val + step);
        $slider.trigger('change');
    });
}

function digimodes_init() {
    // initialze DMR timeslot muting
    $('.openwebrx-dmr-timeslot-panel').click(function (e) {
        $(e.currentTarget).toggleClass("muted");
        update_dmr_timeslot_filtering();
    });
}

function update_dmr_timeslot_filtering() {
    var filter = $('.openwebrx-dmr-timeslot-panel').map(function (index, el) {
        return (!$(el).hasClass("muted")) << index;
    }).toArray().reduce(function (acc, v) {
        return acc | v;
    }, 0);
    webrx_set_param("dmr_filter", filter);
}

function playButtonClick() {
    //On iOS, we can only start audio from a click or touch event.
    audioEngine.start(onAudioStart);
    var $overlay = $('#openwebrx-autoplay-overlay');
    $overlay.css('opacity', 0);
    $overlay.on('transitionend', function() {
        $overlay.hide();
    });
}

var rt = function (s, n) {
    return s.replace(/[a-zA-Z]/g, function (c) {
        return String.fromCharCode((c <= "Z" ? 90 : 122) >= (c = c.charCodeAt(0) + n) ? c : c - 26);
    });
};

// ========================================================
// =======================  PANELS  =======================
// ========================================================

function panel_displayed(el){
    return !(el.style && el.style.display && el.style.display === 'none')
}

function toggle_panel(what, on) {
    var item = $('#' + what)[0];
    if (!item) return;
    var displayed = panel_displayed(item);
    if (typeof on !== "undefined" && displayed === on) {
        return;
    }
    if (item.openwebrxDisableClick) return;
    if (displayed) {
        item.movement = 'collapse';
        item.style.transform = "perspective(600px) rotateX(90deg)";
        item.style.transitionProperty = 'transform';
    } else {
        item.movement = 'expand';
        item.style.display = 'block';
        setTimeout(function(){
            item.style.transitionProperty = 'transform';
            item.style.transform = 'perspective(600px) rotateX(0deg)';
        }, 20);
    }
    item.style.transitionDuration = "600ms";
    item.style.transitionDelay = "0ms";

    item.openwebrxDisableClick = true;

}

function first_show_panel(panel) {
    panel.style.transitionDuration = 0;
    panel.style.transitionDelay = 0;
    var rotx = (Math.random() > 0.5) ? -90 : 90;
    var roty = 0;
    if (Math.random() > 0.5) {
        var rottemp = rotx;
        rotx = roty;
        roty = rottemp;
    }
    if (rotx !== 0 && Math.random() > 0.5) rotx = 270;
    panel.style.transform = "perspective(600px) rotateX(%1deg) rotateY(%2deg)"
        .replace("%1", rotx.toString()).replace("%2", roty.toString());
    window.setTimeout(function () {
        panel.style.transitionDuration = "600ms";
        panel.style.transitionDelay = (Math.floor(Math.random() * 500)).toString() + "ms";
        panel.style.transform = "perspective(600px) rotateX(0deg) rotateY(0deg)";
    }, 1);
}

function initPanels() {
    $('#openwebrx-panels-container').find('.openwebrx-panel').each(function(){
        var el = this;
        el.openwebrxPanelTransparent = (!!el.dataset.panelTransparent);
        el.addEventListener('transitionend', function(ev){
            if (ev.target !== el) return;
            el.openwebrxDisableClick = false;
            el.style.transitionDuration = null;
            el.style.transitionDelay = null;
            el.style.transitionProperty = null;
            if (el.movement && el.movement === 'collapse') {
                el.style.display = 'none';
            }
        });
        if (panel_displayed(el)) first_show_panel(el);
    });
}

function demodulator_buttons_update() {
    $(".openwebrx-demodulator-button").removeClass("highlighted");
    if (secondary_demod) {
        $("#openwebrx-button-dig").addClass("highlighted");
        $('#openwebrx-secondary-demod-listbox').val(secondary_demod);
    } else switch (demodulators[0].subtype) {
        case "lsb":
        case "usb":
        case "cw":
            if (demodulators[0].high_cut - demodulators[0].low_cut < 300)
                $("#openwebrx-button-cw").addClass("highlighted");
            else {
                if (demodulators[0].high_cut < 0)
                    $("#openwebrx-button-lsb").addClass("highlighted");
                else if (demodulators[0].low_cut > 0)
                    $("#openwebrx-button-usb").addClass("highlighted");
                else $("#openwebrx-button-lsb, #openwebrx-button-usb").addClass("highlighted");
            }
            break;
        default:
            var mod = demodulators[0].subtype;
            $("#openwebrx-button-" + mod).addClass("highlighted");
            break;
    }
}

function demodulator_analog_replace_last() {
    demodulator_analog_replace(last_analog_demodulator_subtype);
}

/*
  _____  _       _                     _
 |  __ \(_)     (_)                   | |
 | |  | |_  __ _ _ _ __ ___   ___   __| | ___  ___
 | |  | | |/ _` | | '_ ` _ \ / _ \ / _` |/ _ \/ __|
 | |__| | | (_| | | | | | | | (_) | (_| |  __/\__ \
 |_____/|_|\__, |_|_| |_| |_|\___/ \__,_|\___||___/
            __/ |
           |___/
*/

var secondary_demod = false;
var secondary_demod_fft_offset_db = 30; //need to calculate that later
var secondary_demod_canvases_initialized = false;
var secondary_demod_listbox_updating = false;
var secondary_demod_channel_freq = 1000;
var secondary_demod_waiting_for_set = false;
var secondary_demod_low_cut;
var secondary_demod_high_cut;
var secondary_demod_mousedown = false;
var secondary_demod_canvas_width;
var secondary_demod_canvas_left;
var secondary_demod_canvas_container;
var secondary_demod_current_canvas_actual_line;
var secondary_demod_current_canvas_context;
var secondary_demod_current_canvas_index;
var secondary_demod_canvases;

function demodulator_digital_replace_last() {
    demodulator_digital_replace(last_digital_demodulator_subtype);
    secondary_demod_listbox_update();
}

function demodulator_digital_replace(subtype) {
    switch (subtype) {
        case "bpsk31":
        case "rtty":
        case "ft8":
        case "jt65":
        case "jt9":
        case "ft4":
            secondary_demod_start(subtype);
            demodulator_analog_replace('usb', true);
            break;
        case "wspr":
            secondary_demod_start(subtype);
            demodulator_analog_replace('usb', true);
            // WSPR only samples between 1400 and 1600 Hz
            demodulators[0].low_cut = 1350;
            demodulators[0].high_cut = 1650;
            demodulators[0].set();
            break;
        case "packet":
            secondary_demod_start(subtype);
            demodulator_analog_replace('nfm', true);
            break;
    }
    demodulator_buttons_update();
    $('#openwebrx-panel-digimodes').attr('data-mode', subtype);
    toggle_panel("openwebrx-panel-digimodes", true);
    toggle_panel("openwebrx-panel-wsjt-message", ['ft8', 'wspr', 'jt65', 'jt9', 'ft4'].indexOf(subtype) >= 0);
    toggle_panel("openwebrx-panel-packet-message", subtype === "packet");
}

function secondary_demod_create_canvas() {
    var new_canvas = document.createElement("canvas");
    new_canvas.width = secondary_fft_size;
    new_canvas.height = $(secondary_demod_canvas_container).height();
    new_canvas.style.width = $(secondary_demod_canvas_container).width() + "px";
    new_canvas.style.height = $(secondary_demod_canvas_container).height() + "px";
    secondary_demod_current_canvas_actual_line = new_canvas.height - 1;
    $(secondary_demod_canvas_container).children().last().before(new_canvas);
    return new_canvas;
}

function secondary_demod_remove_canvases() {
    $(secondary_demod_canvas_container).children("canvas").remove();
}

function secondary_demod_init_canvases() {
    secondary_demod_remove_canvases();
    secondary_demod_canvases = [];
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases.push(secondary_demod_create_canvas());
    secondary_demod_canvases[0].openwebrx_top = -$(secondary_demod_canvas_container).height();
    secondary_demod_canvases[1].openwebrx_top = 0;
    secondary_demod_canvases_update_top();
    secondary_demod_current_canvas_context = secondary_demod_canvases[0].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
    secondary_demod_current_canvas_index = 0;
    secondary_demod_canvases_initialized = true;
    mkscale(); //so that the secondary waterfall zoom level will be initialized
}

function secondary_demod_canvases_update_top() {
    for (var i = 0; i < 2; i++) secondary_demod_canvases[i].style.top = secondary_demod_canvases[i].openwebrx_top + "px";
}

function secondary_demod_swap_canvases() {
    secondary_demod_canvases[0 + !secondary_demod_current_canvas_index].openwebrx_top -= $(secondary_demod_canvas_container).height() * 2;
    secondary_demod_current_canvas_index = 0 + !secondary_demod_current_canvas_index;
    secondary_demod_current_canvas_context = secondary_demod_canvases[secondary_demod_current_canvas_index].getContext("2d");
    secondary_demod_current_canvas_actual_line = $(secondary_demod_canvas_container).height() - 1;
}

function secondary_demod_init() {
    secondary_demod_canvas_container = $("#openwebrx-digimode-canvas-container")[0];
    $(secondary_demod_canvas_container)
        .mousemove(secondary_demod_canvas_container_mousemove)
        .mouseup(secondary_demod_canvas_container_mouseup)
        .mousedown(secondary_demod_canvas_container_mousedown)
        .mouseenter(secondary_demod_canvas_container_mousein)
        .mouseleave(secondary_demod_canvas_container_mouseleave);
    init_digital_removal_timer();
}

function secondary_demod_start(subtype) {
    secondary_demod_canvases_initialized = false;
    ws.send(JSON.stringify({"type": "dspcontrol", "params": {"secondary_mod": subtype}}));
    secondary_demod = subtype;
}

function secondary_demod_stop() {
    ws.send(JSON.stringify({"type": "dspcontrol", "params": {"secondary_mod": false}}));
    secondary_demod = false;
}

function secondary_demod_push_data(x) {
    x = Array.from(x).filter(function (y) {
        var c = y.charCodeAt(0);
        return (c === 10 || (c >= 32 && c <= 126));
    }).map(function (y) {
        if (y === "&")
            return "&amp;";
        if (y === "<") return "&lt;";
        if (y === ">") return "&gt;";
        if (y === " ") return "&nbsp;";
        return y;
    }).map(function (y) {
        if (y === "\n")
            return "<br />";
        return "<span class=\"part\">" + y + "</span>";
    }).join("");
    $("#openwebrx-cursor-blink").before(x);
}

function secondary_demod_close_window() {
    secondary_demod_stop();
    toggle_panel("openwebrx-panel-digimodes", false);
    toggle_panel("openwebrx-panel-wsjt-message", false);
    toggle_panel("openwebrx-panel-packet-message", false);
}

function secondary_demod_waterfall_add(data) {
    if (!secondary_demod) return;
    var w = secondary_fft_size;

    //Add line to waterfall image
    var oneline_image = secondary_demod_current_canvas_context.createImageData(w, 1);
    for (var x = 0; x < w; x++) {
        var color = waterfall_mkcolor(data[x] + secondary_demod_fft_offset_db);
        for (var i = 0; i < 4; i++) oneline_image.data[x * 4 + i] = ((color >>> 0) >> ((3 - i) * 8)) & 0xff;
    }

    //Draw image
    secondary_demod_current_canvas_context.putImageData(oneline_image, 0, secondary_demod_current_canvas_actual_line--);
    secondary_demod_canvases.map(function (x) {
        x.openwebrx_top += 1;
    })
    ;
    secondary_demod_canvases_update_top();
    if (secondary_demod_current_canvas_actual_line < 0) secondary_demod_swap_canvases();
}

function secondary_demod_listbox_changed() {
    if (secondary_demod_listbox_updating) return;
    var sdm = $("#openwebrx-secondary-demod-listbox")[0].value;
    if (sdm === "none") {
        demodulator_analog_replace_last();
    } else {
        demodulator_digital_replace(sdm);
    }
}

function secondary_demod_listbox_update() {
    secondary_demod_listbox_updating = true;
    $("#openwebrx-secondary-demod-listbox").val((secondary_demod) ? secondary_demod : "none");
    secondary_demod_listbox_updating = false;
}

function secondary_demod_update_marker() {
    var width = Math.max((secondary_bw / (if_samp_rate / 2)) * secondary_demod_canvas_width, 5);
    var center_at = (secondary_demod_channel_freq / (if_samp_rate / 2)) * secondary_demod_canvas_width + secondary_demod_canvas_left;
    var left = center_at - width / 2;
    $("#openwebrx-digimode-select-channel").width(width).css("left", left + "px")
}

function secondary_demod_update_channel_freq_from_event(evt) {
    if (typeof evt !== "undefined") {
        var relativeX = (evt.offsetX) ? evt.offsetX : evt.layerX;
        secondary_demod_channel_freq = secondary_demod_low_cut +
            (relativeX / $(secondary_demod_canvas_container).width()) * (secondary_demod_high_cut - secondary_demod_low_cut);
    }
    if (!secondary_demod_waiting_for_set) {
        secondary_demod_waiting_for_set = true;
        window.setTimeout(function () {
                ws.send(JSON.stringify({
                    "type": "dspcontrol",
                    "params": {"secondary_offset_freq": Math.floor(secondary_demod_channel_freq)}
                }));
                secondary_demod_waiting_for_set = false;
            },
            50
        )
        ;
    }
    secondary_demod_update_marker();
}

function secondary_demod_canvas_container_mousein() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0.7"); //.css("border-width", "1px");
}

function secondary_demod_canvas_container_mouseleave() {
    $("#openwebrx-digimode-select-channel").css("opacity", "0");
}

function secondary_demod_canvas_container_mousemove(evt) {
    if (secondary_demod_mousedown) secondary_demod_update_channel_freq_from_event(evt);
}

function secondary_demod_canvas_container_mousedown(evt) {
    if (evt.which === 1) secondary_demod_mousedown = true;
}

function secondary_demod_canvas_container_mouseup(evt) {
    if (evt.which === 1) secondary_demod_mousedown = false;
    secondary_demod_update_channel_freq_from_event(evt);
}


function secondary_demod_waterfall_set_zoom(low_cut, high_cut) {
    if (!secondary_demod || !secondary_demod_canvases_initialized) return;
    if (low_cut < 0 && high_cut < 0) {
        var hctmp = high_cut;
        var lctmp = low_cut;
        low_cut = -hctmp;
        high_cut = -lctmp;
    }
    else if (low_cut < 0 && high_cut > 0) {
        high_cut = Math.max(Math.abs(high_cut), Math.abs(low_cut));
        low_cut = 0;
    }
    secondary_demod_low_cut = low_cut;
    secondary_demod_high_cut = high_cut;
    var shown_bw = high_cut - low_cut;
    secondary_demod_canvas_width = $(secondary_demod_canvas_container).width() * (if_samp_rate / 2) / shown_bw;
    secondary_demod_canvas_left = -secondary_demod_canvas_width * (low_cut / (if_samp_rate / 2));
    //console.log("setzoom", secondary_demod_canvas_width, secondary_demod_canvas_left, low_cut, high_cut);
    secondary_demod_canvases.map(function (x) {
        $(x).css("left", secondary_demod_canvas_left + "px").css("width", secondary_demod_canvas_width + "px");
    })
    ;
    secondary_demod_update_channel_freq_from_event();
}

function sdr_profile_changed() {
    var value = $('#openwebrx-sdr-profiles-listbox').val();
    ws.send(JSON.stringify({type: "selectprofile", params: {profile: value}}));
}
