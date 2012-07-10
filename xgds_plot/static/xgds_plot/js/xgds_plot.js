// __BEGIN_LICENSE__
// Copyright (C) 2008-2010 United States Government as represented by
// the Administrator of the National Aeronautics and Space Administration.
// All Rights Reserved.
// __END_LICENSE__

xgds_plot = {};

$.extend(xgds_plot, {
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
        shadowSize: 0,
        zoom: {
            interactive: true
        },
        pan: {
            interactive: true
        }
    },

    masterMeta: null,

    plots: [],

    haveNewData: false,

    timeSkew: 0.0,

    liveMode: true,

    epochToString: function (epoch) {
        var d = new Date(epoch);
        dateString = d.toGMTString();
        return dateString.replace(/ GMT$/, '');
    },

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

    gaussian: function (x, sigma) {
        var xp = x / sigma;
        return Math.exp(-xp * xp);
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
                this.kernelWidth = this.meta.smoothing.sigmaSeconds * 4;
                this.halfKernelWidth = Math.floor(0.5 * this.kernelWidth);
                this.kernel = xgds_plot.gaussianKernel(this.meta.smoothing.sigmaSeconds,
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
                this.kernelWidth = this.meta.smoothing.sigmaSeconds * 4;
                this.halfKernelWidth = Math.floor(0.5 * this.kernelWidth);
                this.kernel = xgds_plot.gaussianKernel(this.meta.smoothing.sigmaSeconds,
                                                       this.kernelWidth);
            }
        }

    },

    /**********************************************************************/

    updateRange: function (plot) {
        var xopts = plot.getAxes().xaxis.options;
        var tminSpan = $('#tmin');
        var tmaxSpan = $('#tmax');
        tminSpan.html(xgds_plot.epochToString(xopts.min));
        tmaxSpan.html(xgds_plot.epochToString(xopts.max) + ' UTC');
    },

    matchXRange: function (masterPlot) {
        var masterXopts = masterPlot.getAxes().xaxis.options;
        $.each(xgds_plot.plots, function (i, info) {
            var slavePlot = info.plot;
            if (slavePlot != null && slavePlot != masterPlot) {
                var slaveXopts = slavePlot.getAxes().xaxis.options;

                if (! ((masterXopts.min == slaveXopts.min)
                       && (masterXopts.max == slaveXopts.max))) {
                    slaveXopts.min = masterXopts.min;
                    slaveXopts.max = masterXopts.max;
                    slavePlot.setupGrid();
                    slavePlot.draw();
                }
            }
        });
    },

    setLiveMode: function (liveMode) {
        xgds_plot.liveMode = liveMode;
        var liveModeCheckBox = $('#liveModeCheckBox');
        if (liveMode) {
            liveModeCheckBox.attr('checked', 'checked');
        } else {
            liveModeCheckBox.removeAttr('checked');
        }
    },

    updatePlots: function () {
        $.each(xgds_plot.plots, function (i, info) {
            xgds_plot.updatePlot(info);
        });

        xgds_plot.haveNewData = false;
    },

    updatePlot: function (info) {
        if (!info.show) return;

        var data;
        if (info.plot == undefined || xgds_plot.haveNewData) {
            var data0 = info.timeSeries.getPlotData();
            var raw = data0[0];
            var smooth = data0[1];
            var styledRaw = $.extend(true, {}, raw, info.meta.seriesOpts);
            var styledSmooth = $.extend(true, {}, smooth,
                                        info.meta.smoothing.seriesOpts);
            data = [styledRaw, styledSmooth];
        }

        if (info.plot == undefined) {
            // make new plot
            var opts = $.extend(true,
                                {
                                    hooks: {
                                        draw: xgds_plot.updateRange
                                    }
                                },
                                xgds_plot.BASE_PLOT_OPTS,
                                info.meta.plotOpts);

            var plot = $.plot(info.plotDiv, data, opts);
            info.plot = plot;
            plot.getPlaceholder().bind('plotpan plotzoom', function (plot) {
                return function () {
                    xgds_plot.setLiveMode(false);
                    xgds_plot.matchXRange(plot);
                    xgds_plot.getSegmentDataCoveringPlot(plot);
                }
            }(plot));
        } else {
            // update old plot
            if (xgds_plot.haveNewData) {
                info.plot.setData(data);
            }
        }

        if (xgds_plot.liveMode) {
            // auto-scroll to current time
            var serverNow = new Date().valueOf() + xgds_plot.timeSkew;
            var xopts = info.plot.getAxes().xaxis.options;
            xopts.min = serverNow - settings.XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS;
            xopts.max = serverNow;
        }

        info.plot.setupGrid();
        info.plot.draw();
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

        $.each(xgds_plot.plots, function (i, info) {
            var topic = info.meta.queryModel;
            var handler = function (info) {
                return function (zmq, topic, obj) {
                    info.timeSeries.add(obj);
                    xgds_plot.haveNewData = true;
                };
            }(info);

            zmq.subscribeDjango(topic, handler);
        });
    },

    onclose: function (zmq) {
        $('#socketStatus').html('disconnected');
    },

    getSegmentLevelForInterval: function (xmin, xmax) {
        var minSegmentsInPlot = (settings.XGDS_PLOT_MIN_DISPLAY_RESOLUTION
                                 / settings.XGDS_PLOT_SEGMENT_RESOLUTION);
        var maxSegmentLength = (xmax - xmin) / minSegmentsInPlot;
        var level = Math.floor(Math.log(maxSegmentLength) / Math.log(2.0));
        return level;
    },

    getSegmentsCoveringInterval: function (info, xmin, xmax) {
        var level = xgds_plot.getSegmentLevelForInterval(xmin, xmax);
        var segmentLength = Math.pow(2, level);
        var indexMin = Math.floor(xmin / segmentLength);
        var indexMax = Math.floor(xmax / segmentLength) + 1;
        var result = [];
        for (var i = indexMin; i < indexMax; i++) {
            result.push({info: info,
                         level: level,
                         index: i});
        }
        return result;
    },

    getSegmentUrl: function (segment) {
        return (settings.DATA_URL
                + settings.XGDS_PLOT_DATA_SUBDIR
                + 'plot/'
                + segment.info.meta.valueCode + '/'
                + segment.level + '/'
                + segment.index + '.json');
    },

    loadSegmentData: function (segment) {
        var current = xgds_plot.getSegmentDataCache(segment);
        if (current == undefined) {
            xgds_plot.requestSegmentData(segment);
        }
    },

    getSegmentKey: function (segment) {
        return segment.info + '/' + segment.level + '/' + segment.index;
    },

    getSegmentDataCache: function (segment) {
        return xgds_plot.segmentCache[xgds_plot.getSegmentKey(segment)];
    },

    setSegmentDataCache: function (info, level, index, result) {
        xgds_plot.segmentCache[xgds_plot.segmentKey(segment)] = result;
    },

    requestSegmentData: function (segment) {
        $.getJSON(xgds_plot.getSegmentUrl(segment),
                  function (segment) {
                      return function (result) {
                          xgds_plot.handleSegmentData(segment, result);
                      };
                  }(segment));
    },

    handleSegmentData: function (segment, result) {
        xgds_plot.setSegmentDataCache(segment, result);
        xgds_plot.haveNewData = true;
    },

    getSegmentDataCoveringPlot: function (plot) {
        var xopts = plot.getAxes().xaxis.options;
        xgds_plot.getSegmentDataCoveringInterval(xopts.min, xopts.max);
    },

    getSegmentDataCoveringInterval: function (xmin, xmax) {
        $.each(xgds_plot.plots, function (i, info) {
            var segments = xgds_plot.getSegmentsCoveringInterval(info, xmin, xmax);
            $.each(segments, function (j, segment) {
                xgds_plot.loadSegmentData(segment);
            });
        });
    },

    handleMasterMeta: function (inMeta) {
        xgds_plot.masterMeta = inMeta;

        // create live mode control
        $('#liveModeControl').html('<input type="checkbox" checked="checked" id="liveModeCheckBox">'
                                   + '</input>'
                                   + '<label for="liveModeCheckBox">'
                                   + 'Live</label>');
        $('#liveModeCheckBox').change(function () {
            var checked = $(this).attr('checked');
            console.log(checked);
            xgds_plot.liveMode = checked;
        });

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

        // connect to data feed
        var zmqUrl = settings
            .XGDS_ZMQ_WEB_SOCKET_URL
            .replace('{{host}}', window.location.hostname);
        var zmq = new ZmqManager(zmqUrl,
                                 {onopen: xgds_plot.onopen,
                                  onclose: xgds_plot.onclose,
                                  autoReconnect: true});
        zmq.start();

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

        // start updating plots
        xgds_plot.periodicUpdatePlots();

    }, // function handleMasterMeta

    handleServerTime: function (serverTime) {
        xgds_plot.timeSkew = serverTime - new Date().valueOf();
        //console.log('timeSkew: ' + xgds_plot.timeSkew);
    },

    init: function () {
        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/meta.json', xgds_plot.handleMasterMeta);
        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/now/', xgds_plot.handleServerTime);
    }

}); // xgds_plot namespace

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

    // note: we could avoid recalculating most of the smoothed values
    this.initSmoothing();
}

xgds_plot.value.Scalar.prototype.initSmoothing = function () {
    var sigmaMs = this.meta.smoothing.sigmaSeconds * 1000;
    this.kernelStart = 0;
    this.smooth = [];
    var self = this;
    $.each(self.raw, function (i, ty) {
        var t = ty[0];
        var sum = 0.0;
        var weightSum = 0.0;
        for (var j = self.kernelStart; j < self.raw.length; j++) {
            var typ = self.raw[j];
            var tp = typ[0];
            if ((t - tp) > (2 * sigmaMs)) {
                self.kernelStart++;
                continue;
            }
            var yp = typ[1];
            var weight = xgds_plot.gaussian(tp - t, sigmaMs);
            sum +=  weight * yp;
            weightSum += weight;
        }
        self.smooth.push([t, sum / weightSum]);
    });
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

    this.initSmoothing();
}

xgds_plot.value.Ratio.prototype.initSmoothing = function () {
    var sigmaMs = this.meta.smoothing.sigmaSeconds * 1000;
    this.kernelStart = 0;
    this.smooth = [];
    var self = this;
    $.each(self.raw, function (i, ty) {
        var t = ty[0];
        var numSum = 0.0;
        var denomSum = 0.0;
        for (var j = self.kernelStart; j < self.raw.length; j++) {
            var tynump = self.numerator[j];
            var tp = tynump[0];
            if ((t - tp) > (2 * sigmaMs)) {
                self.kernelStart++;
                continue;
            }
            var ynump = tynump[1];
            var tydenomp = self.denominator[j];
            var ydenomp = tydenomp[1];
            var weight = xgds_plot.gaussian(tp - t, sigmaMs);
            numSum +=  weight * ynump;
            denomSum += weight * ydenomp;
        }
        self.smooth.push([t, numSum / denomSum]);
    });
}

xgds_plot.value.Ratio.prototype.getPlotData = xgds_plot.value.Scalar.prototype.getPlotData;

