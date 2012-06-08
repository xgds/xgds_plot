// __BEGIN_LICENSE__
// Copyright (C) 2008-2010 United States Government as represented by
// the Administrator of the National Aeronautics and Space Administration.
// All Rights Reserved.
// __END_LICENSE__

xgds_plot = {
    MAX_NUM_DATA_POINTS: 500,

    BASE_PLOT_OPTS: {
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
    },

    masterMeta: null,

    plots: [],

    haveNewData: false,

    parseIso8601: function (string) {
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
    },

    pushTruncate: function (arr, vals, n) {
        if (arr.length >= n-1) {
            arr.splice(0, 1);
        }
        arr.push(vals);
    },

    dotProduct: function (u, v) {
        var n = u.length;
        var ret = 0;
        for (var i=0; i < n; i++) {
            ret += u[i] * v[i];
        }
        return ret;
    },

    gaussianKernel: function (sigma, k) {
        var halfK = Math.floor(0.5 * k);
        var ret = new Array(k);
        var sum = 0;
        for (var i=0; i < k; i++) {
            var x = (i - halfK) / sigma;
            var y = Math.exp(-x*x);
            ret[i] = y;
            sum += y;
        }
        for (var i=0; i < k; i++) {
            ret[i] /= sum;
        }
        return ret;
    },

    getLastKSamples: function (arr, k) {
        var ret = [];
        var n = arr.length;
        for (var i=0; i < k; i++) {
            ret.push(arr[n-i-1][1]);
        }
        return ret;
    },

    /**********************************************************************/

    value: {

        Scalar: function (meta) {
            this.meta = $.extend(true, {}, meta);
            this.raw = [];
            if (this.meta.smoothing) {
                this.smooth = [];
                this.kernelWidth = this.meta.smoothing.sigmaPoints * 4;
                this.halfKernelWidth = Math.floor(0.5 * this.kernelWidth);
                this.kernel = xgds_plot.gaussianKernel(this.meta.smoothing.sigmaPoints,
                                                       this.kernelWidth);
            }
        },

        Ratio: function (meta) {
            this.meta = $.extend(true, {}, meta);
            this.raw = [];
            this.numerator = [];
            this.denominator = [];
            if (this.meta.smoothing) {
                this.smooth = [];
                this.kernelWidth = this.meta.smoothing.sigmaPoints * 4;
                this.halfKernelWidth = Math.floor(0.5 * this.kernelWidth);
                this.kernel = xgds_plot.gaussianKernel(this.meta.smoothing.sigmaPoints,
                                                       this.kernelWidth);
            }
        }

    },

    /**********************************************************************/

    updatePlots: function () {
        if (!xgds_plot.haveNewData) {
            return; // nothing to do
        }
        $.each(xgds_plot.plots, function (i, info) {
            xgds_plot.updatePlot(info);
        });

        xgds_plot.haveNewData = false;
    },

    updatePlot: function (info) {
        if (!info.show) return;

        var opts = $.extend(true, {}, xgds_plot.BASE_PLOT_OPTS, info.meta.plotOpts);
        var data = info.timeSeries.getPlotData();
        var raw = data[0];
        var smooth = data[1];
        var styledRaw = $.extend(true, {}, raw, info.meta.seriesOpts);
        var styledSmooth = $.extend(true, {}, smooth,
                                    info.meta.smoothing.seriesOpts);
        var plot = $.plot(info.plotDiv,
                          [styledRaw, styledSmooth],
                          opts);
        info.plot = plot;
    },

    periodicUpdatePlots: function () {
        xgds_plot.updatePlots();
        setTimeout(xgds_plot.periodicUpdatePlots, 200);
    },

    setupPlotHandlers: function (info) {
        info.plotDiv
            .bind('plothover', function (event, pos, item) {
                if (item) {
                    var pt = item.datapoint;
                    var t = $.plot.formatDate(new Date(pt[0]), '%H:%M:%S');
                    var y = pt[1].toFixed(3);
                    info.infoDiv
                        .html('<span style="padding-right: 10px; color: #888;">'
                              + t + '</span>'
                              + '<span style="font-weight: bold;">' + y + '</span>');
                }
            });
    },

    onopen: function (zmq) {
        $('#socketStatus').html('connected');
        zmq.subscribeJson('isruApp.resolvenstier1data:',
                          xgds_plot.handleNsData);
    },

    onclose: function (zmq) {
        $('#socketStatus').html('disconnected');
    },

    handleNsData: function (zmq, topic, obj) {
        var fields = obj.data.fields;
        $.each(xgds_plot.plots, function (i, info) {
            info.timeSeries.add(obj.data.fields);
        });
        xgds_plot.haveNewData = true;
    },

    handleMasterMeta: function (inMeta) {
        xgds_plot.masterMeta = inMeta;

        // create show/hide controls for each plot
        var plotControlsHtml = [];
        $.each(xgds_plot.masterMeta, function (i, meta) {
            var checked;
            if (meta.show) {
                checked = 'checked="checked" ';
            } else {
                checked = '';
            }
            plotControlsHtml
                .push('<div class="plotControl">'
                      + '<input type="checkbox" ' + checked + 'id="showPlot_' + i + '"></input>'
                      + '<label for="showPlot_' + i + '">'
                      + meta.valueName + '</label></div>');
        });
        $('#plotControls').html(plotControlsHtml.join(""));

        // create a div for each plot
        var plotsHtml = [];
        $.each(xgds_plot.masterMeta, function (i, meta) {
            var style;
            if (meta.show) {
                style = '';
            } else {
                style = 'style="display: none"';
            }
            plotsHtml.push('<div id="plotContainer_' + i + '"' + style + '>'
                           + '<div id="plotLabel_' + i + '">'
                           + meta.valueName
                           + '<span class="plotInfo" id="plotInfo_' + i + '"></span>'
                           + '</div>'
                           + '<div id="plot_' + i + '" class="flotPlot"></div>'
                           + '</div>');
        });
        $("#plots").html(plotsHtml.join(""));

        var timeSeriesTypeRegistry = {
            'xgds_plot.value.Ratio': xgds_plot.value.Ratio,
            'xgds_plot.value.Scalar': xgds_plot.value.Scalar
        };

        // initialize the xgds_plot.plots array
        $.each(xgds_plot.masterMeta, function (i, meta) {
            var timeSeriesType = timeSeriesTypeRegistry[meta.valueType];
            var timeSeries = new timeSeriesType(meta);
            var info = {index: i,
                        meta: meta,
                        plotDiv: $('#plot_' + i),
                        containerDiv: $('#plotContainer_' + i),
                        infoDiv: $('#plotInfo_' + i),
                        show: meta.show,
                        timeSeries: timeSeries,
                        plot: null}
            xgds_plot.plots.push(info);
            xgds_plot.setupPlotHandlers(info);
        });

        // connect to data feed
        var zmqUrl = settings
            .XGDS_ZMQ_WEB_SOCKET_URL
            .replace('{{host}}', window.location.hostname);
        var zmq = new ZmqManager(zmqUrl,
                                 {onopen: xgds_plot.onopen,
                                  onclose: xgds_plot.onclose,
                                  autoReconnect: true});
        zmq.start();

        // start updating plots
        xgds_plot.periodicUpdatePlots();

    }, // function handleMasterMeta

    init: function () {
        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/meta.json', xgds_plot.handleMasterMeta);
    }

}; // xgds_plot namespace

/**********************************************************************/

xgds_plot.value.Scalar.prototype.getValue = function (rec) {
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueField]];
}

xgds_plot.value.Scalar.prototype.add = function (rec) {
    var ty = this.getValue(rec);
    var t = ty[0];
    var y = ty[1];

    xgds_plot.pushTruncate(this.raw, [t, y], xgds_plot.MAX_NUM_DATA_POINTS);

    if (this.meta.smoothing && this.raw.length > this.kernelWidth) {
        var ysmooth = xgds_plot
            .dotProduct(this.kernel,
                        xgds_plot.getLastKSamples(this.raw, this.kernelWidth));

        var mid = this.raw.length - this.halfKernelWidth;
        var tmid = this.raw[mid][0];
        xgds_plot.pushTruncate(this.smooth, [tmid, ysmooth],
                               xgds_plot.MAX_NUM_DATA_POINTS - this.halfKernelWidth + 1);
    }
}

xgds_plot.value.Scalar.prototype.getPlotData = function () {
    return [{data: this.raw}, {data: this.smooth}];
}

/**********************************************************************/

xgds_plot.value.Ratio.prototype.getValue = function (rec) {
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueFields[0]],
            rec[this.meta.valueFields[1]]];
}

xgds_plot.value.Ratio.prototype.add = function (rec) {
    var tnd = this.getValue(rec);
    var t = tnd[0];
    var ynum = tnd[1];
    var ydenom = tnd[2];

    xgds_plot.pushTruncate(this.numerator, [t, ynum], xgds_plot.MAX_NUM_DATA_POINTS);
    xgds_plot.pushTruncate(this.denominator, [t, ydenom], xgds_plot.MAX_NUM_DATA_POINTS);
    xgds_plot.pushTruncate(this.raw, [t, ynum/ydenom], xgds_plot.MAX_NUM_DATA_POINTS);

    if (this.meta.smoothing && this.raw.length > this.kernelWidth) {
        var numSmooth = xgds_plot
            .dotProduct(this.kernel,
                        xgds_plot.getLastKSamples(this.numerator, this.kernelWidth));
        var denomSmooth = xgds_plot
            .dotProduct(this.kernel,
                        xgds_plot.getLastKSamples(this.denominator, this.kernelWidth));

        var mid = this.raw.length - this.halfKernelWidth;
        var tmid = this.raw[mid][0];

        xgds_plot.pushTruncate(this.smooth, [tmid, numSmooth / denomSmooth],
                               xgds_plot.MAX_NUM_DATA_POINTS - this.halfKernelWidth + 1);
    }
}

xgds_plot.value.Ratio.prototype.getPlotData = xgds_plot.value.Scalar.prototype.getPlotData;

