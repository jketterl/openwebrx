function Header(el) {
    this.el = el;

    this.el.find('#openwebrx-main-buttons').find('[data-toggle-panel]').click(function () {
        toggle_panel($(this).data('toggle-panel'));
    });

    this.init_rx_photo();
    this.download_details();
};

Header.prototype.setDetails = function(details) {
    this.el.find('#webrx-rx-title').html(details['receiver_name']);
    var query = encodeURIComponent(details['receiver_gps']['lat'] + ',' + details['receiver_gps']['lon']);
    this.el.find('#webrx-rx-desc').html(details['receiver_location'] + ' | Loc: ' + details['locator'] + ', ASL: ' + details['receiver_asl'] + ' m, <a href="https://www.google.com/maps/search/?api=1&query=' + query + '" target="_blank">[maps]</a>');
    this.el.find('#webrx-rx-photo-title').html(details['photo_title']);
    this.el.find('#webrx-rx-photo-desc').html(details['photo_desc']);
};

Header.prototype.init_rx_photo = function() {
    this.rx_photo_state = 0;

    $.extend($.easing, {
        easeOutCubic:function(x) {
            return 1 - Math.pow( 1 - x, 3 );
        }
    });

    $('#webrx-top-container').find('.openwebrx-photo-trigger').click(this.toggle_rx_photo.bind(this));
};

Header.prototype.close_rx_photo = function() {
    this.rx_photo_state = 0;
    this.el.find("#webrx-rx-photo-desc").animate({opacity: 0});
    this.el.find("#webrx-rx-photo-title").animate({opacity: 0});
    this.el.find('#webrx-top-photo-clip').animate({maxHeight: 67}, {duration: 1000, easing: 'easeOutCubic'});
    this.el.find("#openwebrx-rx-details-arrow-down").show();
    this.el.find("#openwebrx-rx-details-arrow-up").hide();
}

Header.prototype.open_rx_photo = function() {
    this.rx_photo_state = 1;
    this.el.find("#webrx-rx-photo-desc").animate({opacity: 1});
    this.el.find("#webrx-rx-photo-title").animate({opacity: 1});
    this.el.find('#webrx-top-photo-clip').animate({maxHeight: 350}, {duration: 1000, easing: 'easeOutCubic'});
    this.el.find("#openwebrx-rx-details-arrow-down").hide();
    this.el.find("#openwebrx-rx-details-arrow-up").show();
}

Header.prototype.toggle_rx_photo = function(ev) {
    if (ev && ev.target && ev.target.tagName == 'A') {
        return;
    }
    if (this.rx_photo_state) {
        this.close_rx_photo();
    } else {
        this.open_rx_photo();
    }
};

Header.prototype.download_details = function() {
    var self = this;
    $.ajax('api/receiverdetails').done(function(data){
        self.setDetails(data);
    });
};

$.fn.header = function() {
    if (!this.data('header')) {
        this.data('header', new Header(this));
    }
    return this.data('header');
};

$(function(){
    $('#webrx-top-container').header();
});
