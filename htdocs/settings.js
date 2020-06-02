$(function(){
    $(".map-input").each(function(el) {
        var $el = $(this);
        var field_id = $el.attr("for");
        var $lat = $('#' + field_id + '-lat');
        var $lon = $('#' + field_id + '-lon');
        $.getScript("https://maps.googleapis.com/maps/api/js?key=" + $el.data("key")).done(function(){
            $el.css("height", "200px");
            var lp = new locationPicker($el.get(0), {
                lat: parseFloat($lat.val()),
                lng: parseFloat($lon.val())
            }, {
                zoom: 7
            });

            google.maps.event.addListener(lp.map, 'idle', function(event){
                var pos = lp.getMarkerPosition();
                $lat.val(pos.lat);
                $lon.val(pos.lng);
            });
        });
    });

    $(".sdrdevice").sdrdevice();
});