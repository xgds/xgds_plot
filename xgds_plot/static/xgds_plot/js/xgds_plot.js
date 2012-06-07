// __BEGIN_LICENSE__
// Copyright (C) 2008-2010 United States Government as represented by
// the Administrator of the National Aeronautics and Space Administration.
// All Rights Reserved.
// __END_LICENSE__

var masterMeta;
var plots = [];

var MAX_NUM_DATA_POINTS = 500;
var SIGMA = 15;
var KERNEL_WIDTH = SIGMA * 4;
var HALF_KERNEL_WIDTH = Math.floor(KERNEL_WIDTH / 2.0);

var ratioData;
var snData;
var cdData;
var kernel;
var newData = true;

var sock = null;

function parseIso8601(string) {
    var regexp = "([0-9]{4})(-([0-9]{2})(-([0-9]{2})" +
        "(T([0-9]{2}):([0-9]{2})(:([0-9]{2})(\.([0-9]+))?)?" +
        "(Z|(([-+])([0-9]{2}):([0-9]{2})))?)?)?)?";
    var d = string.match(new RegExp(regexp));

    var offset = 0;
    var date = new Date(d[1], 0, 1);

    if (d[3]) { date.setMonth(d[3] - 1); }
    if (d[5]) { date.setDate(d[5]); }
    if (d[7]) { date.setHours(d[7]); }
    if (d[8]) { date.setMinutes(d[8]); }
    if (d[10]) { date.setSeconds(d[10]); }
    if (d[12]) { date.setMilliseconds(Number("0." + d[12]) * 1000); }
    if (d[14]) {
        offset = (Number(d[16]) * 60) + Number(d[17]);
        offset *= ((d[15] == '-') ? 1 : -1);
    }

    offset -= date.getTimezoneOffset();
    time = (Number(date) + (offset * 60 * 1000));
    return Number(time);
}

function pushTruncate(arr, vals, n) {
    if (arr.length >= n-1) {
        arr.splice(0, 1);
    }
    arr.push(vals);
}

function dotProduct(u, v) {
    var n = u.length;
    var ret = 0;
    for (var i=0; i < n; i++) {
        ret += u[i] * v[i];
    }
    return ret;
}

function gaussianKernel(sigma, k) {
    var ret = new Array(k);
    var sum = 0;
    for (var i=0; i < k; i++) {
        var x = (i - HALF_KERNEL_WIDTH) / sigma;
        var y = Math.exp(-x*x);
        ret[i] = y;
        sum += y;
    }
    for (var i=0; i < k; i++) {
        ret[i] /= sum;
    }
    return ret;
}

function getLastKSamples(arr, k) {
    var ret = [];
    var n = arr.length;
    for (var i=0; i < k; i++) {
        ret.push(arr[n-i-1][1]);
    }
    return ret;
}

/**********************************************************************/

function ScalarTimeSeries(meta) {
    this.meta = $.extend(true, {}, meta);
    this.raw = [];
    this.smooth = [];
}

ScalarTimeSeries.prototype.getValue = function (rec) {
    return [parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueField]];
}

ScalarTimeSeries.prototype.add = function (rec) {
    var ty = this.getValue(rec);
    var t = ty[0];
    var y = ty[1];

    pushTruncate(this.raw, [t, y], MAX_NUM_DATA_POINTS);

    if (this.raw.length > KERNEL_WIDTH) {
        var ysmooth = dotProduct(kernel,
                                 getLastKSamples(this.raw, KERNEL_WIDTH));

        var mid = this.raw.length - HALF_KERNEL_WIDTH;
        var tmid = this.raw[mid][0];
        pushTruncate(this.smooth, [tmid, ysmooth],
                     MAX_NUM_DATA_POINTS - HALF_KERNEL_WIDTH + 1);
    }
}

ScalarTimeSeries.prototype.getPlotData = function () {
    return [{data: this.raw}, {data: this.smooth}];
}

/**********************************************************************/

function RatioTimeSeries(meta) {
    this.meta = $.extend(true, {}, meta);
    this.raw = [];
    this.smooth = [];
    this.numerator = [];
    this.denominator = [];
}

RatioTimeSeries.prototype.getValue = function (rec) {
    return [parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueFields[0]],
            rec[this.meta.valueFields[1]]];
}

RatioTimeSeries.prototype.add = function (rec) {
    var tnd = this.getValue(rec);
    var t = tnd[0];
    var ynum = tnd[1];
    var ydenom = tnd[2];

    pushTruncate(this.numerator, [t, ynum], MAX_NUM_DATA_POINTS);
    pushTruncate(this.denominator, [t, ydenom], MAX_NUM_DATA_POINTS);
    pushTruncate(this.raw, [t, ynum/ydenom], MAX_NUM_DATA_POINTS);

    if (this.raw.length > KERNEL_WIDTH) {
        var numSmooth = dotProduct(kernel,
                                   getLastKSamples(this.numerator, KERNEL_WIDTH));
        var denomSmooth = dotProduct(kernel,
                                     getLastKSamples(this.denominator, KERNEL_WIDTH));

        var mid = this.raw.length - HALF_KERNEL_WIDTH;
        var tmid = this.raw[mid][0];

        pushTruncate(this.smooth, [tmid, numSmooth / denomSmooth],
                     MAX_NUM_DATA_POINTS - HALF_KERNEL_WIDTH + 1);
    }
}

RatioTimeSeries.prototype.getPlotData = ScalarTimeSeries.prototype.getPlotData;

/**********************************************************************/

function plot() {
    // FIX: don't hard code
    var dataFuncs = [
        function () { return ratioData.getPlotData(); },
        function () { return snData.getPlotData(); },
        function () { return cdData.getPlotData(); }
    ];

    if (ratioData.length < 2) {
        return; // not ready yet
    }
    if (!newData) {
        return; // nothing to do
    }

    var defaultOpts = {
        xaxis: {
            mode: 'time'
        },
        yaxis: {
            labelWidth: 20
        },
        grid: {
            hoverable: true,
            clickable: true
        },
        shadowSize: 0
    };

    $.each(dataFuncs, function (i, dataFunc) {
        var meta = masterMeta[i];
        var opts = $.extend(true, {}, defaultOpts, meta.plotOpts);
        var data = dataFunc();
        var raw = data[0];
        var smooth = data[1];
        //console.log(i + ' ' + raw.data.length);
        var styledRaw = $.extend(true, {}, raw, meta.seriesOpts);
        var styledSmooth = $.extend(true, {}, smooth, meta.smoothing.seriesOpts);
        plots[i] = $.plot($('#plot_' + i),
                          [styledRaw, styledSmooth],
                          opts);
    });

    newData = false;
}

function periodicPlot() {
    plot();
    setTimeout(periodicPlot, 200);
}

function setupPlotHandlers(plotId) {
    var plotDiv = $('#' + plotId);
    var infoDiv = $('#' + plotId + '_info');
    plotDiv.bind('plothover', function (event, pos, item) {
        if (item) {
            var pt = item.datapoint;
            var t = $.plot.formatDate(new Date(pt[0]), '%H:%M:%S');
            var y = pt[1].toFixed(3);
            infoDiv.html('<span style="padding-right: 10px; color: #888;">' + t + '</span>'
                         + '<span style="font-weight: bold;">' + y + '</span>');
        }
    });
}

function onopen(zmq) {
    $('#socketStatus').html('connected');
    zmq.subscribeJson('isruApp.resolvenstier1data:', handleNsData);
}

function onclose(zmq) {
    $('#socketStatus').html('disconnected');
}

function handleNsData (zmq, topic, obj) {
    var fields = obj.data.fields;
    ratioData.add(obj.data.fields);
    snData.add(obj.data.fields);
    cdData.add(obj.data.fields);
    newData = true;
}

function handleMasterMeta(inMeta) {
    masterMeta = inMeta;

    // create show/hide controls for each plot
    var plotControlsHtml = [];
    $.each(masterMeta, function (i, plot) {
        var checked;
        if (plot.show) {
            checked = 'checked="checked" ';
        } else {
            checked = '';
        }
        plotControlsHtml
            .push('<div class="plotControl">'
                  + '<input type="checkbox" ' + checked + 'id="showPlot_' + i + '"></input>'
                  + '<label for="showPlot_' + i + '">'
                  + plot.valueName + '</label></div>');
    });
    $('#plotControls').html(plotControlsHtml.join(""));

    // create a div and an entry in the plots array for each plot
    var plotsHtml = [];
    $.each(masterMeta, function (i, plot) {
        var style;
        if (plot.show) {
            style = '';
        } else {
            style = 'style="display: none"';
        }
        plotsHtml.push('<div ' + style + '>'
                       + '<div id="plotLabel_' + i + '">' + plot.valueName + '</div>'
                       + '<div id="plot_' + i + '" class="flotPlot"></div>'
                       + '</div>');
        plots.push(null);
    });
    $("#plots").html(plotsHtml.join(""));

    kernel = gaussianKernel(SIGMA, KERNEL_WIDTH);
    ratioData = new RatioTimeSeries(masterMeta[0]);
    snData = new ScalarTimeSeries(masterMeta[1]);
    cdData = new ScalarTimeSeries(masterMeta[2]);
    setupPlotHandlers('ratioPlot');
    setupPlotHandlers('snPlot');

    var zmqUrl = settings
        .XGDS_ZMQ_WEB_SOCKET_URL
        .replace('{{host}}', window.location.hostname);
    var zmq = new ZmqManager(zmqUrl,
                             {onopen: onopen,
                              onclose: onclose,
                              autoReconnect: true});
    zmq.start();

    periodicPlot();
}

$(function () {
    $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/meta.json', handleMasterMeta);
});
