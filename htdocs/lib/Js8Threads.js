Js8Thread = function(el){
    this.messages = [];
    this.el = el;
};

Js8Thread.prototype.getAverageFrequency = function(){
    var total = this.messages.map(function(message){
        return message.freq;
    }).reduce(function(t, f){
        return t + f;
    }, 0);
    return total / this.messages.length;
};

Js8Thread.prototype.pushMessage = function(message) {
    this.messages.push(message);
    this.render();
};

Js8Thread.prototype.render = function() {
    this.el.html(
        '<td>' + this.renderTimestamp(this.getLatestTimestamp()) + '</td>' +
        '<td class="decimal freq">' + Math.round(this.getAverageFrequency()) + '</td>' +
        '<td class="message"><div>' + this.renderMessages() + '</div></td>'
    );
};

Js8Thread.prototype.getLatestTimestamp = function() {
    return this.messages[0].timestamp;
};

Js8Thread.prototype.isOpen = function() {
    if (!this.messages.length) return true;
    var last_message = this.messages[this.messages.length - 1];
    return (last_message.thread_type & 2) === 0;
};

Js8Thread.prototype.renderMessages = function() {
    var res = [];
    for (var i = 0; i < this.messages.length; i++) {
        var msg = this.messages[i];
        if (msg.thread_type & 1) {
            res.push('[ ');
        } else if (i === 0 || msg.timestamp - this.messages[i - 1].timestamp > this.getMessageDuration()) {
            res.push(' ... ');
        }
        res.push(msg.msg);
        if (msg.thread_type & 2) {
            res.push(' ]');
        } else if (i === this.messages.length -1) {
            res.push(' ... ');
        }
    }
    return res.join('');
};

Js8Thread.prototype.getMessageDuration = function() {
    switch (this.getMode()) {
        case 'A':
            return 15000;
        case 'E':
            return 30000;
        case 'B':
            return 10000;
        case 'C':
            return 6000;
    }
};

Js8Thread.prototype.getMode = function() {
    // we filter messages by mode, so the first one is as good as any
    if (!this.messages.length) return;
    return this.messages[0].mode;
};

Js8Thread.prototype.acceptsMode = function(mode) {
    var currentMode = this.getMode();
    return typeof(currentMode) === 'undefined' || currentMode === mode;
};

Js8Thread.prototype.renderTimestamp = function(timestamp) {
    var t = new Date(timestamp);
    var pad = function (i) {
        return ('' + i).padStart(2, "0");
    };
    return pad(t.getUTCHours()) + pad(t.getUTCMinutes()) + pad(t.getUTCSeconds());
};

Js8Thread.prototype.purgeOldMessages = function() {
    var now = new Date().getTime();
    this.messages = this.messages.filter(function(m) {
        // keep messages around for 20 minutes
        return now - m.timestamp < 20 * 60 * 1000;
    });
    if (!this.messages.length) {
        this.el.remove();
    } else {
        this.render();
    }
    return this.messages.length;
};

Js8Threader = function(el){
    this.threads = [];
    this.tbody = $(el).find('tbody');
    var me = this;
    this.interval = setInterval(function(){
        me.purgeOldMessages();
    }, 15000);
};

Js8Threader.prototype.purgeOldMessages = function() {
    this.threads = this.threads.filter(function(t) {
        return t.purgeOldMessages();
    });
};

Js8Threader.prototype.findThread = function(freq, mode) {
    var matching = this.threads.filter(function(thread) {
        // max frequency deviation: 5 Hz. this may be a little tight.
        return thread.isOpen() && thread.acceptsMode(mode) && Math.abs(thread.getAverageFrequency() - freq) <= 5;
    });
    matching.sort(function(a, b){
        return b.getLatestTimestamp() - a.getLatestTimestamp();
    });
    return matching[0] || false;
};

Js8Threader.prototype.pushMessage = function(message) {
    var thread;
    // only look for exising threads if the message is not a starting message
    if ((message.thread_type & 1) === 0) {
        thread = this.findThread(message.freq, message.mode);
    }
    if (!thread) {
        var line = $("<tr></tr>");
        this.tbody.append(line);
        thread = new Js8Thread(line);
        this.threads.push(thread);
    }
    thread.pushMessage(message);
    this.tbody.scrollTop(this.tbody[0].scrollHeight);
};

$.fn.js8 = function() {
    if (!this.data('threader')) {
        this.data('threader', new Js8Threader(this));
    }
    return this.data('threader');
};