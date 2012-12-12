# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import time
from cStringIO import StringIO
import re
import datetime
import iso8601

from django.shortcuts import render_to_response
from django.http import HttpResponse, \
     HttpResponseRedirect, \
     HttpResponseForbidden, \
     Http404, \
     HttpResponseBadRequest
from django.template import RequestContext
from django.core.urlresolvers import reverse

from geocamUtil import anyjson as json
from geocamUtil import KmlUtil

from xgds_plot import settings
try:
    from xgds_plot import meta, tile, profiles
except ImportError:
    print 'warning: scipy is not available; some views will not work'

MAP_DATA_PATH = os.path.join(settings.DATA_URL,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')

FLOAT_REGEX = re.compile(r'^-?\d+(\.\d*)?$')



def dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def getMeta(request):
    return HttpResponse(dumps(meta.TIME_SERIES),
                        mimetype='application/json')


def now(request):
    return HttpResponse(unicode(int(time.time() * 1000)).encode('utf-8'),
                        mimetype='text/plain; charset="utf-8"')

def plots(request):
    timeSeriesNamesString = request.GET.get('s')

    requestParams = {}

    if timeSeriesNamesString is not None:
        if timeSeriesNamesString:
            timeSeriesNames = timeSeriesNamesString.split(',')
        else:
            timeSeriesNames = []
        requestParams['timeSeriesNames'] = timeSeriesNames

        # sanity check
        for name in timeSeriesNames:
            if name not in meta.TIME_SERIES_LOOKUP:
                return HttpResponseBadRequest('unknown time series %s' % name)

    exportFields = ('DATA_URL',
                    'XGDS_PLOT_DATA_SUBDIR',
                    'SCRIPT_NAME',
                    'XGDS_ZMQ_WEB_SOCKET_URL',
                    'XGDS_PLOT_LIVE_PLOT_HISTORY_LENGTH_MS',
                    'XGDS_PLOT_SEGMENT_RESOLUTION',
                    'XGDS_PLOT_MIN_DISPLAY_RESOLUTION',
                    'XGDS_PLOT_MIN_DATA_INTERVAL_MS',
                    'XGDS_PLOT_MAX_SEGMENT_LENGTH_MS',
                    'XGDS_PLOT_LIVE_MODE_DEFAULT',
                    'XGDS_PLOT_CHECK_FOR_NEW_DATA',
                    'XGDS_PLOT_TIME_OFFSET_HOURS',
                    'XGDS_PLOT_TIME_ZONE_NAME'
                    )
    exportSettings = dict(((k, getattr(settings, k)) for k in exportFields))
    return render_to_response('xgds_plot/plots.html',
                              {'settings': dumps(exportSettings),
                               'requestParams': dumps(requestParams)},
                              context_instance=RequestContext(request))

def mapIndexKml(request):
    out = StringIO()
    out.write("""
<Document>
  <name>Raster Maps</name>
""")
    for layerOpts in meta.TIME_SERIES:
        if 'map' in layerOpts:
            layerUrl = (request.build_absolute_uri
                        (reverse
                         ('xgds_plot_mapKml',
                          args=[layerOpts['valueCode']])))
            out.write("""
<NetworkLink>
  <name>%(name)s</name>
  <visibility>0</visibility>
  <Link>
    <href>%(layerUrl)s</href>
  </Link>
</NetworkLink>
"""
                      % dict(name=layerOpts['valueName'],
                             layerUrl=layerUrl))
    out.write("</Document>")
    return KmlUtil.wrapKmlDjango(out.getvalue())


def mapKml(request, layerId):
    layerOpts = meta.TIME_SERIES_LOOKUP[layerId]
    initialTile = tile.getTileContainingBounds(settings.XGDS_PLOT_MAP_BBOX)
    level, x, y = initialTile
    initialTileUrl = (request.build_absolute_uri
                      (reverse
                       ('xgds_plot_mapTileKml',
                        args=(layerId, level, x, y))))
    legendUrl = request.build_absolute_uri('%s/%s/colorbar.png'
                                           % (MAP_DATA_PATH,
                                              layerId))
    return KmlUtil.wrapKmlDjango("""
<Document>
  <name>%(name)s</name>
  <NetworkLink>
    <name>Data</name>
    <visibility>0</visibility>
    <Link>
      <href>%(initialTileUrl)s</href>
    </Link>
  </NetworkLink>
  <ScreenOverlay>
    <name>Legend</name>
    <visibility>0</visibility>
    <overlayXY x="0" y="1" xunits="fraction" yunits="fraction"/>
    <screenXY x="0" y="0.25" xunits="fraction" yunits="fraction"/>
    <Icon>
      <href>%(legendUrl)s</href>
    </Icon>
  </ScreenOverlay>
</Document>
""" % dict(name=layerOpts['valueName'],
           initialTileUrl=initialTileUrl,
           legendUrl=legendUrl))


def mapTileKml(request, layerId, level, x, y):
    level = int(level)
    x = int(x)
    y = int(y)

    # make links to sub-tiles if necessary
    if level < settings.XGDS_PLOT_MAP_ZOOM_RANGE[1] - 1:
        linkList = []
        subLevel = level + 1
        for offset in ((0, 0), (0, 1), (1, 0), (1, 1)):
            subX = 2 * x + offset[0]
            subY = 2 * y + offset[1]
            subUrl = (request.build_absolute_uri
                      (reverse
                       ('xgds_plot_mapTileKml',
                        args=[layerId, subLevel, subX, subY])))
            linkList.append("""
<NetworkLink>
  <Region>
    %(box)s
    <Lod>
      <minLodPixels>%(minLodPixels)s</minLodPixels>
      <maxLodPixels>-1</maxLodPixels>
    </Lod>
  </Region>
  <Link>
    <href>%(subUrl)s</href>
    <viewRefreshMode>onRegion</viewRefreshMode>
  </Link>
</NetworkLink>
""" % dict(box=tile.getLatLonAltBox(tile.getTileBounds(subLevel, subX, subY)),
           subUrl=subUrl,
           minLodPixels=settings.XGDS_PLOT_MAP_PIXELS_PER_TILE // 2))
        netLinks = '\n'.join(linkList)
    else:
        netLinks = ''

    #tileUrl = request.build_absolute_uri(reverse('mapTileImage', args=[level, x, y]))
    tileUrl = request.build_absolute_uri('%s/%s/%d/%d/%d.png'
                                         % (MAP_DATA_PATH,
                                            layerId,
                                            level, x, y))
    bounds = tile.getTileBounds(level, x, y)
    minZoom, maxZoom = settings.XGDS_PLOT_MAP_ZOOM_RANGE
    if level < maxZoom - 1:
        maxLodPixels = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE * 2
    else:
        maxLodPixels = -1
    if level > minZoom:
        minLodPixels = settings.XGDS_PLOT_MAP_PIXELS_PER_TILE // 2
    else:
        minLodPixels = -1
    return KmlUtil.wrapKmlDjango("""
<Folder>
  %(netLinks)s
  <GroundOverlay>
    <Icon>
      <href>%(tileUrl)s</href>
      <refreshMode>onInterval</refreshMode>
      <refreshInterval>5</refreshInterval>
    </Icon>
    %(llBox)s
    <drawOrder>%(level)s</drawOrder>
    <Region>
      %(llaBox)s
      <Lod>
        <minLodPixels>%(minLodPixels)s</minLodPixels>
        <maxLodPixels>%(maxLodPixels)s</maxLodPixels>
      </Lod>
    </Region>
  </GroundOverlay>
  <Style>
    <ListStyle>
      <listItemType>checkHideChildren</listItemType>
    </ListStyle>
  </Style>
</Folder>
""" % dict(netLinks=netLinks,
           llBox=tile.getLatLonBox(bounds),
           llaBox=tile.getLatLonAltBox(bounds),
           tileUrl=tileUrl,
           level=level,
           minLodPixels=minLodPixels,
           maxLodPixels=maxLodPixels))


def mapTileImage(request, level, x, y):
    level = int(level)
    x = int(x)
    y = int(y)

    genTilePath = os.path.join(os.path.dirname(__file__), 'genTile.py')
    coordArgs = ('--west=%s --south=%s --east=%s --north=%s'
                 % tile.getTileBounds(level, x, y))
    fd, outPath = tempfile.mkstemp('-genTileOutput.png')
    os.close(fd)
    ret = dosys('%s %s %s'
                % (genTilePath, coordArgs, outPath))

    if ret == 0:
        img = outPath
        mimetype = 'image/png'
    else:
        # stupid fallback if genTile doesn't work. for example, if matplotlib is not installed.
        img = os.path.join(os.path.dirname(__file__), 'static', 'style', 'isruApp', 'resolveLogo70.png')
        mimetype = 'image/gif'
    try:
        pass  # os.remove(outPath)
    except OSError:
        pass
    return HttpResponse(file(img, 'r').read(),
                        mimetype=mimetype)


def parseTime(timeString):
    # exact match 'now'
    now = datetime.datetime.utcnow()
    if timeString == 'now':
        return now

    # match a float
    m = FLOAT_REGEX.search(timeString)
    if m:
        f = float(timeString)
        if f < 1e+6:
            # interpret small values as delta hours from now
            dt = datetime.timedelta(hours=f)
            return now + dt
        else:
            # interpret large values as Java-style millisecond epoch time
            return datetime.datetime.utcfromtimestamp(f * 1e-3)

    # full ISO 8601 format datetime
    return iso8601.parse_date(timeString)


def profileRender(request, layerId):
    widthPix = int(request.GET.get('w', settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION))
    heightPix = int(request.GET.get('h', settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION))
    minTime = parseTime(request.GET.get('start', '-72'))
    maxTime = parseTime(request.GET.get('end', 'now'))
    imageData = profiles.getProfileContourPlotImageData(layerId,
                                                        widthPix=widthPix,
                                                        heightPix=heightPix,
                                                        minTime=minTime,
                                                        maxTime=maxTime)
    return HttpResponse(imageData,
                        mimetype='image/png')


def profilesPage(request):
    minTime = parseTime(request.GET.get('start', '-72'))
    maxTime = parseTime(request.GET.get('end', 'now'))
    return render_to_response('xgds_plot/profiles.html',
                              {'minTime': minTime,
                               'maxTime': maxTime,
                               'profiles': profiles.PROFILES},
                              context_instance=RequestContext(request))
