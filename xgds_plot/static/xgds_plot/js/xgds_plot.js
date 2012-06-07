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

var BLACK_COLORS = {
    raw: '#ccc',
    smooth: '#000'
}

var BLUE_COLORS = {
    raw: '#bbf',
    smooth: '#00a'
}

var GREEN_COLORS = {
    raw: '#9d9',
    smooth: '#0a0'
}

var ratioData;
var snData;
var cdData;
var kernel;
var newData = true;

var sock = null;

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

function dataSetCreate() {
    return {raw: [], smooth: []};
}

function dataSetAdd(data, t, y) {
    pushTruncate(data.raw, [t, y], MAX_NUM_DATA_POINTS);

    if (data.raw.length > KERNEL_WIDTH) {
        var ysmooth = dotProduct(kernel,
                                 getLastKSamples(data.raw, KERNEL_WIDTH));

        var mid = data.raw.length - HALF_KERNEL_WIDTH;
        var tmid = data.raw[mid][0];
        pushTruncate(data.smooth, [tmid, ysmooth],
                     MAX_NUM_DATA_POINTS - HALF_KERNEL_WIDTH + 1);
    }
}

function dataSetGetPlotData(data, colors, yred) {
    smoothData = {data: data.smooth, color: colors.smooth};
    if (yred != undefined) {
        setYRedLine(smoothData, yred);
    }
    return [
        {
            data: data.raw,
            color: colors.raw
        },
        smoothData
    ];
}

/**********************************************************************/

function ratioDataSetCreate() {
    return {raw: [], smooth: [], numerator: [], denominator: []};
}

function ratioDataSetAdd(data, t, ynum, ydenom) {
    pushTruncate(data.numerator, [t, ynum], MAX_NUM_DATA_POINTS);
    pushTruncate(data.denominator, [t, ydenom], MAX_NUM_DATA_POINTS);
    pushTruncate(data.raw, [t, ynum/ydenom], MAX_NUM_DATA_POINTS);

    if (data.raw.length > KERNEL_WIDTH) {
        var numSmooth = dotProduct(kernel,
                                   getLastKSamples(data.numerator, KERNEL_WIDTH));
        var denomSmooth = dotProduct(kernel,
                                     getLastKSamples(data.denominator, KERNEL_WIDTH));

        var mid = data.raw.length - HALF_KERNEL_WIDTH;
        var tmid = data.raw[mid][0];

        pushTruncate(data.smooth, [tmid, numSmooth / denomSmooth],
                     MAX_NUM_DATA_POINTS - HALF_KERNEL_WIDTH + 1);
    }
}

function ratioDataSetGetPlotData(data, color, yred) {
    return dataSetGetPlotData(data, color, yred);
}

/**********************************************************************/

function getPlotOpts(extraOpts) {
    var opts = {
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
    if (extraOpts != undefined) {
        $.extend(true, opts, extraOpts);
    }
    return opts;
}

function turnOffXTicks(opts) {
    $.extend(true, opts, {
        xaxis: {
            labelHeight: 0,
            tickFormatter: function () { return " "; }
        }
    });
}

function setYRedBackground(opts, threshold) {
    $.extend(true, opts, {
        grid: {
            markings: [
                {
                    yaxis: {
                        from: threshold,
                        to: 9999
                    },
                    color: "#fdd"
                }
            ]
        }
    });
}

function setYRedLine(seriesOpts, yred) {
    var normalColor = seriesOpts.color;
    $.extend(true, seriesOpts, {
        color: '#f00',
        threshold: {
            below: yred,
            color: normalColor
        }
    });
}

function plot() {
    if (ratioData.length < 2) {
        return; // not ready yet
    }
    if (!newData) {
        return; // nothing to do
    }

    var opts1 = getPlotOpts({
        yaxis: {
            min: 0,
            max: 6
        }
    });
    turnOffXTicks(opts1);
    setYRedBackground(opts1, 3.2);
    $.plot($('#plot_0'),
           ratioDataSetGetPlotData(ratioData, BLACK_COLORS, 3.2),
           opts1);


    var opts2 = getPlotOpts({
        yaxis: {
            min: 0,
            max: 80
        }
    });
    setYRedBackground(opts2, 48);
    $.plot($('#plot_1'),
           dataSetGetPlotData(snData, GREEN_COLORS, 48),
           opts2);

    var opts3 = getPlotOpts({
        yaxis: {
            min: 0,
            max: 80
        }
    });
    $.plot($('#plot_2'),
           dataSetGetPlotData(cdData, BLUE_COLORS),
           opts3);

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
    zmq.subscribeJson('isruApp.ddsnstier1data:', handleNsData);
}

function onclose(zmq) {
    $('#socketStatus').html('disconnected');
}

function handleNsData (zmq, topic, obj) {
    var fields = obj.data.fields;
    timestamp = obj.timestamp / 1000;
    ratioDataSetAdd(ratioData, timestamp, fields.snScalar, fields.cdScalar);
    dataSetAdd(snData, timestamp, fields.snScalar);
    dataSetAdd(cdData, timestamp, fields.cdScalar);
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
        /*
        if (plot.show) {
            style = '';
        } else {
            style = 'style="display: none"';
        }
        */
        style = '';
        plotsHtml.push('<div ' + style + '>'
                       + '<div id="plotLabel_' + i + '">' + plot.valueName + '</div>'
                       + '<div id="plot_' + i + '" class="flotPlot"></div>'
                       + '</div>');
        plots.push(null);
    });
    $("#plots").html(plotsHtml.join(""));

    kernel = gaussianKernel(SIGMA, KERNEL_WIDTH);
    ratioData = ratioDataSetCreate();
    snData = dataSetCreate();
    cdData = dataSetCreate();
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
