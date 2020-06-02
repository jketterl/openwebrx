(function(){
    var query = window.location.search.replace(/^\?/, '').split('&').map(function(v){
        var s = v.split('=');
        var r = {};
        r[s[0]] = s.slice(1).join('=');
        return r;
    }).reduce(function(a, b){
        return a.assign(b);
    });

    var expectedCallsign;
    if (query.callsign) expectedCallsign = query.callsign;
    var expectedLocator;
    if (query.locator) expectedLocator = query.locator;

    var protocol = window.location.protocol.match(/https/) ? 'wss' : 'ws';

    var href = window.location.href;
    var index = href.lastIndexOf('/');
    if (index > 0) {
        href = href.substr(0, index + 1);
    }
    href = href.split("://")[1];
    href = protocol + "://" + href;
    if (!href.endsWith('/')) {
        href += '/';
    }
    var ws_url = href + "ws/";

    var map;
    var markers = {};
    var rectangles = {};
    var updateQueue = [];

    // reasonable default; will be overriden by server
    var retention_time = 2 * 60 * 60 * 1000;
    var strokeOpacity = 0.8;
    var fillOpacity = 0.35;

    var colorKeys = {};
    var colorScale = chroma.scale(['red', 'blue', 'green']).mode('hsl');
    var getColor = function(id){
        if (!id) return "#000000";
        if (!colorKeys[id]) {
            var keys = Object.keys(colorKeys);
            keys.push(id);
            keys.sort();
            var colors = colorScale.colors(keys.length);
            colorKeys = {};
            keys.forEach(function(key, index) {
                colorKeys[key] = colors[index];
            });
            reColor();
            updateLegend();
        }
        return colorKeys[id];
    }

    // when the color palette changes, update all grid squares with new color
    var reColor = function() {
        $.each(rectangles, function(_, r) {
            var color = getColor(colorAccessor(r));
            r.setOptions({
                strokeColor: color,
                fillColor: color
            });
        });
    }

    var colorMode = 'byband';
    var colorAccessor = function(r) {
        switch (colorMode) {
            case 'byband':
                return r.band;
            case 'bymode':
                return r.mode;
        }
    };

    $(function(){
        $('#openwebrx-map-colormode').on('change', function(){
            colorMode = $(this).val();
            colorKeys = {};
            reColor();
            updateLegend();
        });
    });

    var updateLegend = function() {
        var lis = $.map(colorKeys, function(value, key) {
            return '<li class="square"><span class="illustration" style="background-color:' + chroma(value).alpha(fillOpacity) + ';border-color:' + chroma(value).alpha(strokeOpacity) + ';"></span>' + key + '</li>';
        });
        $(".openwebrx-map-legend .content").html('<ul>' + lis.join('') + '</ul>');
    }

    var processUpdates = function(updates) {
        if (typeof(AprsMarker) == 'undefined') {
            updateQueue = updateQueue.concat(updates);
            return;
        }
        updates.forEach(function(update){

            switch (update.location.type) {
                case 'latlon':
                    var pos = new google.maps.LatLng(update.location.lat, update.location.lon);
                    var marker;
                    var markerClass = google.maps.Marker;
                    var aprsOptions = {}
                    if (update.location.symbol) {
                        markerClass = AprsMarker;
                        aprsOptions.symbol = update.location.symbol;
                        aprsOptions.course = update.location.course;
                        aprsOptions.speed = update.location.speed;
                    }
                    if (markers[update.callsign]) {
                        marker = markers[update.callsign];
                    } else {
                        marker = new markerClass();
                        marker.addListener('click', function(){
                            showMarkerInfoWindow(update.callsign, pos);
                        });
                        markers[update.callsign] = marker;
                    }
                    marker.setOptions($.extend({
                        position: pos,
                        map: map,
                        title: update.callsign
                    }, aprsOptions, getMarkerOpacityOptions(update.lastseen) ));
                    marker.lastseen = update.lastseen;
                    marker.mode = update.mode;
                    marker.band = update.band;
                    marker.comment = update.location.comment;

                    // TODO the trim should happen on the server side
                    if (expectedCallsign && expectedCallsign == update.callsign.trim()) {
                        map.panTo(pos);
                        showMarkerInfoWindow(update.callsign, pos);
                        expectedCallsign = false;
                    }

                    if (infowindow && infowindow.callsign && infowindow.callsign == update.callsign.trim()) {
                        showMarkerInfoWindow(infowindow.callsign, pos);
                    }
                break;
                case 'locator':
                    var loc = update.location.locator;
                    var lat = (loc.charCodeAt(1) - 65 - 9) * 10 + Number(loc[3]);
                    var lon = (loc.charCodeAt(0) - 65 - 9) * 20 + Number(loc[2]) * 2;
                    var center = new google.maps.LatLng({lat: lat + .5, lng: lon + 1});
                    var rectangle;
                    // the accessor is designed to work on the rectangle... but it should work on the update object, too
                    var color = getColor(colorAccessor(update));
                    if (rectangles[update.callsign]) {
                        rectangle = rectangles[update.callsign];
                    } else {
                        rectangle = new google.maps.Rectangle();
                        rectangle.addListener('click', function(){
                            showLocatorInfoWindow(this.locator, this.center);
                        });
                        rectangles[update.callsign] = rectangle;
                    }
                    rectangle.setOptions($.extend({
                        strokeColor: color,
                        strokeWeight: 2,
                        fillColor: color,
                        map: map,
                        bounds:{
                            north: lat,
                            south: lat + 1,
                            west: lon,
                            east: lon + 2
                        }
                    }, getRectangleOpacityOptions(update.lastseen) ));
                    rectangle.lastseen = update.lastseen;
                    rectangle.locator = update.location.locator;
                    rectangle.mode = update.mode;
                    rectangle.band = update.band;
                    rectangle.center = center;

                    if (expectedLocator && expectedLocator == update.location.locator) {
                        map.panTo(center);
                        showLocatorInfoWindow(expectedLocator, center);
                        expectedLocator = false;
                    }

                    if (infowindow && infowindow.locator && infowindow.locator == update.location.locator) {
                        showLocatorInfoWindow(infowindow.locator, center);
                    }
                break;
            }
        });
    };

    var clearMap = function(){
        var reset = function(callsign, item) { item.setMap(); };
        $.each(markers, reset);
        $.each(rectangles, reset);
        markers = {};
        rectangles = {};
    };

    var reconnect_timeout = false;

    var connect = function(){
        var ws = new WebSocket(ws_url);
        ws.onopen = function(){
            ws.send("SERVER DE CLIENT client=map.js type=map");
            reconnect_timeout = false
        };

        ws.onmessage = function(e){
            if (typeof e.data != 'string') {
                console.error("unsupported binary data on websocket; ignoring");
                return
            }
            if (e.data.substr(0, 16) == "CLIENT DE SERVER") {
                console.log("Server acknowledged WebSocket connection.");
                return
            }
            try {
                var json = JSON.parse(e.data);
                switch (json.type) {
                    case "config":
                        var config = json.value;
                        if (!map) $.getScript("https://maps.googleapis.com/maps/api/js?key=" + config.google_maps_api_key).done(function(){
                            var mapTypeId = config.google_maps_api_key ? 'roadmap' : 'OSM';

                            map = new google.maps.Map($('.openwebrx-map')[0], {
                                center: {
                                    lat: config.receiver_gps.lat,
                                    lng: config.receiver_gps.lon
                                },
                                zoom: 5,
                                mapTypeId: mapTypeId
                            });

                            map.mapTypes.set("OSM", new google.maps.ImageMapType({
                                getTileUrl: function(coord, zoom) {
                                    return "https://maps.wikimedia.org/osm-intl/" + zoom + "/" + coord.x + "/" + coord.y + ".png";
                                },
                                tileSize: new google.maps.Size(256, 256),
                                name: "OpenStreetMap",
                                maxZoom: 18
                            }));

                            $.getScript("static/lib/nite-overlay.js").done(function(){
                                nite.init(map);
                                setInterval(function() { nite.refresh() }, 10000); // every 10s
                            });
                            $.getScript('static/lib/AprsMarker.js').done(function(){
                                processUpdates(updateQueue);
                                updateQueue = [];
                            });
                            map.controls[google.maps.ControlPosition.LEFT_BOTTOM].push($(".openwebrx-map-legend")[0]);
                        });
                        retention_time = config.map_position_retention_time * 1000;
                    break;
                    case "update":
                        processUpdates(json.value);
                    break;
                    case 'receiver_details':
                        $('#webrx-top-container').header().setDetails(json['value']);
                    break;
                    default:
                        console.warn('received message of unknown type: ' + json['type']);
                }
            } catch (e) {
                // don't lose exception
                console.error(e);
            }
        };
        ws.onclose = function(){
            clearMap();
            if (reconnect_timeout) {
                // max value: roundabout 8 and a half minutes
                reconnect_timeout = Math.min(reconnect_timeout * 2, 512000);
            } else {
                // initial value: 1s
                reconnect_timeout = 1000;
            }
            setTimeout(connect, reconnect_timeout);
        };

        window.onbeforeunload = function() { //http://stackoverflow.com/questions/4812686/closing-websocket-correctly-html5-javascript
            ws.onclose = function () {};
            ws.close();
        };

        /*
        ws.onerror = function(){
            console.info("websocket error");
        };
        */
    };

    connect();

    var getInfoWindow = function() {
        if (!infowindow) {
            infowindow = new google.maps.InfoWindow();
            google.maps.event.addListener(infowindow, 'closeclick', function() {
                delete infowindow.locator;
                delete infowindow.callsign;
            });
        }
        return infowindow;
    }

    var infowindow;
    var showLocatorInfoWindow = function(locator, pos) {
        var infowindow = getInfoWindow();
        infowindow.locator = locator;
        var inLocator = $.map(rectangles, function(r, callsign) {
            return {callsign: callsign, locator: r.locator, lastseen: r.lastseen, mode: r.mode, band: r.band}
        }).filter(function(d) {
            return d.locator == locator;
        }).sort(function(a, b){
            return b.lastseen - a.lastseen;
        });
        infowindow.setContent(
            '<h3>Locator: ' + locator + '</h3>' +
            '<div>Active Callsigns:</div>' +
            '<ul>' +
                inLocator.map(function(i){
                    var timestring = moment(i.lastseen).fromNow();
                    var message = i.callsign + ' (' + timestring + ' using ' + i.mode;
                    if (i.band) message += ' on ' + i.band;
                    message += ')';
                    return '<li>' + message + '</li>'
                }).join("") +
            '</ul>'
        );
        infowindow.setPosition(pos);
        infowindow.open(map);
    };

    var showMarkerInfoWindow = function(callsign, pos) {
        var infowindow = getInfoWindow();
        infowindow.callsign = callsign;
        var marker = markers[callsign];
        var timestring = moment(marker.lastseen).fromNow();
        var commentString = "";
        if (marker.comment) {
            commentString = '<div>' + marker.comment + '</div>';
        }
        infowindow.setContent(
            '<h3>' + callsign + '</h3>' +
            '<div>' + timestring + ' using ' + marker.mode + ( marker.band ? ' on ' + marker.band : '' ) + '</div>' +
            commentString
        );
        infowindow.open(map, marker);
    }

    var getScale = function(lastseen) {
        var age = new Date().getTime() - lastseen;
        var scale = 1;
        if (age >= retention_time / 2) {
            scale = (retention_time - age) / (retention_time / 2);
        }
        return Math.max(0, Math.min(1, scale));
    };

    var getRectangleOpacityOptions = function(lastseen) {
        var scale = getScale(lastseen);
        return {
            strokeOpacity: strokeOpacity * scale,
            fillOpacity: fillOpacity * scale
        };
    };

    var getMarkerOpacityOptions = function(lastseen) {
        var scale = getScale(lastseen);
        return {
            opacity: scale
        };
    };

    // fade out / remove positions after time
    setInterval(function(){
        var now = new Date().getTime();
        $.each(rectangles, function(callsign, m) {
            var age = now - m.lastseen;
            if (age > retention_time) {
                delete rectangles[callsign];
                m.setMap();
                return;
            }
            m.setOptions(getRectangleOpacityOptions(m.lastseen));
        });
        $.each(markers, function(callsign, m) {
            var age = now - m.lastseen;
            if (age > retention_time) {
                delete markers[callsign];
                m.setMap();
                return;
            }
            m.setOptions(getMarkerOpacityOptions(m.lastseen));
        });
    }, 1000);

})();
