function Input(name, value, options) {
    this.name = name;
    this.value = value;
    this.options = options;
    this.label = options && options.label || name;
};

Input.prototype.getClasses = function() {
    return ['form-control', 'form-control-sm'];
}

Input.prototype.bootstrapify = function(input) {
    this.getClasses().forEach(input.addClass.bind(input));
    return [
        '<div class="form-group row">',
            '<label class="col-form-label col-form-label-sm col-3" for="' + this.name + '">' + this.label + '</label>',
            '<div class="col-9">',
                $.map(input, function(el) {
                    return el.outerHTML;
                }).join(''),
            '</div>',
        '</div>'
    ].join('');
};

function TextInput() {
    Input.apply(this, arguments);
};

TextInput.prototype = new Input();

TextInput.prototype.render = function() {
    return this.bootstrapify($('<input type="text" name="' + this.name + '" value="' + this.value + '">'));
}

function NumberInput() {
    Input.apply(this, arguments);
};

NumberInput.prototype = new Input();

NumberInput.prototype.render = function() {
    return this.bootstrapify($('<input type="number" name="' + this.name + '" value="' + this.value + '">'));
};

function SoapyGainInput() {
    Input.apply(this, arguments);
}

SoapyGainInput.prototype = new Input();

SoapyGainInput.prototype.getClasses = function() {
    return [];
};

SoapyGainInput.prototype.render = function(){
    var markup = $(
        '<div class="row form-group">' +
            '<div class="col-4">Gain mode</div>' +
            '<div class="col-8">' +
                '<select class="form-control form-control-sm">' +
                    '<option value="auto">automatic gain</option>' +
                    '<option value="single">single gain value</option>' +
                    '<option value="separate">separate gain values</option>' +
                '</select>' +
            '</div>' +
        '</div>' +
        '<div class="row option form-group gain-mode-single">' +
            '<div class="col-4">Gain</div>' +
            '<div class="col-8">' +
                '<input class="form-control form-control-sm" type="number">' +
            '</div>' +
        '</div>' +
        this.options.gains.map(function(g){
            return '<div class="row option form-group gain-mode-separate">' +
                '<div class="col-4">' + g + '</div>' +
                '<div class="col-8">' +
                    '<input class="form-control form-control-sm" data-gain="' + g + '" type="number">' +
                '</div>' +
            '</div>';
        }).join('')
    );
    var el = $(this.bootstrapify(markup))
    var setMode = function(mode){
        el.find('select').val(mode);
        el.find('.option').hide();
        el.find('.gain-mode-' + mode).show();
    };
    el.on('change', 'select', function(){
        var mode = $(this).val();
        setMode(mode);
    });
    if (typeof(this.value) === 'number') {
        setMode('single');
        el.find('.gain-mode-single input').val(this.value);
    } else if (typeof(this.value) === 'string') {
        if (this.value === 'auto') {
            setMode('auto');
        } else {
            setMode('separate');
            values = $.extend.apply($, this.value.split(',').map(function(seg){
                var split = seg.split('=');
                if (split.length < 2) return;
                var res = {};
                res[split[0]] = parseInt(split[1]);
                return res;
            }));
            el.find('.gain-mode-separate input').each(function(){
                var $input = $(this);
                var g = $input.data('gain');
                $input.val(g in values ? values[g] : 0);
            });
        }
    } else {
        setMode('auto');
    }
    return el;
};

function ProfileInput() {
    Input.apply(this, arguments);
};

ProfileInput.prototype = new Input();

ProfileInput.prototype.render = function() {
    return $('<div><h3>Profiles</h3></div>');
};

function SchedulerInput() {
    Input.apply(this, arguments);
};

SchedulerInput.prototype = new Input();

SchedulerInput.prototype.render = function() {
    return $('<div><h3>Scheduler</h3></div>');
};
