var globe = DAT.Globe(document.getElementById('container'));
var maximum_interval = 1;
var data = [];

const STATS_URI = '/globe_stats.json';

var interval_keys = function(data){
    var keys = [];
    for(index in data){
        if(data.hasOwnProperty(index)){
            keys.push(parseInt(data[index][0]));
        }
    }

    return keys;
};

var redraw_globe = function() {
    globe.resetData();
    for(index in data){
        if(data.hasOwnProperty(index)){
            var interval = parseInt(data[index][0]);
            var points = data[index][1];
            if(interval <= maximum_interval){
                globe.addData(points,{format: 'magnitude', animate: true});
            }
        }
    };
    globe.createPoints();
    globe.animate();
};

var elem = function(elem_type) {
    return $(document.createElement(elem_type));
}

var create_interval_buttons = function() {
    var interval_button_container = $("#intervals");
    var first = true;
    interval_keys(data).forEach(function(interval){
        interval_button_container.append(elem('a')
                                         .attr('href','#')
                                         .text(interval.toString()
                                               + " Minute"
                                               + ((interval > 1) ? "s" : ""))
                                         .addClass('interval')
                                         .attr('interval',interval)
                                         .css('font-weight', first ? "bold" : "normal")
                                         .click(function(cows){
                                             $('.interval').css('font-weight','normal');
                                             $(this).css('font-weight','bold');
                                             maximum_interval = $(this).attr('interval');
                                             redraw_globe();
                                         }));
        if(first){
            maximum_interval = interval;
        }
        first = false;
    });
};

var update_globe = function(callback) {
    $.getJSON(STATS_URI,function(new_data){
        data = new_data;
        callback ? callback() : true;
        redraw_globe();
    });
};

$(document).ready(function(){
    update_globe(create_interval_buttons);
});
