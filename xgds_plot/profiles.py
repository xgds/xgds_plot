#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import datetime
import calendar
import iso8601
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import numpy
import scipy
import matplotlib

# must set matplotlib mode before importing pylab to suppress errors
matplotlib.interactive(False)
matplotlib.use('agg')

import matplotlib.mlab
import matplotlib.pylab
from matplotlib import ticker
import matplotlib.dates

from geocamUtil.loader import getModelByName

from xgds_plot import settings


class Profile(object):
    pass


class ShortDateFormatter(matplotlib.dates.AutoDateFormatter):
    def __call__(self, x, pos=0):
        scale = float( self._locator._get_unit() )

        d = matplotlib.dates.DateFormatter
        if ( scale >= 365.0 ):
            self._formatter = d("%Y", self._tz)
        elif ( scale == 30.0 ):
            self._formatter = d("%b %Y", self._tz)
        elif ( (scale == 1.0) or (scale == 7.0) ):
            self._formatter = d("%b %d", self._tz)
        elif ( scale == (1.0/24.0) ):
            self._formatter = d("%H:%M", self._tz)
        elif ( scale == (1.0/(24*60)) ):
            self._formatter = d("%H:%M", self._tz)
        elif ( scale == (1.0/(24*3600)) ):
            self._formatter = d("%M:%S", self._tz)
        else:
            self._formatter = d("%b %d %Y %H:%M:%S", self._tz)

        return self._formatter(x, pos)


PROFILE_LOOKUP = {}
for profileMeta in settings.XGDS_PLOT_PROFILES:
    profile = Profile()
    profile.valueField = profileMeta['valueField']
    profile.model = getModelByName(profileMeta['queryModel'])
    profile.timestampField = profileMeta['queryTimestampField']
    profile.zField = profileMeta['queryZField']
    profile.filter = profileMeta['queryFilter']
    PROFILE_LOOKUP[profile.valueField] = profile


def pigeonHole(xp, yp, xi, yi):
    x0 = xi[0, 0]
    y0 = yi[0, 0]
    dx = xi[0, 1] - x0
    dy = yi[1, 0] - y0
    ix = int((xp - x0) / dx + 0.5)
    iy = int((yp - y0) / dy + 0.5)
    ny, nx = xi.shape
    if ((ix < nx)
        and (0 <= iy < ny)):
        if ix < 0:
            ix = 0
        return iy, ix
    else:
        return None


def balancedDiff(m):
    result = numpy.ma.masked_all(m.shape)
    d = m[1:, :] - m[:-1, :]
    result[1:-1, :] = 0.5 * (d[1:, :] + d[:-1, :])
    result[0, :] = m[1, :] - m[0, :]
    result[-1, :] = m[-1, :] - m[-2, :]
    return result


def griddata(x, y, z, xi, yi):
    zi = numpy.ma.masked_all(xi.shape, dtype='float64')
    for xp, yp, zp in zip(x, y, z):
        coords = pigeonHole(xp, yp, xi, yi)
        if coords is None:
            continue
        zi[coords] = zp

    ny, nx = xi.shape
    for iy in xrange(ny):
        zprev = None
        for ix in xrange(nx):
            zval = zi[iy, ix]
            if zprev and not zval:
                zval = zprev
                zi[iy, ix] = zval
            zprev = zval

    return zi


def getRawRecs(profile, minTime=None, maxTime=None):
    q = profile.model.objects.all()
    filterKwargs = {}
    for field, val in profile.filter:
        filterKwargs[field] = val
    if minTime is not None:
        filterKwargs[profile.timestampField + '__gte'] = minTime
    if maxTime is not None:
        filterKwargs[profile.timestampField + '__lte'] = maxTime
    q = q.filter(**filterKwargs)
    return q


def getValueTuples(profile, rawRecs):
    offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)

    t = []
    z = []
    v = []
    for rec in rawRecs:
        timestamp = getattr(rec, profile.timestampField, None)
        if timestamp is None:
            continue
        ti = matplotlib.dates.date2num(timestamp + offset)
        t.append(ti)

        zi = getattr(rec, profile.zField, None)
        if zi is None:
            continue
        z.append(zi)

        vi = getattr(rec, profile.valueField, None)
        if vi is None:
            continue
        v.append(vi)

    return numpy.array(t), numpy.array(z), numpy.array(v)


def getMeshGrid(t, z, minT=None, maxT=None):
    if minT is None:
        minT = t.min()
    if maxT is None:
        maxT = t.max()
    nt = settings.XGDS_PLOT_PROFILE_TIME_GRID_RESOLUTION
    dt = float(maxT - minT) / nt
    tvals = numpy.arange(minT, maxT, dt)

    minZ = z.min()
    maxZ = z.max()
    nz = settings.XGDS_PLOT_PROFILE_Z_GRID_RESOLUTION
    dz = float(maxZ - minZ) / nz
    zvals = numpy.arange(minZ, maxZ, dz)

    return scipy.meshgrid(tvals, zvals)


def getContourPlotImage(out, x, y, z,
                        xi, yi, zi,
                        labelx, labely,
                        sizePixels):
    xpix, ypix = sizePixels
    xinch, yinch = xpix / 100, ypix / 100
    #fig = matplotlib.pylab.figure(figsize=(xinch, yinch))
    fig = matplotlib.pylab.figure()
    matplotlib.pylab.contourf(xi, yi, zi, 256)
    xmin, xmax, ymin, ymax = matplotlib.pyplot.axis()
    ax = matplotlib.pylab.gca()

    ax.xaxis_date(tz='UTC')
    fmt = ShortDateFormatter(ax.xaxis.get_major_locator())
    ax.xaxis.set_major_formatter(fmt)

    matplotlib.pyplot.axis([xmin, xmax, ymax, ymin])
    # ax.set_xticklabels(ax.get_xticklabels(), fontdict={'size': 8})
    #matplotlib.pyplot.xlabel(labelx, fontsize=8)
    #matplotlib.pyplot.ylabel(labely, fontsize=8)
    #matplotlib.pylab.setp(matplotlib.pylab.getp(ax, 'xticklabels'),
    #                      fontsize='xx-small')
    #matplotlib.pylab.setp(matplotlib.pylab.getp(ax, 'yticklabels'),
    #                      fontsize='xx-small')
    # matplotlib.pyplot.tight_layout()
    matplotlib.pylab.colorbar()
    # ax.hold(True)
    matplotlib.pylab.scatter(x, y, s=0.5, c='k')
    matplotlib.pylab.setp(fig, figwidth=xinch, figheight=yinch)
    matplotlib.pyplot.savefig(out,
                              format='png',
                              bbox_inches='tight',
                              dpi=100,
                              pad_inches=0.05,
                              # transparent=True,
                              )


def firstcaps(val):
    return val[0].upper() + val[1:]


def numFromDateOrNone(dt):
    if dt:
        return matplotlib.dates.date2num(dt)
    else:
        return None


def writeProfileContourPlotImage(out, layerId,
                                 widthPix, heightPix,
                                 minTime=None,
                                 maxTime=None):
    profile = PROFILE_LOOKUP[layerId]

    if minTime:
        paddedMinTime = minTime - datetime.timedelta(days=7)
    else:
        paddedMinTime = None

    rawRecs = getRawRecs(profile, paddedMinTime, maxTime)
    t, z, v = numpy.array(getValueTuples(profile, rawRecs))
    ti, zi = getMeshGrid(t, z,
                         numFromDateOrNone(minTime),
                         numFromDateOrNone(maxTime))
    vi = griddata(t, z, v, ti, zi)

    sizePixels = (settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION,
                  settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION)
    fields = profile.model._meta._field_name_cache
    fieldLookup = dict([(f.name, f) for f in fields])
    labelT = (firstcaps(fieldLookup[profile.timestampField].verbose_name)
              + ' (%s)' % settings.XGDS_PLOT_TIME_ZONE_NAME)
    labelZ = firstcaps(fieldLookup[profile.zField].verbose_name)
    getContourPlotImage(out,
                        t, z, v,
                        ti, zi, vi,
                        labelT, labelZ,
                        sizePixels)


def saveProfileContourPlotImage(layerId, minTime=None, maxTime=None):
    logging.info('saving contour plot image to %s', layerId)
    out = open('%s.png' % layerId, 'wb')
    writeProfileContourPlotImage(out, layerId,
                                 widthPix=settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION,
                                 heightPix=settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION,
                                 minTime=minTime,
                                 maxTime=maxTime)
    out.close()


def getProfileContourPlotImageData(layerId,
                                   widthPix,
                                   heightPix,
                                   minTime=None,
                                   maxTime=None):
    out = StringIO()
    writeProfileContourPlotImage(out, layerId,
                                 widthPix, heightPix,
                                 minTime, maxTime)
    return out.getvalue()


def testProfiles():
    now = datetime.datetime.utcnow()
    ago = now - datetime.timedelta(days=3)
    for f in settings.XGDS_PLOT_PROFILES:
        saveProfileContourPlotImage(f['valueField'], minTime=ago, maxTime=now)


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    opts, args = parser.parse_args()
    if args:
        parser.error('expected no args')
    logging.basicConfig(level=logging.DEBUG)
    testProfiles()


if __name__ == '__main__':
    main()
