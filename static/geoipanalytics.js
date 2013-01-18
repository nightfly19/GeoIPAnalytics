var min_breakdowns = [1, 5, 15, 60];

var globe = DAT.Globe(document.getElementById('container'));
globe.min_ndx = 0;

var setmin = function(globe, set_ndx) {
    return function() {
        if(set_ndx !== undefined)
            globe.min_ndx = set_ndx;
        globe.resetData();
        globe.addData(data[globe.min_ndx][1], {format: 'magnitude', animate: true});
        globe.createPoints();
        globe.animate();
    };
};

var update_data = function(globe) {
    return function() {
        xhr = new XMLHttpRequest();
        xhr.open('GET', '/globe_stats.json', true);
        xhr.onreadystatechange = function(e) {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    var data = JSON.parse(xhr.responseText);
                    window.data = data;
                    setmin(globe)();

                    //                window.setInterval(update_data(globe), 1000);
                }
            }
        };
        xhr.send(null);
    };
};

for(var i = 0; i < min_breakdowns.length; i++) {
    var bd_link = document.getElementById('min'+min_breakdowns[i]);
    bd_link.addEventListener('click', setmin(globe, i), false);
}

update_data(globe)();
