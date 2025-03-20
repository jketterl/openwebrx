function MessagePanel(el) {
    this.el = el;
    this.render();
    this.initClearButton();
}

MessagePanel.prototype.supportsMessage = function(message) {
    return false;
};

MessagePanel.prototype.render = function() {
};

MessagePanel.prototype.pushMessage = function(message) {
};

// automatic clearing is not enabled by default. call this method from the constructor to enable
MessagePanel.prototype.initClearTimer = function() {
    var me = this;
    if (me.removalInterval) clearInterval(me.removalInterval);
    me.removalInterval = setInterval(function () {
        me.clearMessages(1000);
    }, 15000);
};

MessagePanel.prototype.clearMessages = function(toRemain) {
    var $elements = $(this.el).find('tbody tr');
    // limit to 1000 entries in the list since browsers get laggy at some point
    var toRemove = $elements.length - toRemain;
    if (toRemove <= 0) return;
    $elements.slice(0, toRemove).remove();
};

MessagePanel.prototype.initClearButton = function() {
    var me = this;
    me.clearButton = $(
        '<div class="openwebrx-button">Clear</div>'
    );
    me.clearButton.css({
        position: 'absolute',
        top: '10px',
        right: '10px'
    });
    me.clearButton.on('click', function() {
        me.clearMessages(0);
    });
    $(me.el).append(me.clearButton);
};

MessagePanel.prototype.htmlEscape = function(input) {
    return $('<div/>').text(input).html()
};

MessagePanel.prototype.scrollToBottom = function() {
    var $t = $(this.el).find('table');
    $t.scrollTop($t[0].scrollHeight);
};

function WsjtMessagePanel(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
    this.qsoModes = ['FT8', 'JT65', 'JT9', 'JT4', 'FT4', 'FST4', 'Q65', 'MSK144'];
    this.beaconModes = ['WSPR', 'FST4W'];
    this.modes = [].concat(this.qsoModes, this.beaconModes);
}

WsjtMessagePanel.prototype = Object.create(MessagePanel.prototype);

WsjtMessagePanel.prototype.supportsMessage = function(message) {
    return this.modes.indexOf(message['mode']) >= 0;
};

WsjtMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th>UTC</th>' +
                '<th class="decimal">dB</th>' +
                '<th class="decimal">DT</th>' +
                '<th class="decimal freq">Freq</th>' +
                '<th class="message">Message</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

WsjtMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    var t = new Date(msg['timestamp']);
    var pad = function (i) {
        return ('' + i).padStart(2, "0");
    };
    var linkedmsg = msg['msg'];
    var matches;

    if (this.qsoModes.indexOf(msg['mode']) >= 0) {
        matches = linkedmsg.match(/(.*\s[A-Z0-9]+\s)([A-R]{2}[0-9]{2})$/);
        if (matches && matches[2] !== 'RR73') {
            linkedmsg = this.htmlEscape(matches[1]) + '<a href="map?locator=' + matches[2] + '" target="openwebrx-map">' + matches[2] + '</a>';
        } else {
            linkedmsg = this.htmlEscape(linkedmsg);
        }
    } else if (this.beaconModes.indexOf(msg['mode']) >= 0) {
        matches = linkedmsg.match(/([A-Z0-9]*\s)([A-R]{2}[0-9]{2})(\s[0-9]+)/);
        if (matches) {
            linkedmsg = this.htmlEscape(matches[1]) + '<a href="map?locator=' + matches[2] + '" target="openwebrx-map">' + matches[2] + '</a>' + this.htmlEscape(matches[3]);
        } else {
            linkedmsg = this.htmlEscape(linkedmsg);
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
    this.scrollToBottom();
}

$.fn.wsjtMessagePanel = function(){
    if (!this.data('panel')) {
        this.data('panel', new WsjtMessagePanel(this));
    }
    return this.data('panel');
};

function PacketMessagePanel(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

PacketMessagePanel.prototype = Object.create(MessagePanel.prototype);

PacketMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'APRS';
};

PacketMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th>UTC</th>' +
                '<th class="callsign">Callsign</th>' +
                '<th class="coord">Coord</th>' +
                '<th class="message">Comment</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

PacketMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    var pad = function (i) {
        return ('' + i).padStart(2, "0");
    };

    if (msg.type && msg.type === 'thirdparty' && msg.data) {
        msg = msg.data;
    }

    var source = msg.source;
    var callsign;
    if ('object' in source) {
        callsign = source.object;
    } else if ('item' in source) {
        callsign = source.item;
    } else {
        callsign = source.callsign;
        if ('ssid' in source) {
            callsign += '-' + source.ssid;
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
        overlay = '<svg viewBox="0 0 20 35"><use xlink:href="static/gfx/svg-defs.svg#maps-pin"></use></svg>';
    }
    var attrs = [
        'class="' + classes.join(' ') + '"',
        'style="' + stylesToString(styles) + '"'
    ].join(' ');
    if (msg.lat && msg.lon) {
        link = '<a ' + attrs + ' href="map?' + new URLSearchParams(source).toString() + '" target="openwebrx-map">' + overlay + '</a>';
    } else {
        link = '<div ' + attrs + '>' + overlay + '</div>'
    }

    $b.append($(
        '<tr>' +
        '<td>' + timestamp + '</td>' +
        '<td class="callsign">' + callsign + '</td>' +
        '<td class="coord">' + link + '</td>' +
        '<td class="message">' + this.htmlEscape(msg.comment || msg.message || '') + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.packetMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new PacketMessagePanel(this));
    }
    return this.data('panel');
};

PocsagMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
}

PocsagMessagePanel.prototype = Object.create(MessagePanel.prototype);

PocsagMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'Pocsag';
};

PocsagMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="address">Address</th>' +
                '<th class="message">Message</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

PocsagMessagePanel.prototype.pushMessage = function(msg) {
    var $b = $(this.el).find('tbody');
    $b.append($(
        '<tr>' +
            '<td class="address">' + msg.address + '</td>' +
            '<td class="message">' + this.htmlEscape(msg.message) + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.pocsagMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new PocsagMessagePanel(this));
    }
    return this.data('panel');
};

AdsbMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.aircraft = {}
    this.aircraftTrackingService = false;
    this.initClearTimer();
}

AdsbMessagePanel.prototype = Object.create(MessagePanel.prototype);

AdsbMessagePanel.prototype.supportsMessage = function(message) {
    return message["mode"] === "ADSB";
};

AdsbMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="address">ICAO</th>' +
                '<th class="callsign">Flight</th>' +
                '<th class="altitude">Altitude</th>' +
                '<th class="speed">Speed</th>' +
                '<th class="track">Track</th>' +
                '<th class="verticalspeed">V/S</th>' +
                '<th class="position">Position</th>' +
                '<th class="messages">Messages</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};


AdsbMessagePanel.prototype.pushMessage = function(message) {
    if (!('icao' in message)) return;
    if (!(message.icao in this.aircraft)) {
        var el = $("<tr>");
        $(this.el).find('tbody').append(el);
        this.aircraft[message.icao] = {
            el: el,
            messages: 0
        }
    }
    var state = this.aircraft[message.icao];
    Object.assign(state, message);
    state.lastSeen = Date.now();
    state.messages += 1;

    var ifDefined = function(input, formatter) {
        if (typeof(input) !== 'undefined') {
            if (formatter) return formatter(input);
            return input;
        }
        return "";
    }

    var coordRound = function(i) {
        return Math.round(i * 1000) / 1000;
    }

    var getPosition = function(state) {
        if (!('lat' in state) || !('lon') in state) return '';
        return '<a href="map?icao=' + state.icao + '" target="openwebrx-map">' + coordRound(state.lat) + ', ' + coordRound(state.lon) + '</a>';
    }

    state.el.html(
        '<td>' + this.linkify(state, state.icao) + '</td>' +
        '<td>' + this.linkify(state, ifDefined(state.identification)) + '</td>' +
        '<td>' + ifDefined(state.altitude) + '</td>' +
        '<td>' + ifDefined(state.groundspeed || state.IAS || state.TAS, Math.round) + '</td>' +
        '<td>' + ifDefined(state.groundtrack || state.heading, Math.round) + '</td>' +
        '<td>' + ifDefined(state.verticalspeed) + '</td>' +
        '<td>' + getPosition(state) + '</td>' +
        '<td>' + state.messages + '</td>'
    );
};

AdsbMessagePanel.prototype.clearMessages = function(toRemain) {
    var now = Date.now();
    var me = this;
    Object.entries(this.aircraft).forEach(function(e) {
        if (now - e[1].lastSeen > toRemain) {
            delete me.aircraft[e[0]];
            e[1].el.remove();
        }
    })
};

AdsbMessagePanel.prototype.initClearTimer = function() {
    var me = this;
    if (me.removalInterval) clearInterval(me.removalInterval);
    me.removalInterval = setInterval(function () {
        me.clearMessages(30000);
    }, 15000);
};

AdsbMessagePanel.prototype.setAircraftTrackingService = function(service) {
    this.aircraftTrackingService = service;
};

AdsbMessagePanel.prototype.linkify = function(state, text) {
    var link = false;
    switch (this.aircraftTrackingService) {
        case 'flightaware':
            link = 'https://flightaware.com/live/modes/' + state.icao;
            if (state.identification) link += "/ident/" + state.identification
            link += '/redirect';
            break;
        case 'planefinder':
            if (state.identification) link = 'https://planefinder.net/flight/' + state.identification;
            break;
    }
    if (link) {
        return '<a target="_blank" href="' + link + '">' + text + '</a>';
    }
    return text;

};

$.fn.adsbMessagePanel = function () {
    if (!this.data('panel')) {
        this.data('panel', new AdsbMessagePanel(this));
    }
    return this.data('panel');
};

IsmMessagePanel = function(el) {
    MessagePanel.call(this, el);
    this.initClearTimer();
};

IsmMessagePanel.prototype = Object.create(MessagePanel.prototype);

IsmMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'ISM';
};

IsmMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="model">Model</th>' +
                '<th class="id">ID</th>' +
                '<th class="channel">Channel</th>' +
                '<th class="data">Data</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));

};

IsmMessagePanel.prototype.pushMessage = function(message) {
    var $b = $(this.el).find('tbody');

    var ifDefined = function(input, formatter) {
        if (typeof(input) !== 'undefined') {
            if (formatter) return formatter(input);
            return input;
        }
        return "";
    }

    var mergeRemainingMessage = function(input, exclude) {
        return Object.entries(input).map(function(entry) {
            if (exclude.includes(entry[0])) return '';
            return entry[0] + ': ' + entry[1] + ';';
        }).join(' ');
    }

    $b.append($(
        '<tr>' +
            '<td class="model">' + ifDefined(message.model) + '</td>' +
            '<td class="id">' + ifDefined(message.id) + '</td>' +
            '<td class="channel">' + ifDefined(message.channel) + '</td>' +
            '<td class="data">' + this.htmlEscape(mergeRemainingMessage(message, ['model', 'id', 'channel', 'mode', 'time'])) + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.ismMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new IsmMessagePanel(this));
    }
    return this.data('panel');
};

AircraftMessagePanel = function(el) {
    MessagePanel.call(this, el);
}

AircraftMessagePanel.prototype = Object.create(MessagePanel.prototype);

AircraftMessagePanel.prototype.renderAcars = function(acars) {
    if (acars['more']) {
        return '<h4>Partial ACARS message</h4>';
    }
    var details = '<h4>ACARS message</h4>';
    if ('flight' in acars) {
        details += '<div>Flight: ' + this.handleFlight(acars['flight']) + '</div>';
    }
    details += '<div>Registration: ' + acars['reg'].replace(/^\.+/g, '') + '</div>';
    if ('media-adv' in acars) {
        details += '<div>Media advisory</div>';
        var mediaadv = acars['media-adv'];
        if ('current_link' in mediaadv) {
            details += '<div>Current link: ' + mediaadv['current_link']['descr'];
        }
        if ('links_avail' in mediaadv) {
            details += '<div>Available links: ' + mediaadv['links_avail'].map(function (l) {
                return l['descr'];
            }).join(', ') + '</div>';
        }
    } else if ('arinc622' in acars) {
        var arinc622 = acars['arinc622'];
        if ('adsc' in arinc622) {
            var adsc = arinc622['adsc'];
            if ('tags' in adsc) {
                adsc['tags'].forEach(function(tag) {
                    if ('basic_report' in tag) {
                        var basic_report = tag['basic_report'];
                        details += '<div>Basic ADS-C report</div>';
                        details += '<div>Position: ' + basic_report['lat'] + ', ' + basic_report['lon'] + '</div>';
                        details += '<div>Altitude: ' + basic_report['alt'] + '</div>';
                    } else if ('earth_ref_data' in tag) {
                        var earth_ref_data = tag['earth_ref_data'];
                        details += '<div>Track: ' + earth_ref_data['true_trk_deg'] + '</div>';
                        details += '<div>Speed: ' + earth_ref_data['gnd_spd_kts'] + ' kt</div>';
                        details += '<div>Vertical speed: ' + earth_ref_data['vspd_ftmin'] + ' ft/min</div>';
                    } else if ('cancel_all_contracts' in tag) {
                        details += '<div>Cancel all ADS-C contracts</div>';
                    } else if ('cancel_contract' in tag) {
                        details += '<div>Cancel ADS-C contract</div>';
                    } else {
                        details += '<div>Unsupported tag</div>';
                    }
                });
            } else {
                details += '<div>Other ADS-C data</div>';
            }
        }
    } else {
        // plain text
        details += '<div>Label: ' + acars['label'] + '</div>';
        details += '<div class="acars-message">' + acars['msg_text'] + '</div>';
    }
    return details;
};

AircraftMessagePanel.prototype.handleFlight = function(raw) {
    return raw.replace(/^([0-9A-Z]{2})0*([0-9A-Z]+$)/, '$1$2');
};

HfdlMessagePanel = function(el) {
    AircraftMessagePanel.call(this, el);
    this.initClearTimer();
}

HfdlMessagePanel.prototype = Object.create(AircraftMessagePanel.prototype);

HfdlMessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="source">Source</th>' +
                '<th class="destination">Destination</th>' +
                '<th class="details">Details</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

HfdlMessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'HFDL';
};

HfdlMessagePanel.prototype.renderPosition = function(hfnpdu) {
    if ('pos' in hfnpdu) {
        var pos = hfnpdu['pos'];
        var lat = pos['lat'] || 180;
        var lon = pos['lon'] || 180;
        if (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
            return '<div>Position: ' + pos['lat'] + ', ' + pos['lon'] + '</div>';
        }
    }
    return '';
};

HfdlMessagePanel.prototype.renderLogon = function(lpdu) {
    var details = ''
    if (lpdu['ac_info'] && lpdu['ac_info']['icao']) {
        details += '<div>ICAO: ' + lpdu['ac_info']['icao'] + '</div>';
    }
    if (lpdu['hfnpdu']) {
        var hfnpdu = lpdu['hfnpdu'];
        if (hfnpdu['flight_id'] && hfnpdu['flight_id'] !== '') {
            details += '<div>Flight: ' + this.handleFlight(lpdu['hfnpdu']['flight_id']) + '</div>'
        }
        details += this.renderPosition(hfnpdu);
    }
    return details;
};

HfdlMessagePanel.prototype.pushMessage = function(message) {
    var $b = $(this.el).find('tbody');

    var src = '';
    var dst = '';
    var details = JSON.stringify(message);

    var renderAddress = function(a) {
        return a['id'];
    }

    // TODO remove safety net once parsing is complete
    try {
        var payload = message['hfdl'];
        if ('spdu' in payload) {
            var spdu = payload['spdu'];
            src = renderAddress(spdu['src']);
            details = '<h4>HFDL Squitter message</h4>'
            details += '<div>Systable version: ' + spdu['systable_version'] + '</div>';

            if ('gs_status' in spdu) {
                details += spdu['gs_status'].map(function(gs){
                    return '<div>Ground station ' + gs['gs']['id'] + ' is operating on frequency ids ' + gs['freqs'].map(function(f) {return f['id']; }).join(', ') + '</div>';
                }).join('')
            }
        } else if ('lpdu' in payload) {
            var lpdu = payload['lpdu'];
            src = renderAddress(lpdu['src']);
            dst = renderAddress(lpdu['dst']);
            if (lpdu['type']['id'] === 13 || lpdu['type']['id'] === 29) {
                // unnumbered data
                var hfnpdu = lpdu['hfnpdu'];
                if (hfnpdu['type']['id'] === 209) {
                    // performance data
                    details = '<h4>Performance data</h4>';
                    details += '<div>Flight: ' + this.handleFlight(hfnpdu['flight_id']) + '</div>';
                    details += this.renderPosition(hfnpdu);
                } else if (hfnpdu['type']['id'] === 255) {
                    // enveloped data
                    if ('acars' in hfnpdu) {
                        details = this.renderAcars(hfnpdu['acars']);
                    }
                }
            } else if (lpdu['type']['id'] === 47) {
                // logon denied
                details = '<h4>Logon denied</h4>';
            } else if (lpdu['type']['id'] === 63) {
                details = '<h4>Logoff request</h4>';
                if (lpdu['ac_info'] && lpdu['ac_info']['icao']) {
                    details += '<div>ICAO: ' + lpdu['ac_info']['icao'] + '</div>';
                }
            } else if (lpdu['type']['id'] === 79) {
                details = '<h4>Logon resume</h4>';
                details += this.renderLogon(lpdu);
            } else if (lpdu['type']['id'] === 95) {
                details = '<h4>Logon resume confirmation</h4>';
            } else if (lpdu['type']['id'] === 143) {
                details = '<h4>Logon request</h4>';
                details += this.renderLogon(lpdu);
            } else if (lpdu['type']['id'] === 159) {
                details = '<h4>Logon confirmation</h4>';
                if (lpdu['ac_info'] && lpdu['ac_info']['icao']) {
                    details += '<div>ICAO: ' + lpdu['ac_info']['icao'] + '</div>';
                }
                if (lpdu['assigned_ac_id']) {
                    details += '<div>Assigned aircraft ID: ' + lpdu['assigned_ac_id'] + '</div>';
                }
            } else if (lpdu['type']['id'] === 191) {
                details = '<h4>Logon request (DLS)</h4>';
                details += this.renderLogon(lpdu);
            }
        }
    } catch (e) {
        console.error(e, e.stack);
    }

    $b.append($(
        '<tr>' +
            '<td class="source">' + src + '</td>' +
            '<td class="destination">' + dst + '</td>' +
            '<td class="details">' + details + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

$.fn.hfdlMessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new HfdlMessagePanel(this));
    }
    return this.data('panel');
};

Vdl2MessagePanel = function(el) {
    AircraftMessagePanel.call(this, el);
    this.initClearTimer();
}

Vdl2MessagePanel.prototype = Object.create(AircraftMessagePanel.prototype);

Vdl2MessagePanel.prototype.render = function() {
    $(this.el).append($(
        '<table>' +
            '<thead><tr>' +
                '<th class="source">Source</th>' +
                '<th class="destination">Destination</th>' +
                '<th class="details">Details</th>' +
            '</tr></thead>' +
            '<tbody></tbody>' +
        '</table>'
    ));
};

Vdl2MessagePanel.prototype.supportsMessage = function(message) {
    return message['mode'] === 'VDL2';
};

Vdl2MessagePanel.prototype.pushMessage = function(message) {
    var $b = $(this.el).find('tbody');
    var src = '';
    var dst = '';
    var details = JSON.stringify(message);

    var renderAddress = function(a) {
        return '<div>' + a['addr'] + '</div><div>' + a['type'] + ( 'status' in a ? ' (' + a['status'] + ')' : '' ) + '</div>'
    }

    // TODO remove safety net once parsing is complete
    try {
        var payload = message['vdl2'];
        if ('avlc' in payload) {
            var avlc = payload['avlc'];
            src = renderAddress(avlc['src']);
            dst = renderAddress(avlc['dst']);

            if (avlc['frame_type'] === 'S') {
                details = '<h4>Supervisory frame</h4>';
                if (avlc['cmd'] === 'Receive Ready') {
                    details = '<h4>Receive Ready</h4>';
                }
            } else if (avlc['frame_type'] === 'I') {
                details = '<h4>Information frame</h4>';
                if ('acars' in avlc) {
                    details = this.renderAcars(avlc['acars']);
                } else if ('x25' in avlc) {
                    var x25 = avlc['x25'];
                    if (!('reasm_status' in x25) || ['skipped', 'complete'].includes(x25['reasm_status'])) {
                        details = '<h4>X.25 frame</h4>';
                        if ('clnp' in x25) {
                            var clnp = x25['clnp']
                            if ('cotp' in clnp) {
                                var cotp = clnp['cotp'];
                                if ('cpdlc' in cotp) {
                                    var cpdlc = cotp['cpdlc'];
                                    details = '<h4>CPDLC</h4>';
                                    if ('atc_downlink_message' in cpdlc) {
                                        var atc_downlink_message = cpdlc['atc_downlink_message'];
                                        if ('msg_data' in atc_downlink_message) {
                                            var msg_data = atc_downlink_message['msg_data'];
                                            if ('msg_elements' in msg_data) {
                                                details += '<div>' + msg_data['msg_elements'].map(function(e) { return e['msg_element']['choice_label']; }).join(', ') + '</div>';
                                            }
                                        } else {
                                            details += '<div>' + JSON.stringify(cpdlc) + '</div>';
                                        }
                                    }
                                }
                                if ('adsc_v2' in cotp) {
                                    var adsc_v2 = cotp['adsc_v2']
                                    details = '<h4>ADS-C v2 Frame</h4>';
                                    if ('adsc_report' in adsc_v2) {
                                        var adsc_report = adsc_v2['adsc_report'];
                                        var data = adsc_report['data'];
                                        if ('periodic_report' in data) {
                                            details += '<div>Periodic report</div>';
                                            details += this.processReport(data['periodic_report']['report_data']);
                                        } else if ('event_report' in data) {
                                            details += '<div>Event report</div>';
                                            details += this.processReport(data['event_report']['report_data']);
                                        }
                                    }
                                }
                            }
                        }
                    } else {
                        details = '<h4>Partial X.25 frame</h4>';
                    }
                }
            } else if (avlc['frame_type'] === 'U') {
                details = '<h4>Unnumbered frame</h4>';
                if ('xid' in avlc) {
                    var xid = avlc['xid'];
                    details = '<h4>' + xid['type_descr'] + '</h4>';
                }
            }
        }
    } catch (e) {
        console.error(e, e.stack);
    }

    $b.append($(
        '<tr>' +
            '<td class="source">' + src + '</td>' +
            '<td class="destination">' + dst + '</td>' +
            '<td class="details">' + details + '</td>' +
        '</tr>'
    ));
    this.scrollToBottom();
};

Vdl2MessagePanel.prototype.processReport = function(report) {
    var details = '';
    if ('position' in report) {
        var position = report['position'];
        var lat = position['lat']
        var lon = position['lon']
        details += '<div>Position: ' +
            lat['deg'] + '° ' + lat['min'] + '\' ' + lat['sec'] + '" ' + lat['dir'] + ', ' +
            lon['deg'] + '° ' + lon['min'] + '\' ' + lon['sec'] + '" ' + lon['dir'] +
            '</div>';
        details += '<div>Altitude: ' + position['alt']['val'] + ' ' + position['alt']['unit'] + '</div>';
    }
    return details;
}

$.fn.vdl2MessagePanel = function() {
    if (!this.data('panel')) {
        this.data('panel', new Vdl2MessagePanel(this));
    }
    return this.data('panel');
};
