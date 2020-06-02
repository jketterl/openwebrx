function Measurement() {
    this.reporters = [];
    this.reset();
}

Measurement.prototype.add = function(v) {
    this.value += v;
};

Measurement.prototype.getValue = function() {
    return this.value;
};

Measurement.prototype.getElapsed = function() {
    return new Date() - this.start;
};

Measurement.prototype.getRate = function() {
    return this.getValue() / this.getElapsed();
};

Measurement.prototype.reset = function() {
    this.value = 0;
    this.start = new Date();
    this.reporters.forEach(function(r){ r.reset(); });
};

Measurement.prototype.report = function(range, interval, callback) {
    var reporter = new Reporter(this, range, interval, callback);
    this.reporters.push(reporter);
    return reporter;
};

function Reporter(measurement, range, interval, callback) {
    this.measurement = measurement;
    this.range = range;
    this.samples = [];
    this.callback = callback;
    this.interval = setInterval(this.report.bind(this), interval);
}

Reporter.prototype.sample = function(){
    this.samples.push({
        timestamp: new Date(),
        value: this.measurement.getValue()
    });
};

Reporter.prototype.report = function(){
    this.sample();
    var now = new Date();
    var minDate = now.getTime() - this.range;
    this.samples = this.samples.filter(function(s) {
        return s.timestamp.getTime() > minDate;
    });
    this.samples.sort(function(a, b) {
        return a.timestamp - b.timestamp;
    });
    var oldest = this.samples[0];
    var newest = this.samples[this.samples.length -1];
    var elapsed = newest.timestamp - oldest.timestamp;
    if (elapsed <= 0) return;
    var accumulated = newest.value - oldest.value;
    // we want rate per second, but our time is in milliseconds... compensate by 1000
    this.callback(accumulated * 1000 / elapsed);
};

Reporter.prototype.reset = function(){
    this.samples = [];
};