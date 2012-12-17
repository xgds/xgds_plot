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

import numpy as np
import scipy
import matplotlib
import pytz

# must set matplotlib mode before importing pylab to suppress errors
matplotlib.interactive(False)
matplotlib.use('agg')

from matplotlib import pyplot as plt
from matplotlib import ticker
import matplotlib.dates

from geocamUtil.loader import getModelByName

from xgds_plot import settings

TIME_OFFSET = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
TIME_OFFSET_DAYS = float(settings.XGDS_PLOT_TIME_OFFSET_HOURS) / 24

class Profile(object):
    pass


def firstcaps(val):
    return val[0].upper() + val[1:]


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


PROFILES = []
PROFILE_LOOKUP = {}
for profileMeta in settings.XGDS_PLOT_PROFILES:
    profile = Profile()
    profile.valueField = profileMeta['valueField']
    profile.valueCode = profile.valueField
    profile.model = getModelByName(profileMeta['queryModel'])
    profile.timestampField = profileMeta['queryTimestampField']
    profile.zField = profileMeta['queryZField']
    profile.filter = profileMeta['queryFilter']

    fields = profile.model._meta._field_name_cache
    fieldLookup = dict([(f.name, f) for f in fields])
    profile.name = firstcaps(fieldLookup[profile.valueField].verbose_name)
    profile.timeLabel = firstcaps(fieldLookup[profile.timestampField].verbose_name)
    profile.zLabel = firstcaps(fieldLookup[profile.zField].verbose_name)

    PROFILES.append(profile)
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
    result = np.ma.masked_all(m.shape)
    d = m[1:, :] - m[:-1, :]
    result[1:-1, :] = 0.5 * (d[1:, :] + d[:-1, :])
    result[0, :] = m[1, :] - m[0, :]
    result[-1, :] = m[-1, :] - m[-2, :]
    return result


def griddata(x, y, z, xi, yi):
    zi = np.ma.masked_all(xi.shape, dtype='float64')
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
    t = []
    z = []
    v = []
    for rec in rawRecs:
        timestamp = getattr(rec, profile.timestampField, None)
        if timestamp is None:
            continue
        ti = matplotlib.dates.date2num(timestamp + TIME_OFFSET)
        t.append(ti)

        zi = getattr(rec, profile.zField, None)
        if zi is None:
            continue
        z.append(zi)

        vi = getattr(rec, profile.valueField, None)
        if vi is None:
            continue
        v.append(vi)

    return np.array(t), np.array(z), np.array(v)


def getMeshGrid(t, z, minT=None, maxT=None):
    if minT is None:
        minT = t.min()
    if maxT is None:
        maxT = t.max()
    nt = settings.XGDS_PLOT_PROFILE_TIME_GRID_RESOLUTION
    dt = float(maxT - minT) / nt
    tvals = np.arange(minT + TIME_OFFSET_DAYS,
                         maxT + TIME_OFFSET_DAYS,
                         dt)

    minZ = z.min()
    maxZ = z.max()
    nz = settings.XGDS_PLOT_PROFILE_Z_GRID_RESOLUTION
    dz = float(maxZ - minZ) / nz
    zvals = np.arange(minZ, maxZ, dz)

    return scipy.meshgrid(tvals, zvals)


def percentile(vec, pct):
    """
    Sort of like np.percentile, back-ported to older versions of
    np.
    """
    vec = sorted(vec)
    n = len(vec)
    pos = float(pct) / 100 * (n - 1)
    i = min(int(pos), n - 2)
    weight = pos - i
    return vec[i] * (1 - weight) + vec[i + 1] * weight


def getContourPlotImage(out, x, y, z,
                        xi, yi, zi,
                        labelx, labely,
                        sizePixels):
    xpix, ypix = sizePixels
    xinch, yinch = xpix / 100, ypix / 100
    fig = plt.figure()

    # suppress outliers
    minLevel = percentile(z, 1.0)
    maxLevel = percentile(z, 99.0)
    norm = matplotlib.colors.Normalize(minLevel, maxLevel)

    ax = fig.gca()
    contours = ax.contourf(xi, yi, zi, 256, norm=norm)
    ax.xaxis_date(tz=pytz.utc)
    fmt = ShortDateFormatter(ax.xaxis.get_major_locator())
    ax.xaxis.set_major_formatter(fmt)

    fig.colorbar(contours)

    # suppress scatterplot points outside the contourf grid
    inRange = reduce(np.logical_and,
                     [xi.min() <= x,
                      x <= xi.max(),
                      yi.min() <= y,
                      y <= yi.max()],
                     True)
    rng = np.where(inRange)

    if 1:
        ax.hold(True)
        # add scatterplot sample points to figure
        ax.scatter(x[rng], y[rng], s=0.5, c='k')

    # this is mostly to flip the y axis so increasing depth is down.  we
    # also put in a special case for depth profiles: y < 0 (negative
    # depth) is distracting and we should make sure any bogus points
    # above water don't show up on the plot.
    xmin, xmax, ymin, ymax = plt.axis()
    ax.axis([max(xi.min(), xmin), xmax, ymax, max(0, ymin)])

    plt.setp(fig, figwidth=xinch, figheight=yinch)
    fig.savefig(out,
                format='png',
                bbox_inches='tight',
                dpi=100,
                pad_inches=0.05,
                # transparent=True,
                )


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
    t, z, v = np.array(getValueTuples(profile, rawRecs))
    ti, zi = getMeshGrid(t, z,
                         numFromDateOrNone(minTime),
                         numFromDateOrNone(maxTime))
    vi = griddata(t, z, v, ti, zi)

    sizePixels = (settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION,
                  settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION)
    getContourPlotImage(out,
                        t, z, v,
                        ti, zi, vi,
                        profile.timeLabel, profile.zLabel,
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
    ago = now - datetime.timedelta(days=30)
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
