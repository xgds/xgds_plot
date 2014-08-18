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

    rangeChanged: false,

    timeSkew: 0.0,

    liveMode: null,

    segmentCache: {},

    dataTimeRange: {
        min: 99e+20,
        max: -99e+20
    },

    plotTimeRange: null,

    epochToString: function(epoch) {
        var d = new Date(epoch);
        dateString = d.toGMTString();
        return dateString.replace(/ GMT$/, '');
    },

    displayFromUtcTime: function(t) {
        return t + settings.XGDS_PLOT_TIME_OFFSET_HOURS * 3600 * 1000;
    },

    utcFromDisplayTime: function(t) {
        return t - settings.XGDS_PLOT_TIME_OFFSET_HOURS * 3600 * 1000;
    },

    parseIso8601: function(string) {
        var regexp = '([0-9]{4})(-([0-9]{2})(-([0-9]{2})' +
            '(T([0-9]{2}):([0-9]{2})(:([0-9]{2})(\.([0-9]+))?)?' +
            '(Z|(([-+])([0-9]{2}):([0-9]{2})))?)?)?)?';
        var d = string.match(new RegExp(regexp));

        var offset = 0;
        var date = new Date(d[1], 0, 1);

        if (d[3]) { date.setMonth(d[3] - 1); }
        if (d[5]) { date.setDate(d[5]); }
        if (d[7]) { date.setHours(d[7]); }
        if (d[8]) { date.setMinutes(d[8]); }
        if (d[10]) { date.setSeconds(d[10]); }
        if (d[12]) { date.setMilliseconds(Number('0.' + d[12]) * 1000); }
        if (d[14]) {
            offset = (Number(d[16]) * 60) + Number(d[17]);
            offset *= ((d[15] == '-') ? 1 : -1);
        }

        offset -= date.getTimezoneOffset();
        time = (Number(date) + (offset * 60 * 1000));
        return Number(time);
    },

    getBoundingBoxForAxis: function(plot, axis) {
        var left = axis.box.left, top = axis.box.top,
        right = left + axis.box.width, bottom = top + axis.box.height;

        // some ticks may stick out, enlarge the box to encompass all ticks
        var cls = axis.direction + axis.n + 'Axis';
        plot.getPlaceholder().find('.' + cls + ' .tickLabel').each(function() {
            var pos = $(this).position();
            left = Math.min(pos.left, left);
            top = Math.min(pos.top, top);
            right = Math.max(Math.round(pos.left) + $(this).outerWidth(), right);
            bottom = Math.max(Math.round(pos.top) + $(this).outerHeight(), bottom);
        });

        return { left: left, top: top, width: right - left, height: bottom - top + 5 };
    },

    pushTruncate: function(arr, vals, n) {
        if (arr.length >= n - 1) {
            arr.splice(0, 1);
        }
        arr.push(vals);
    },

    dotProduct: function(u, v) {
        var n = u.length;
        var ret = 0;
        for (var i = 0; i < n; i++) {
            ret += u[i] * v[i];
        }
        return ret;
    },

    gaussianKernel: function(sigma, k) {
        var halfK = Math.floor(0.5 * k);
        var ret = new Array(k);
        var sum = 0;
        for (var i = 0; i < k; i++) {
            var x = (i - halfK) / sigma;
            var y = Math.exp(-x * x);
            ret[i] = y;
            sum += y;
        }
        for (var i = 0; i < k; i++) {
            ret[i] /= sum;
        }
        return ret;
    },

    gaussian: function(x, sigma) {
        var xp = x / sigma;
        return Math.exp(-xp * xp);
    },

    getLastKSamples: function(arr, k) {
        var ret = [];
        var n = arr.length;
        for (var i = 0; i < k; i++) {
            ret.push(arr[n - i - 1][1]);
        }
        return ret;
    },

    /**********************************************************************/

    value: {

        Scalar: function(meta) {
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

        Ratio: function(meta) {
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

    updateRange: function(plot) {
        var xopts = plot.getAxes().xaxis.options;
        var tminSpan = $('#tmin');
        var tmaxSpan = $('#tmax');
        tminSpan.html(xgds_plot.epochToString(xopts.min));
        tmaxSpan.html(xgds_plot.epochToString(xopts.max) + ' ' +
                      settings.XGDS_PLOT_TIME_ZONE_NAME);
    },

    matchXRange: function(masterPlot) {
        var masterXopts = masterPlot.getAxes().xaxis.options;
        xgds_plot.plotTimeRange = masterXopts;
        $.each(xgds_plot.plots, function(i, info) {
            var slavePlot = info.plot;
            if (slavePlot != null && slavePlot != masterPlot) {
                var slaveXopts = slavePlot.getAxes().xaxis.options;

                if (! ((masterXopts.min == slaveXopts.min) &&
                       (masterXopts.max == slaveXopts.max))) {
                    slaveXopts.min = masterXopts.min;
                    slaveXopts.max = masterXopts.max;
                    slavePlot.setupGrid();
                    slavePlot.draw();
                }
            }
        });
    },

    setLiveMode: function(liveMode) {
        xgds_plot.liveMode = liveMode;
        var liveModeCheckBox = $('#liveModeCheckBox');
        if (liveMode) {
            liveModeCheckBox.attr('checked', 'checked');
        } else {
            liveModeCheckBox.removeAttr('checked');
        }
    },

    updatePlots: function() {
        $.each(xgds_plot.plots, function(i, info) {
            xgds_plot.updatePlot(info);
        });

        xgds_plot.haveNewData = false;
        xgds_plot.rangeChanged = false;
    },

    updatePlot: function(info) {
        if (!info.show) return;

        var data;
        if (info.plot == undefined || xgds_plot.haveNewData || xgds_plot.rangeChanged) {
            var data0 = info.timeSeries.getPlotData(info);
            var raw = data0[0];
            var smooth = data0[1];
            var styledRaw = $.extend(true, {}, raw, info.meta.seriesOpts);
            if (info.meta.smoothing != undefined &&
                info.meta.smoothing.seriesOpts != undefined) {
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
            if (!xgds_plot.liveMode) {
                $.extend(true, opts, {
                    xaxis: xgds_plot.plotTimeRange
                });
            }

            var plot = $.plot(info.plotDiv, data, opts);
            info.plot = plot;
            plot.getPlaceholder().bind('plotpan plotzoom', function(info) {
                return function() {
                    xgds_plot.setLiveMode(false);
                    xgds_plot.matchXRange(info.plot);
                    xgds_plot.rangeChanged = true;
                }
            }(info));

            xgds_plot.setupPlotAxisControls(info);
        } else {
            // update old plot
            if (xgds_plot.haveNewData || xgds_plot.rangeChanged) {
                info.plot.setData(data);
            }
        }

        if (xgds_plot.liveMode) {
            // auto-scroll to current time
            var liveTimeInterval = xgds_plot.getLiveTimeInterval(info);
            xgds_plot.plotTimeRange = liveTimeInterval;
            var xopts = info.plot.getAxes().xaxis.options;
            xopts.min = liveTimeInterval.min;
            xopts.max = liveTimeInterval.max;
        }

        info.plot.setupGrid();
        info.plot.draw();
    },

    getServerTime: function(t) {
        if (t == undefined) {
            t = new Date().valueOf();
        }
        return t + xgds_plot.timeSkew;
    },

    getLiveTimeInterval: function(info) {
        var serverNow = xgds_plot.getServerTime();
        var width = 0;
        if (info != undefined && info.plot != undefined) {
            var current = xgds_plot.getIntervalForPlot(info);
            width = current.max - current.min;
        }
        if (width == 0) {
            width = settings.XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS;
        }
        return {min: serverNow - width,
                max: serverNow};
    },

    setupPlotHandlers: function(info) {
        info.plotDiv
            .bind('plothover', function(event, pos, item) {
                if (item) {
                    var pt = item.datapoint;
                    var t = $.plot.formatDate(new Date(pt[0]), '%H:%M:%S');
                    var y = pt[1].toFixed(3);
                    info.infoDiv
                        .html('<span style="padding-right: 10px; color: #888;">' +
                              t + '</span>' +
                              '<span style="font-weight: bold;">' + y + '</span>');
                }
            });
    },

    onopen: function(zmq) {
        $('#socketStatus').html('connected');

        // FIX: should subscribe/unsubscribe based on plot visibility
        $.each(xgds_plot.plots, function(i, info) {
            var topic = info.meta.queryModel;
            if (info.meta.queryFilter != undefined) {
                $.each(info.meta.queryFilter,
                       function(i, filterEntry) {
                           var filterValue = filterEntry[1];
                           topic += '.' + filterValue;
                       });
            }
            topic += ':';
            var handler = function(info) {
                return function(zmq, topic, obj) {
                    info.timeSeries.add(obj);
                    xgds_plot.haveNewData = true;
                };
            }(info);

            zmq.subscribeDjango(topic, handler);
        });
    },

    onclose: function(zmq) {
        $('#socketStatus').html('disconnected');
    },

    getBucketSizeForXaxisRange: function(interval) {
        var level = xgds_plot.getSegmentLevelForInterval(interval);
        var segmentLength = Math.pow(2.0, level);
        var bucketSize = segmentLength / settings.XGDS_PLOT_SEGMENT_RESOLUTION;
        return bucketSize;
    },

    getSegmentLevelForInterval: function(interval) {
        /* note: can be either displayInterval *or* utcInterval, will get same result */
        var minSegmentsInPlot = (settings.XGDS_PLOT_MIN_DISPLAY_RESOLUTION /
                                 settings.XGDS_PLOT_SEGMENT_RESOLUTION);
        var maxSegmentLength = (interval.max - interval.min) / minSegmentsInPlot;
        var level = Math.floor(Math.log(maxSegmentLength) / Math.log(2.0));
        level = Math.max(level, xgds_plot.MIN_SEGMENT_LEVEL);
        level = Math.min(level, xgds_plot.MAX_SEGMENT_LEVEL - 1);
        return level;
    },

    getSegmentsCoveringInterval: function(info, displayInterval) {
        var utcInterval = {
            min: xgds_plot.utcFromDisplayTime(displayInterval.min),
            max: xgds_plot.utcFromDisplayTime(displayInterval.max)
        };
        var level = xgds_plot.getSegmentLevelForInterval(utcInterval);
        var segmentLength = Math.pow(2, level);
        var indexMin = Math.floor(utcInterval.min / segmentLength);
        var indexMax = Math.ceil(utcInterval.max / segmentLength) + 1;
        var result = [];
        for (var i = indexMin; i < indexMax; i++) {
            result.push({info: info,
                         level: level,
                         index: i});
        }
        return result;
    },

    getSegmentUrl: function(segment) {
        return (settings.DATA_URL +
                settings.XGDS_PLOT_DATA_SUBDIR +
                'plot/' +
                segment.info.meta.valueCode + '/' +
                segment.level + '/' +
                segment.index + '.json');
    },

    getStatusUrl: function(info) {
        return (settings.DATA_URL +
                settings.XGDS_PLOT_DATA_SUBDIR +
                'plot/' +
                info.meta.valueCode + '/' +
                'status.json');
    },

    requestStatus: function(info) {
        $.getJSON(xgds_plot.getStatusUrl(info),
                  function(info) {
                      return function(result) {
                          info.status = result;
                          xgds_plot.dataTimeRange.min = Math.min(xgds_plot.dataTimeRange.min,
                                                                 info.status.minTime);
                          xgds_plot.dataTimeRange.max = Math.max(xgds_plot.dataTimeRange.max,
                                                                 info.status.maxTime);
                          xgds_plot.checkIfStatusComplete();
                      };
                  }(info));
    },

    loadSegmentData: function(segment) {
        var cached = xgds_plot.getSegmentDataCache(segment);
        if (cached == undefined) {
            xgds_plot.requestSegmentData(segment);
        } else {
            var now = new Date().valueOf();
            if (settings.XGDS_PLOT_CHECK_FOR_NEW_DATA && now - cached.timestamp > 5000) {
                xgds_plot.requestSegmentData(segment);
            }
        }
    },

    getSegmentKey: function(segment) {
        return segment.info.meta.valueCode + '/' + segment.level + '/' + segment.index;
    },

    getSegmentDataCache: function(segment) {
        return xgds_plot.segmentCache[xgds_plot.getSegmentKey(segment)];
    },

    setSegmentDataCache: function(segment, result) {
        xgds_plot.segmentCache[xgds_plot.getSegmentKey(segment)] = result;
    },

    requestSegmentData: function(segment) {
        $.getJSON(xgds_plot.getSegmentUrl(segment),
                  function(segment) {
                      return function(result) {
                          result.timestamp = new Date().valueOf();
                          xgds_plot.setSegmentDataCache(segment, result);
                          xgds_plot.haveNewData = true;
                      };
                  }(segment))
        .error(function(segment) {
            return function(evt) {
                if (evt.status == 200) {
                    console.log('unknown error in handling segment data at url' +
                                ' ' + xgds_plot.getSegmentUrl(segment));
                    console.log('check segment file for json parse errors?');
                }

                var updatedSegmentData = xgds_plot.getSegmentDataCache(segment);
                if (updatedSegmentData == undefined) {
                    updatedSegmentData = {};
                }
                updatedSegmentData.timestamp = new Date().valueOf();
                xgds_plot.setSegmentDataCache(segment, updatedSegmentData);
            };
        }(segment));
    },

    getIntervalForPlot: function(info) {
        var xopts = info.plot.getAxes().xaxis.options;
        return {min: xopts.min,
                max: xopts.max};
    },

    getSegmentDataCoveringPlots: function() {
        xgds_plot.getSegmentDataCoveringInterval(xgds_plot.plotTimeRange);
    },

    getSegmentDataCoveringInterval: function(interval) {
        $.each(xgds_plot.plots, function(i, info) {
            if (!info.show) {
                return true; // continue to next iteration
            }
            var segments = xgds_plot.getSegmentsCoveringInterval(info, interval);
            $.each(segments, function(j, segment) {
                xgds_plot.loadSegmentData(segment);
            });
        });
    },

    setPlotVisibility: function(info, show) {
        info.show = show;
        if (show) {
            $('#plotContainer_' + info.index).css('display', '');
        } else {
            $('#plotContainer_' + info.index).css('display', 'none');
        }
    },

    insertDiscontinuities: function(data, maxContinuousDataGap) {
        if (data.length == 0) {
            return data;
        }

        var prev = data[0][0];
        var result = [];
        $.each(data, function(i, ty) {
            var t = ty[0];
            var dt = t - prev;

            if (dt > maxContinuousDataGap) {
                result.push([t, null]);
            }
            result.push(ty);

            prev = t;
        });

        return result;
    },

    handleMasterMeta: function(inMeta) {
        xgds_plot.masterMeta = inMeta;

        // create data structures: plots and plotNameLookup
        xgds_plot.plots = [];
        xgds_plot.plotNameLookup = {};
        $.each(xgds_plot.masterMeta, function(i, meta) {
            var info = {index: i,
                        meta: meta};
            xgds_plot.plots.push(info);
            xgds_plot.plotNameLookup[meta.valueCode] = info;
        });

        // set plot visibility
        if (requestParams.timeSeriesNames == undefined) {
            // set visibility based on meta
            $.each(xgds_plot.plots, function(i, info) {
                info.show = info.meta.show;
            });
        } else {
            // set visibility based on requestParams
            $.each(xgds_plot.plots, function(i, info) {
                info.show = false;
            });
            $.each(requestParams.timeSeriesNames, function(i, timeSeriesName) {
                var info = xgds_plot.plotNameLookup[timeSeriesName];
                info.show = true;
            });
        }

        // request status of each time series
        $.each(xgds_plot.plots, function(i, info) {
            if (info.show) {
                xgds_plot.requestStatus(info);
            }
        });
    },

    checkIfStatusComplete: function() {
        var allHaveStatus = true;

        $.each(xgds_plot.plots, function(i, info) {
            if (info.show && info.status == undefined) {
                allHaveStatus = false;
                return false; // break
            }
        });

        if (allHaveStatus) {
            xgds_plot.handleStatusComplete();
        }
    },

    handleStatusComplete: function() {
        // set initial plot time range
        if (xgds_plot.liveMode) {
            xgds_plot.plotTimeRange = xgds_plot.getLiveTimeInterval();
        } else {
            xgds_plot.plotTimeRange = xgds_plot.dataTimeRange;
        }

        // create sidebar show/hide controls for each plot
        var plotControlsHtml = [];
        $.each(xgds_plot.plots, function(i, info) {
            var checked;
            if (info.show) {
                checked = 'checked="checked" ';
            } else {
                checked = '';
            }
            plotControlsHtml
                .push('<div class="plotControl">' +
                      '<input' +
                      ' type="checkbox"' + checked +
                      ' id="showPlot_' + i + '"' +
                      ' disabled="disabled"' +
                      '>' +
                      '</input>' +
                      '<label for="showPlot_' + i + '">' +
                      info.meta.valueName + '</label></div>');
        });
        $('#plotControls').html(plotControlsHtml.join(''));

        // create a div for each plot
        var plotsHtml = [];
        $.each(xgds_plot.plots, function(i, info) {
            var style;
            if (info.show) {
                style = '';
            } else {
                style = 'style="display: none"';
            }
            if (info.meta.valueDetails) {
                valueDetails = info.meta.valueDetails;
            } else {
                valueDetails = '';
            }
            plotsHtml.push('<div id="plotContainer_' + i + '"' + style + '>' +
                           '<div id="plotLabel_' + i + '">' +
                           info.meta.valueName + valueDetails +
                           '<span class="plotInfo" id="plotInfo_' + i + '"></span>' +
                           '</div>' +
                           '<div id="plot_' + i + '" class="flotPlot"></div>' +
                           '</div>');
        });
        $('#plots').html(plotsHtml.join(''));

        if (settings.XGDS_PLOT_CHECK_FOR_NEW_DATA) {
            // connect to live data feed
            var zmqUrl = settings
                .XGDS_ZMQ_WEB_SOCKET_URL
                .replace('{{host}}', window.location.hostname);
            var zmq = new ZmqManager(zmqUrl,
                                     {onopen: xgds_plot.onopen,
                                      onclose: xgds_plot.onclose,
                                      autoReconnect: true});
            zmq.start();
        }

        // fill in remaining fields of each xgds_plot.plots entry
        var timeSeriesTypeRegistry = {
            'xgds_plot.value.Ratio': xgds_plot.value.Ratio,
            'xgds_plot.value.Scalar': xgds_plot.value.Scalar
        };
        $.each(xgds_plot.plots, function(i, info) {
            var timeSeriesType = timeSeriesTypeRegistry[info.meta.valueType];
            var timeSeries = new timeSeriesType(info.meta);
            $.extend(info,
                     {plotDiv: $('#plot_' + i),
                      containerDiv: $('#plotContainer_' + i),
                      infoDiv: $('#plotInfo_' + i),
                      timeSeries: timeSeries,
                      plot: null,
                      drag: {}
                     });
            xgds_plot.setupPlotHandlers(info);
        });

        // render plots for the first time
        xgds_plot.updatePlots();

        // enable the plot visibility controls
        $.each(xgds_plot.plots, function(i, info) {
            var checkbox = $('#showPlot_' + i);
            checkbox.change(function(info) {
                return function(evt) {
                    var show = $(this).attr('checked');
                    xgds_plot.setPlotVisibility(info, show);
                };
            }(info));
            checkbox.removeAttr('disabled');
        });

        // start updating plots
        setInterval(xgds_plot.updatePlots, 200);
        setInterval(xgds_plot.getSegmentDataCoveringPlots, 200);
    }, // function handleMasterMeta

    setupPlotAxisControls: function(info) {
        if (info.axisControlsInitialized) {
            return;
        }

        $.each(info.plot.getAxes(), function(i, axis) {
            var box = xgds_plot.getBoundingBoxForAxis(info.plot, axis);

            $('<div class="axisTarget" style="z-index:10;position:absolute;left:' + box.left + 'px;top:' + box.top + 'px;width:' + box.width + 'px;height:' + box.height + 'px"></div>')
                .data('axis.direction', axis.direction)
                .data('axis.n', axis.n)
                .css({ backgroundColor: '#000', opacity: 0, cursor: 'pointer' })
                .appendTo(info.plot.getPlaceholder())
                .hover(
                    function() { $(this).css({ opacity: 0.10 }) },
                    function() { $(this).css({ opacity: 0 }) })
                .bind('dragstart',
                      function(info, axis) {
                          return function(evt) {
                              return xgds_plot.handleAxisDragStart(evt, info, axis);
                          }
                      }(info, axis))
                .bind('drag',
                      function(info, axis) {
                          return function(evt) {
                              return xgds_plot.handleAxisDrag(evt, info, axis);
                          }
                      }(info, axis));
        });

        info.axisControlsInitialized = true;
    },

    handleAxisDragStart: function(evt, info, axis) {
        if (axis.direction == 'x') {
            var xaxis = info.plot.getAxes().xaxis;
            info.drag.x = {
                start: evt.offsetX,
                axisRange: {min: xaxis.min, max: xaxis.max}
            };
        } else if (axis.direction == 'y') {
            var yaxis = info.plot.getAxes().yaxis;
            info.drag.y = {
                start: evt.offsetY,
                axisRange: {min: yaxis.min, max: yaxis.max}
            };
        }
    },

    handleAxisDrag: function(evt, info, axis) {
        //console.log('shiftPressed:' + evt.shiftKey);
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
            var halfSize = valueSize * zoomFactor / 2.0;
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
        if (axis.direction == 'x') {
            xgds_plot.matchXRange(info.plot);
            xgds_plot.rangeChanged = true;
        }
    },

    handleServerTime: function(serverTime) {
        xgds_plot.timeSkew = serverTime - new Date().valueOf();
        //console.log('timeSkew: ' + xgds_plot.timeSkew);
    },

    init: function() {
        xgds_plot.MIN_SEGMENT_LENGTH_MS =
            settings.XGDS_PLOT_MIN_DATA_INTERVAL_MS *
            settings.XGDS_PLOT_SEGMENT_RESOLUTION;

        xgds_plot.liveMode = settings.XGDS_PLOT_LIVE_MODE_DEFAULT;

        // python range convention -- level is in range [MIN_SEGMENT_LEVEL, MAX_SEGMENT_LEVEL)
        xgds_plot.MIN_SEGMENT_LEVEL =
            Math.floor(Math.log(xgds_plot.MIN_SEGMENT_LENGTH_MS) /
                       Math.log(2));

        xgds_plot.MAX_SEGMENT_LEVEL =
            (Math.ceil(Math.log(settings.XGDS_PLOT_MAX_SEGMENT_LENGTH_MS) /
                       Math.log(2)) + 1);

        // create live mode control
        $('#liveModeControl').html('<input type="checkbox" checked="checked" id="liveModeCheckBox">' +
                                   '</input>' +
                                   '<label for="liveModeCheckBox">' +
                                   'Live</label>');
        $('#liveModeCheckBox').change(function() {
            var checked = $(this).attr('checked');
            xgds_plot.liveMode = checked;
        });

        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/meta.json', xgds_plot.handleMasterMeta);
        $.getJSON(settings.SCRIPT_NAME + 'xgds_plot/now/', xgds_plot.handleServerTime);
    }

}); // xgds_plot namespace

/**********************************************************************/

xgds_plot.value.Scalar.prototype.getValuesFromLiveDataRecord = function(rec) {
    // return [timestamp, valueSum, count]
    // each live data message only holds one data value so count is 1
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueField],
            1];
};

xgds_plot.value.Scalar.prototype.getValuesFromSegmentBucket = function(row) {
    // return [timestamp, valueSum, count]
    var timestamp = row[0];
    var mean = row[1];
    var count = row[5];
    return [xgds_plot.displayFromUtcTime(timestamp), mean * count, count];
};

xgds_plot.value.Scalar.prototype.add = function(rec) {
    xgds_plot.pushTruncate(this.liveData,
                           this.getValuesFromLiveDataRecord(rec),
                           xgds_plot.MAX_NUM_DATA_POINTS);
};

xgds_plot.value.Scalar.prototype.collectData = function(info) {
    var result = [];

    // collect data from segments
    var interval;
    if (info.plot == undefined) {
        interval = xgds_plot.getLiveTimeInterval(info);
    } else {
        interval = xgds_plot.getIntervalForPlot(info);
    }
    var segments = xgds_plot.getSegmentsCoveringInterval(info, interval);
    var self = this;
    $.each(segments, function(i, segment) {
        var segmentData = xgds_plot.getSegmentDataCache(segment);
        if (segmentData != undefined && segmentData.data != undefined) {
            var data = segmentData.data;
            $.each(data, function(i, bucket) {
                result.push(self.getValuesFromSegmentBucket(bucket));
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
    $.each(this.liveData, function(i, row) {
        var timestamp = row[0];
        if (timestamp > lastSegmentTimestamp) {
            result.push(row);
        }
    });

    return result;
};

xgds_plot.value.Scalar.prototype.initSmoothing = function(info) {
    var tndValues = this.collectData(info);

    var self = this;
    this.raw = [];
    $.each(tndValues, function(i, tnd) {
        self.raw.push([tnd[0], tnd[1] / tnd[2]]);
    });

    this.smooth = [];
    if (this.meta.smoothing != undefined) {
        var sigmaMs = this.meta.smoothing.sigmaSeconds * 1000;
        this.kernelStart = 0;
        $.each(tndValues, function(i, tnd) {
            var t = tnd[0];
            var numSum = 0.0;
            var denomSum = 0.0;
            for (var j = self.kernelStart; j < tndValues.length; j++) {
                var tndp = tndValues[j];
                var tp = tndp[0];
                if ((t - tp) > (2 * sigmaMs)) {
                    self.kernelStart++;
                    continue;
                }
                var nump = tndp[1];
                var denomp = tndp[2];
                var weight = xgds_plot.gaussian(tp - t, sigmaMs);
                numSum += weight * nump;
                denomSum += weight * denomp;
            }
            self.smooth.push([t, numSum / denomSum]);
        });
    }

    if (this.meta.plotOpts != undefined &&
        this.meta.plotOpts.xaxis != undefined &&
        this.meta.plotOpts.xaxis.maxContinuousDataGap != undefined) {
        var maxContinuousDataGap = this.meta.plotOpts.xaxis.maxContinuousDataGap;
        if (xgds_plot.plotTimeRange != null) {
            var bucketSize = xgds_plot.getBucketSizeForXaxisRange(xgds_plot.plotTimeRange);
            maxContinuousDataGap = Math.max(maxContinuousDataGap, 2 * bucketSize);
        }
        this.raw = xgds_plot.insertDiscontinuities(this.raw, maxContinuousDataGap);
        if (this.meta.smoothing != undefined) {
            this.smooth = xgds_plot.insertDiscontinuities(this.smooth, maxContinuousDataGap);
        }
    }
};

xgds_plot.value.Scalar.prototype.getPlotData = function(info) {
    this.initSmoothing(info);
    return [{data: this.raw}, {data: this.smooth}];
};

/**********************************************************************/

xgds_plot.value.Ratio.prototype.getValuesFromLiveDataRecord = function(rec) {
    // return [timestamp, numSum, denomSum]
    return [xgds_plot.parseIso8601(rec[this.meta.queryTimestampField]),
            rec[this.meta.valueFields[0]],
            rec[this.meta.valueFields[1]]];
};

xgds_plot.value.Ratio.prototype.getValuesFromSegmentBucket = function(row) {
    var timestamp = row[0];
    var numSum = row[6];
    var denomSum = row[7];
    return [timestamp, numSum, denomSum];
};

xgds_plot.value.Ratio.prototype.add = xgds_plot.value.Scalar.prototype.add;
xgds_plot.value.Ratio.prototype.collectData = xgds_plot.value.Scalar.prototype.collectData;
xgds_plot.value.Ratio.prototype.initSmoothing = xgds_plot.value.Scalar.prototype.initSmoothing;
xgds_plot.value.Ratio.prototype.getPlotData = xgds_plot.value.Scalar.prototype.getPlotData;
