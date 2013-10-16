#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import datetime
import logging
import multiprocessing
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import matplotlib

# must set matplotlib mode before importing pylab to suppress errors
matplotlib.interactive(False)
matplotlib.use('agg')

from matplotlib import pyplot as plt

from geocamUtil.loader import getClassByName

from xgds_plot import settings, pylabUtil
from xgds_plot.meta import TIME_SERIES_LOOKUP


# shift time zone from UTC to desired time zone
TIME_OFFSET_DAYS = float(settings.XGDS_PLOT_TIME_OFFSET_HOURS) / 24


def epochMsToDateTime(epochMs):
    epochSecs = float(epochMs) / 1000.0
    return datetime.datetime.utcfromtimestamp(epochSecs)


def epochMsToMatPlotLib(epochMs):
    return (matplotlib.dates.date2num(epochMsToDateTime(epochMs))
            + TIME_OFFSET_DAYS)


def writePlotData(out,
                  seriesId,
                  widthPix=None,
                  heightPix=None,
                  minTime=None,
                  maxTime=None):
    if widthPix is None:
        widthPix = 800
    if heightPix is None:
        heightPix = 120

    xinch = float(widthPix) / 100
    yinch = float(heightPix) / 100
    fig = plt.figure()

    meta = TIME_SERIES_LOOKUP[seriesId]
    queryClass = getClassByName(meta['queryType'])
    queryManager = queryClass(meta)
    valueClass = getClassByName(meta['valueType'])
    valueManager = valueClass(meta, queryManager)

    recs = queryManager.getData(minTime=minTime,
                                maxTime=maxTime)
    timestamps = [epochMsToMatPlotLib(queryManager.getTimestamp(rec))
                  for rec in recs]
    vals = [valueManager.getValue(rec)
            for rec in recs]

    plt.plot(timestamps, vals)

    ax = fig.gca()
    ax.grid(True)
    xmin, xmax, ymin, ymax = ax.axis()
    if minTime:
        xmin = epochMsToMatPlotLib(minTime)
    if maxTime:
        xmax = epochMsToMatPlotLib(maxTime)
    if ymin == 0 and ymax == 1:
        # HACK styling special case
        ymin = -0.1
        ymax = 1.1
    ax.axis([xmin, xmax, ymin, ymax])

    pylabUtil.setXAxisDate()
    plt.title(queryManager.getValueName(meta['valueField']))

    logging.info('writePlotData: writing image')
    plt.setp(fig, figwidth=xinch, figheight=yinch)
    fig.savefig(out,
                format='png',
                bbox_inches='tight',
                dpi=100,
                pad_inches=0.05,
                # transparent=True,
                )

    logging.info('writePlotData: releasing memory')
    fig.clf()
    plt.close(fig)


def savePlot(path,
             seriesId,
             widthPix=None,
             heightPix=None,
             minTime=None,
             maxTime=None):
    with open(path, 'wb') as out:
        writePlotData(out,
                      seriesId,
                      widthPix,
                      heightPix,
                      minTime,
                      maxTime)


def getPlotData(seriesId,
                widthPix=None,
                heightPix=None,
                minTime=None,
                maxTime=None):
    out = StringIO()
    writePlotData(out,
                  seriesId,
                  widthPix,
                  heightPix,
                  minTime,
                  maxTime)
    return out.getvalue()


def getPlotDataMultiprocessing(seriesId,
                               widthPix=None,
                               heightPix=None,
                               minTime=None,
                               maxTime=None):
    pool = multiprocessing.Pool(processes=1)
    imgData = pool.apply(getPlotData,
                         (seriesId,
                          widthPix,
                          heightPix,
                          minTime,
                          maxTime))
    pool.close()
    pool.join()
    return imgData


def testStaticPlot():
    now = datetime.datetime.utcnow()
    ago = now - datetime.timedelta(days=3)

    for f in ('airPressure', 'relativeHumidity'):
        savePlot(path=f + '.png',
                 seriesId=f,
                 widthPix=None,
                 heightPix=None,
                 minTime=ago,
                 maxTime=now)


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    _opts, args = parser.parse_args()
    if args:
        parser.error('expected no args')
    logging.basicConfig(level=logging.DEBUG)
    testStaticPlot()


if __name__ == '__main__':
    main()
