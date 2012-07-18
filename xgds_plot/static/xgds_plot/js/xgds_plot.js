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
            labelWidth: 60
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

    segmentCache: {},

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

    getBoundingBoxForAxis: function (plot, axis) {
        var left = axis.box.left, top = axis.box.top,
        right = left + axis.box.width, bottom = top + axis.box.height;

        // some ticks may stick out, enlarge the box to encompass all ticks
        var cls = axis.direction + axis.n + 'Axis';
        plot.getPlaceholder().find('.' + cls + ' .tickLabel').each(function () {
            var pos = $(this).position();
            left = Math.min(pos.left, left);
            top = Math.min(pos.top, top);
            right = Math.max(Math.round(pos.left) + $(this).outerWidth(), right);
            bottom = Math.max(Math.round(pos.top) + $(this).outerHeight(), bottom);
        });

        return { left: left, top: top, width: right - left, height: bottom - top + 5 };
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
            this.liveData = [];
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
            this.liveData = [];
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
            var data0 = info.timeSeries.getPlotData(info);
            var raw = data0[0];
            var smooth = data0[1];
            var styledRaw = $.extend(true, {}, raw, info.meta.seriesOpts);
            if (info.meta.smoothing != undefined
                && info.meta.smoothing.seriesOpts != undefined) {
                styledSmooth = $.extend(true, {}, smooth,
                                        info.meta.smoothing.seriesOpts);
                data = [styledRaw, styledSmooth];
            } else {
                data = [styledRaw];
            }
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
            plot.getPlaceholder().bind('plotpan plotzoom', function (info) {
                return function () {
                    xgds_plot.setLiveMode(false);
                    xgds_plot.matchXRange(info.plot);
                }
            }(info));
        } else {
            // update old plot
            if (xgds_plot.haveNewData) {
                info.plot.setData(data);
            }
        }

        if (xgds_plot.liveMode) {
            // auto-scroll to current time
            var liveTimeInterval = xgds_plot.getLiveTimeInterval(info);
            var xopts = info.plot.getAxes().xaxis.options;
            xopts.min = liveTimeInterval.min;
            xopts.max = liveTimeInterval.max;
        }

        info.plot.setupGrid();
        info.plot.draw();
    },

    getLiveTimeInterval: function (info) {
        var serverNow = new Date().valueOf() + xgds_plot.timeSkew;
        var width = 0;
        if (info.plot != undefined) {
            var current = xgds_plot.getIntervalForPlot(info);
            width = current.max - current.min;
        }
        if (width == 0) {
            width = settings.XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS;
        }
        return {min: serverNow - width,
                max: serverNow};
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
            if (info.meta.queryFilter != undefined) {
                $.each(info.meta.queryFilter,
                       function (i, filterEntry) {
                           var filterValue = filterEntry[1];
                           topic += '.' + filterValue;
                       });
            }
            topic += ':';
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

    getSegmentLevelForInterval: function (interval) {
        var minSegmentsInPlot = (settings.XGDS_PLOT_MIN_DISPLAY_RESOLUTION
                                 / settings.XGDS_PLOT_SEGMENT_RESOLUTION);
        var maxSegmentLength = (interval.max - interval.min) / minSegmentsInPlot;
        var level = Math.floor(Math.log(maxSegmentLength) / Math.log(2.0));
        level = Math.max(level, xgds_plot.MIN_SEGMENT_LEVEL);
        level = Math.min(level, xgds_plot.MAX_SEGMENT_LEVEL - 1);
        return level;
    },

    getSegmentsCoveringInterval: function (info, interval) {
        var level = xgds_plot.getSegmentLevelForInterval(interval);
        var segmentLength = Math.pow(2, level);
        var indexMin = Math.floor(interval.min / segmentLength);
        var indexMax = Math.ceil(interval.max / segmentLength) + 1;
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
        } else {
            var now = new Date().valueOf();
            if (now - current.timestamp > 5000) {
                xgds_plot.requestSegmentData(segment);
            }
        }
    },

    getSegmentKey: function (segment) {
        return segment.info.meta.valueCode + '/' + segment.level + '/' + segment.index;
    },

    getSegmentDataCache: function (segment) {
        return xgds_plot.segmentCache[xgds_plot.getSegmentKey(segment)];
    },

    setSegmentDataCache: function (segment, result) {
        xgds_plot.segmentCache[xgds_plot.getSegmentKey(segment)] = result;
    },

    requestSegmentData: function (segment) {
        $.getJSON(xgds_plot.getSegmentUrl(segment),
                  function (segment) {
                      return function (result) {
                          result.timestamp = new Date().valueOf();
                          xgds_plot.setSegmentDataCache(segment, result);
                          xgds_plot.haveNewData = true;
                      };
                  }(segment))
        .error(function (segment) {
            var updatedSegmentData = xgds_plot.getSegmentDataCache(segment);
            if (updatedSegmentData == undefined) {
                updatedSegmentData = {};
            }
            updatedSegmentData.timestamp = new Date().valueOf();
            xgds_plot.setSegmentDataCache(segment, updatedSegmentData);
        }(segment));
    },

    getIntervalForPlot: function (info) {
        var xopts = info.plot.getAxes().xaxis.options;
        return {min: xopts.min,
                max: xopts.max};
    },

    getSegmentDataCoveringPlots: function () {
        var plot1 = xgds_plot.plots[0];
        var interval = xgds_plot.getIntervalForPlot(plot1);
        xgds_plot.getSegmentDataCoveringInterval(interval);
    },

    getSegmentDataCoveringInterval: function (interval) {
        $.each(xgds_plot.plots, function (i, info) {
            var segments = xgds_plot.getSegmentsCoveringInterval(info, interval);
            $.each(segments, function (j, segment) {
                xgds_plot.loadSegmentData(segment);
            });
        });
    },

    setPlotVisibility: function (info, show) {
        info.show = show;
        if (show) {
            $('#plotContainer_' + info.index).css('display', '');
        } else {
            $('#plotContainer_' + info.index).css('display', 'none');
        }
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
                      + '<input'
                      + ' type="checkbox"' + checked
                      + ' id="showPlot_' + i + '"'
                      + ' disabled="disabled"'
                      + '>'
                      + '</input>'
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
                        plot: null,
                        drag: {}
                       }
            xgds_plot.plots.push(info);
            xgds_plot.setupPlotHandlers(info);
        });

        // render plots for the first time
        xgds_plot.updatePlots();

        // enable the plot visibility controls
        $.each(xgds_plot.plots, function (i, info) {
            var checkbox = $('#showPlot_' + i);
            checkbox.change(function (info) {
                return function (evt) {
                    var show = $(this).attr('checked');
                    xgds_plot.setPlotVisibility(info, show);
                };
            }(info));
            checkbox.removeAttr('disabled');
        });

        // set up the plot axis controls
        $.each(xgds_plot.plots, function (i, info) {
            if (info.show) {
                $.each(info.plot.getAxes(), function (i, axis) {
                    var box = xgds_plot.getBoundingBoxForAxis(info.plot, axis);

                    // FIX: also need to draw axisTarget on plots that are turned on by user

                    $('<div class="axisTarget" style="z-index:10;position:absolute;left:' + box.left + 'px;top:' + box.top + 'px;width:' + box.width +  'px;height:' + box.height + 'px"></div>')
                        .data('axis.direction', axis.direction)
                        .data('axis.n', axis.n)
                        .css({ backgroundColor: "#000", opacity: 0, cursor: "pointer" })
                        .appendTo(info.plot.getPlaceholder())
                        .hover(
                            function () { $(this).css({ opacity: 0.10 }) },
                            function () { $(this).css({ opacity: 0 }) })
                        .bind("dragstart",
                              function (info, axis) {
                                  return function (evt) {
                                      return xgds_plot.handleAxisDragStart(evt, info, axis);
                                  }
                              }(info, axis))
                        .bind("drag",
                              function (info, axis) {
                                  return function (evt) {
                                      return xgds_plot.handleAxisDrag(evt, info, axis);
                                  }
                              }(info, axis));
                });
            }
        });

        // start updating plots
        setInterval(xgds_plot.updatePlots, 200);
        setInterval(xgds_plot.getSegmentDataCoveringPlots, 200);
    }, // function handleMasterMeta

    handleAxisDragStart: function (evt, info, axis) {
        if (axis.direction == 'x') {
            info.drag.x = {
                start: evt.offsetX,
                axisRange: $.extend(true, {}, info.plot.getAxes().xaxis.options)
            };
        } else if (axis.direction == 'y') {
            info.drag.y = {
                start: evt.offsetY,
                axisRange: $.extend(true, {}, info.plot.getAxes().yaxis.options)
            };
        }
    },

    handleAxisDrag: function (evt, info, axis) {
        console.log('shiftPressed:' + evt.shiftKey);
        var axes = info.plot.getAxes();
        var axis, dragInfo, delta, pixelSize;
        if (axis.direction == 'x') {
            axis = axes.xaxis;
            dragInfo = info.drag.x;
            delta = evt.offsetX - dragInfo.start;
            pixelSize = info.plot.width();
        } else if (axis.direction == 'y') {
            axis = axes.yaxis;
            dragInfo = info.drag.y;
            delta = -(evt.offsetY - dragInfo.start);
            pixelSize = info.plot.height();
        }
        var valueSize = (dragInfo.axisRange.max - dragInfo.axisRange.min);
        if (evt.shiftKey) {
            // zoom
            var zoomFactor = Math.pow(2, -delta / 30);
            var halfSize = valueSize * zoomFactor / 2.0;;
            var center = (dragInfo.axisRange.min + dragInfo.axisRange.max) / 2.0;
            axis.options.min = center - halfSize;
            axis.options.max = center + halfSize;
        } else {
            // pan
            var motion = -delta * valueSize / pixelSize;
            axis.options.min = dragInfo.axisRange.min + motion;
            axis.options.max = dragInfo.axisRange.max + motion;
        }
        xgds_plot.setLiveMode(false);
        xgds_plot.matchXRange(info.plot);
    },

    handleServerTime: function (serverTime) {
        xgds_plot.timeSkew = serverTime - new Date().valueOf();
        //console.log('timeSkew: ' + xgds_plot.timeSkew);
    },

    init: function () {
        xgds_plot.MIN_SEGMENT_LENGTH_MS =
            settings.XGDS_PLOT_MIN_DATA_INTERVAL_MS
            * settings.XGDS_PLOT_SEGMENT_RESOLUTION;

        // python range convention -- level is in range [MIN_SEGMENT_LEVEL, MAX_SEGMENT_LEVEL)
        xgds_plot.MIN_SEGMENT_LEVEL =
            Math.floor(Math.log(xgds_plot.MIN_SEGMENT_LENGTH_MS)
                       / Math.log(2));

        xgds_plot.MAX_SEGMENT_LEVEL =
            (Math.ceil(Math.log(settings.XGDS_PLOT_MAX_SEGMENT_LENGTH_MS)
                       / Math.log(2))
             + 1);

        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/meta.json', xgds_plot.handleMasterMeta);
        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/now/', xgds_plot.handleServerTime);
    }

}); // xgds_plot namespace

/**********************************************************************/

xgds_plot.value.Scalar.prototype.getValue = function (rec) {
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueField]];
};

xgds_plot.value.Scalar.prototype.add = function (rec) {
    var ty = this.getValue(rec);
    var t = ty[0];
    var y = ty[1];

    xgds_plot.pushTruncate(this.liveData, [t, y], xgds_plot.MAX_NUM_DATA_POINTS);
};

xgds_plot.value.Scalar.prototype.collectData = function (info) {
    var result = [];

    // collect data from segments
    var interval;
    if (info.plot == undefined) {
        interval = xgds_plot.getLiveTimeInterval(info);
    } else {
        interval = xgds_plot.getIntervalForPlot(info);
    }
    var segments = xgds_plot.getSegmentsCoveringInterval(info, interval);
    $.each(segments, function (i, segment) {
        var segmentData = xgds_plot.getSegmentDataCache(segment);
        if (segmentData != undefined && segmentData.data != undefined) {
            var data = segmentData.data;
            $.each(data, function (i, row) {
                var timestamp = row[0];
                var mean = row[1];
                result.push([timestamp, mean]);
            });
        }
    });
    var lastSegmentTimestamp;
    if (result.length > 0) {
        var lastSegmentRow = result[result.length - 1];
        lastSegmentTimestamp = lastSegmentRow[0];
    } else {
        lastSegmentTimestamp = 0;
    }

    // add in rows from liveData
    $.each(this.liveData, function (i, row) {
        var timestamp = row[0];
        if (timestamp > lastSegmentTimestamp) {
            result.push(row);
        }
    });

    return result;
};

xgds_plot.value.Scalar.prototype.initSmoothing = function (info) {
    //this.raw = this.liveData;
    this.raw = this.collectData(info);

    this.smooth = [];
    if (this.meta.smoothing != undefined) {
        var sigmaMs = this.meta.smoothing.sigmaSeconds * 1000;
        this.kernelStart = 0;
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
};

xgds_plot.value.Scalar.prototype.getPlotData = function (info) {
    this.initSmoothing(info);
    return [{data: this.raw}, {data: this.smooth}];
};

/**********************************************************************/

xgds_plot.value.Ratio.prototype.getValue = function (rec) {
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueFields[0]],
            rec[this.meta.valueFields[1]]];
};

xgds_plot.value.Ratio.prototype.add = function (rec) {
    var tnd = this.getValue(rec);
    var t = tnd[0];
    var ynum = tnd[1];
    var ydenom = tnd[2];

    //xgds_plot.pushTruncate(this.numerator, [t, ynum], xgds_plot.MAX_NUM_DATA_POINTS);
    //xgds_plot.pushTruncate(this.denominator, [t, ydenom], xgds_plot.MAX_NUM_DATA_POINTS);
    xgds_plot.pushTruncate(this.liveData, [t, ynum/ydenom], xgds_plot.MAX_NUM_DATA_POINTS);
};

xgds_plot.value.Ratio.prototype.collectData = xgds_plot.value.Scalar.prototype.collectData;

// FIX: figure out how to make smoothing work properly with ratios and segment data
xgds_plot.value.Ratio.prototype.initSmoothing = xgds_plot.value.Scalar.prototype.initSmoothing;

/*
xgds_plot.value.Ratio.prototype.initSmoothing = function (info) {
    this.raw = this.collectData(info);

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
};
*/

xgds_plot.value.Ratio.prototype.getPlotData = xgds_plot.value.Scalar.prototype.getPlotData;

