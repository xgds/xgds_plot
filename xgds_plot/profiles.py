#!/usr/bin/env python
# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import datetime
import logging
import multiprocessing
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

# avoid the following error on 'import matplotlib':
# Failed to create /var/www/.matplotlib; consider setting MPLCONFIGDIR to a writable directory for matplotlib configuration data
if os.environ.get('MPLCONFIGDIR') is None and os.environ.get('HOME').startswith('/var/www'):
    os.environ['MPLCONFIGDIR'] = '/tmp'

import numpy as np
import scipy
import matplotlib

# must set matplotlib mode before importing pylab to suppress errors
matplotlib.interactive(False)
matplotlib.use('agg')

from matplotlib import pyplot as plt
import matplotlib.dates

from geocamUtil.loader import getModelByName

from xgds_plot import settings, pylabUtil
from xgds_plot import csvutil
from xgds_plot.csvutil import q

# pylint: disable=W0201,E1101

TIME_OFFSET0 = csvutil.TIME_OFFSET0
TIME_OFFSET = csvutil.TIME_OFFSET

TIME_OFFSET_DAYS = float(settings.XGDS_PLOT_TIME_OFFSET_HOURS) / 24

EXPORT_TIME_RESOLUTION = float(settings.XGDS_PLOT_PROFILE_EXPORT_TIME_RESOLUTION_SECONDS) / (60 * 60 * 24)


class Profile(object):
    pass


def firstcaps(val):
    return val[0].upper() + val[1:]


PROFILES = []
PROFILE_LOOKUP = {}


def initProfiles():
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

initProfiles()


def pigeonHole(xp, yp, xi, yi):
    x0 = xi[0, 0]
    y0 = yi[0, 0]
    dx = xi[0, 1] - x0
    dy = yi[1, 0] - y0
    ix = int((xp - x0) / dx + 0.5)
    iy = int((yp - y0) / dy + 0.5)
    ny, nx = xi.shape
    if ((ix < nx) and
            (0 <= iy < ny)):
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


def griddata(x, y, z, xi, yi, fillRight=True):
    zi = np.ma.masked_all(xi.shape, dtype='float64')
    count = np.zeros(xi.shape, dtype='int')
    for xp, yp, zp in zip(x, y, z):
        coords = pigeonHole(xp, yp, xi, yi)
        if coords is None:
            continue
        c = count[coords]
        if c:
            zi[coords] = float(c * zi[coords] + zp) / (c + 1)
        else:
            zi[coords] = zp
        count[coords] = c + 1

    if fillRight:
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
    qs = profile.model.objects.all()
    filterKwargs = {}
    for field, val in profile.filter:
        filterKwargs[field] = val
    if minTime is not None:
        filterKwargs[profile.timestampField + '__gte'] = minTime
    if maxTime is not None:
        filterKwargs[profile.timestampField + '__lte'] = maxTime
    qs = qs.filter(**filterKwargs)
    return qs


def getValueTuples(profile, rawRecs):
    t = []
    z = []
    v = []
    for rec in rawRecs:
        if not rec.valid:
            continue

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


def getMeshGrid(t, z, minT=None, maxT=None, export=False):
    if minT is None:
        minT = t.min()
    if maxT is None:
        maxT = t.max()

    nt = settings.XGDS_PLOT_PROFILE_TIME_GRID_RESOLUTION
    intervalStart = minT + TIME_OFFSET_DAYS
    if export:
        dt = EXPORT_TIME_RESOLUTION
        intervalStart = int(float(intervalStart) / dt) * dt
    else:
        dt = float(maxT - minT) / nt
    tvals = np.arange(intervalStart,
                      maxT + TIME_OFFSET_DAYS,
                      dt)

    if 0:
        minZ = z.min()
        maxZ = z.max()
        nz = settings.XGDS_PLOT_PROFILE_Z_GRID_RESOLUTION
        dz = float(maxZ - minZ) / nz
        zvals = np.arange(minZ, maxZ, dz)

    zvals = np.arange(*settings.XGDS_PLOT_PROFILE_Z_RANGE)

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
                        sizePixels,
                        showSamplePoints=True):
    xpix, ypix = sizePixels
    xinch, yinch = xpix / 100, ypix / 100
    fig = plt.figure()

    # suppress outliers
    minLevel = percentile(z, 1.0)
    maxLevel = percentile(z, 99.0)
    logging.info('getContourPlotImage minLevel=%s maxLevel=%s', minLevel, maxLevel)
    norm = matplotlib.colors.Normalize(minLevel, maxLevel)

    dist = maxLevel - minLevel
    minPad = minLevel - 0.05 * dist
    maxPad = maxLevel + 0.05 * dist
    cappedZi = np.maximum(zi, minPad)
    cappedZi = np.minimum(cappedZi, maxPad)

    logging.info('getContourPlotImage: plotting data')
    ax = fig.gca()
    contours = ax.contourf(xi, yi, cappedZi, 256, norm=norm)
    pylabUtil.setXAxisDate()

    fig.colorbar(contours)

    if showSamplePoints:
        logging.info('getContourPlotImage: plotting sample points')

        # suppress scatterplot points outside the contourf grid
        inRange = reduce(np.logical_and,
                         [xi.min() <= x,
                          x <= xi.max(),
                          yi.min() <= y,
                          y <= yi.max()],
                         True)
        rng = np.where(inRange)

        ax.hold(True)
        # add scatterplot sample points to figure
        ax.scatter(x[rng], y[rng], s=0.5, c='k')

    # force the plot limits we want. note the inversion of yi.max() and yi.min()
    # so increasing depth is down.
    logging.info('getContourPlotImage: configuring axes')
    ax.axis([xi.min(), xi.max(), yi.max(), yi.min()])

    logging.info('getContourPlotImage: writing image')
    plt.setp(fig, figwidth=xinch, figheight=yinch)
    fig.savefig(out,
                format='png',
                bbox_inches='tight',
                dpi=100,
                pad_inches=0.05,
                # transparent=True,
                )

    logging.info('getContourPlotImage: releasing memory')
    fig.clf()
    plt.close(fig)


def numFromDateOrNone(dt):
    if dt:
        return matplotlib.dates.date2num(dt)
    else:
        return None


def getProfileData(profile,
                   minTime=None,
                   maxTime=None,
                   fillRight=True,
                   export=False):
    if minTime:
        paddedMinTime = minTime - datetime.timedelta(days=7)
    else:
        paddedMinTime = None

    rawRecs = getRawRecs(profile, paddedMinTime, maxTime)
    t, z, v = np.array(getValueTuples(profile, rawRecs))
    ti, zi = getMeshGrid(t, z,
                         numFromDateOrNone(minTime),
                         numFromDateOrNone(maxTime),
                         export=export)
    vi = griddata(t, z, v, ti, zi, fillRight)

    return t, z, v, ti, zi, vi


def intIfInt(z):
    if z == int(z):
        return int(z)
    else:
        return z


def blankIfMissing(v):
    if v in (None, np.ma.masked):
        return ''
    else:
        return str(v)


def writeProfileCsv(out, layerId,
                    minTime=None,
                    maxTime=None,
                    fill=True):
    profile = PROFILE_LOOKUP[layerId]

    t, z, v, ti, zi, vi = getProfileData(profile, minTime, maxTime,
                                         fill, export=True)

    tvals = ti[0, :].ravel()
    zvals = [intIfInt(z) for z in zi[:, 0].ravel()]

    if minTime:
        minTimeNum = numFromDateOrNone(minTime)
        rng = np.where(tvals > minTimeNum)[0]
        ti = ti[:, rng]
        zi = zi[:, rng]
        vi = vi[:, rng]
        tvals = ti[0, :].ravel()
        #print 'tvals:', tvals.shape
        #print 'rng:', rng
        #print 'ti:', ti.shape

    time1, time2 = csvutil.getTimeHeaders()

    csvutil.writerow(out, [q(h) for h in time1] + [q('z%s') % z for z in zvals])
    csvutil.writerow(out, [q(h) for h in time2] + [q('z=%s' % z) for z in zvals])
    for i, t in enumerate(tvals):
        localizedDt = (matplotlib.dates.num2date(t)
                       .replace(microsecond=0, tzinfo=None))
        csvutil.writerow(out,
                         [str(v) for v in csvutil.getTimeVals(localizedDt)]
                         + [blankIfMissing(v) for v in vi[:, i].ravel()])


def saveProfileCsv(layerId,
                   minTime=None,
                   maxTime=None,
                   fill=True):
    path = '%s.csv' % layerId
    logging.info('saving profile csv to %s', path)
    out = open(path, 'w')
    writeProfileCsv(out, layerId, minTime, maxTime, fill)
    out.close()


def getProfileCsvData(layerId,
                      minTime=None,
                      maxTime=None,
                      fill=True):
    out = StringIO()
    writeProfileCsv(out, layerId,
                    minTime, maxTime, fill)
    return out.getvalue()


def writeProfileContourPlotImage(out, layerId,
                                 widthPix, heightPix,
                                 minTime=None,
                                 maxTime=None,
                                 showSamplePoints=True):
    profile = PROFILE_LOOKUP[layerId]

    t, z, v, ti, zi, vi = getProfileData(profile, minTime, maxTime)
    logging.warning('writeProfileContourPlotImage minTime=%s maxTime=%s',
                    minTime, maxTime)

    sizePixels = (settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION,
                  settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION)
    getContourPlotImage(out,
                        t, z, v,
                        ti, zi, vi,
                        profile.timeLabel, profile.zLabel,
                        sizePixels,
                        showSamplePoints)


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
                                   maxTime=None,
                                   showSamplePoints=True):
    out = StringIO()
    writeProfileContourPlotImage(out, layerId,
                                 widthPix, heightPix,
                                 minTime, maxTime,
                                 showSamplePoints)
    return out.getvalue()


def getProfileContourPlotImageDataMultiprocessing(layerId,
                                                  widthPix,
                                                  heightPix,
                                                  minTime=None,
                                                  maxTime=None,
                                                  showSamplePoints=True):
    pool = multiprocessing.Pool(processes=1)
    imgData = pool.apply(getProfileContourPlotImageData,
                         (layerId,
                          widthPix,
                          heightPix,
                          minTime,
                          maxTime,
                          showSamplePoints))
    pool.close()
    pool.join()
    return imgData


def testProfiles():
    now = datetime.datetime.utcnow()
    ago = now - datetime.timedelta(days=3)

    #s = getProfileContourPlotImageDataMultiprocessing('waterTemperature',
    #                                                  widthPix=1000, heightPix=200,
    #                                                  minTime=ago, maxTime=now)
    #print 'data len:', len(s)

    for f in settings.XGDS_PLOT_PROFILES:
        saveProfileContourPlotImage(f['valueField'], minTime=ago, maxTime=now)
        saveProfileCsv(f['valueField'], minTime=ago, maxTime=now)


def main():
    import optparse
    parser = optparse.OptionParser('usage: %prog')
    _opts, args = parser.parse_args()
    if args:
        parser.error('expected no args')
    logging.basicConfig(level=logging.DEBUG)
    testProfiles()


if __name__ == '__main__':
    main()
