# __BEGIN_LICENSE__
#Copyright (c) 2015, United States Government, as represented by the 
#Administrator of the National Aeronautics and Space Administration. 
#All rights reserved.
#
#The xGDS platform is licensed under the Apache License, Version 2.0 
#(the "License"); you may not use this file except in compliance with the License. 
#You may obtain a copy of the License at 
#http://www.apache.org/licenses/LICENSE-2.0.
#
#Unless required by applicable law or agreed to in writing, software distributed 
#under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR 
#CONDITIONS OF ANY KIND, either express or implied. See the License for the 
#specific language governing permissions and limitations under the License.
# __END_LICENSE__

import os
import time
from cStringIO import StringIO
import datetime
import calendar
import tempfile
import logging
import re
import pytz

from django.shortcuts import render_to_response
from django.http import (HttpResponse,
                         HttpResponseNotFound,
                         HttpResponseBadRequest)
from django.template import RequestContext
from django.core.urlresolvers import reverse
import django.db

from geocamUtil import anyjson as json
from geocamUtil import KmlUtil
from geocamUtil.loader import getClassByName

from xgds_plot import settings
from xgds_plot.plotUtil import parseTime
try:
    from xgds_plot import meta, tile, profiles, staticPlot
except ImportError:
    print 'warning: scipy is not available; some views will not work'

MAP_DATA_PATH = os.path.join(settings.DATA_URL,
                             settings.XGDS_PLOT_DATA_SUBDIR,
                             'map')


OPS_TIME_ZONE = pytz.timezone(settings.XGDS_PLOT_OPS_TIME_ZONE)


def utcToTz(t, tz=OPS_TIME_ZONE):
    return pytz.utc.localize(t).astimezone(tz).replace(tzinfo=None)


def tzToUtc(t, tz=OPS_TIME_ZONE):
    return tz.localize(t).astimezone(pytz.utc).replace(tzinfo=None)


def dosys(cmd):
    logging.info(cmd)
    ret = os.system(cmd)
    if ret != 0:
        logging.warning('command exited with non-zero return value %s', ret)
    return ret


def dumps(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def getMeta(request):
    return HttpResponse(dumps(meta.TIME_SERIES),
                        content_type='application/json')


def now(request):
    return HttpResponse(unicode(int(time.time() * 1000)).encode('utf-8'),
                        content_type='text/plain; charset="utf-8"')


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
                    'XGDS_PLOT_TIME_ZONE_NAME',
                    'XGDS_PLOT_LIVE_PLOT_FUTURE_TIME_MS',
                    )
    exportSettings = dict(((k, getattr(settings, k)) for k in exportFields))

    if request.META['wsgi.url_scheme'] == 'https':
        # must use secure WebSockets if web site is secure
        exportSettings['XGDS_ZMQ_WEB_SOCKET_URL'] = re.sub(r'^ws:', 'wss:',
                                                           exportSettings['XGDS_ZMQ_WEB_SOCKET_URL'])

    return render_to_response('xgds_plot/plots.html',
                              {'settings': dumps(exportSettings),
                               'requestParams': dumps(requestParams)},
                              context_instance=RequestContext(request))


def mapIndexKml(request):
    out = StringIO()
    writeMapIndexKml(request, out)
    return KmlUtil.wrapKmlDjango(out.getvalue())


def writeMapIndexKml(request, out):
    out.write("""
  <Document>
    <name>Raster Maps</name>
    <open>1</open>
""")

    getDatesFn = getClassByName(settings.XGDS_PLOT_GET_DATES_FUNCTION)
    dates = list(reversed(sorted(getDatesFn())))

    nowTime = utcToTz(datetime.datetime.utcnow())
    today = nowTime.date()

    if len(dates) >= 4 and dates[0] == today:
        # Put past days in a separate folder to avoid clutter. The user
        # is most likely to be interested in today's data.
        dates = [dates[0]] + ['pastDaysStart'] + dates[1:] + ['pastDaysEnd']

    for day in dates:
        if day == 'pastDaysStart':
            out.write('<Folder><name>Past Days</name>\n')
            continue
        elif day == 'pastDaysEnd':
            out.write('</Folder>\n')
            continue

        isToday = (day == today)
        writeMapIndexKmlForDay(request, out, day, isToday)

    out.write("""
  </Document>
""")


def writeMapIndexKmlForDay(request, out, day, isToday):
    if isToday:
        dateStr = 'Today'
    else:
        dateStr = day.strftime('%Y-%m-%d')

    out.write("""
<Folder>
  <name>%(dateStr)s</name>
""" % dict(dateStr=dateStr))
    for layerOpts in meta.TIME_SERIES:
        if 'map' in layerOpts:
            writeMapIndexKmlForDayAndLayer(request, out, day, layerOpts)
    out.write("</Folder>")


def writeMapIndexKmlForDayAndLayer(request, out, day, layerOpts):
    initialTile = tile.getTileContainingBounds(settings.XGDS_PLOT_MAP_BBOX)
    level, x, y = initialTile
    dayCode = day.strftime('%Y%m%d')
    initialTileUrl = (request.build_absolute_uri
                      (reverse
                       ('xgds_plot_mapTileKml',
                        args=(layerOpts['valueCode'], dayCode, level, x, y))))
    legendUrl = request.build_absolute_uri('%s/%s/colorbar.png'
                                           % (MAP_DATA_PATH,
                                              layerOpts['valueCode']))

    out.write("""
  <Folder><name>%(name)s</name>\n
  <NetworkLink>
    <name>Data</name>
    <visibility>0</visibility>
    <Style>
      <ListStyle>
        <listItemType>checkHideChildren</listItemType>
      </ListStyle>
    </Style>
    <Link>
      <href>%(initialTileUrl)s</href>
    </Link>
  </NetworkLink>
""" % dict(name=layerOpts['valueName'],
           initialTileUrl=initialTileUrl))

    out.write("""
   <ScreenOverlay>
     <name>Legend</name>
     <visibility>0</visibility>
     <overlayXY x="0" y="1" xunits="fraction" yunits="fraction"/>
     <screenXY x="0" y="0.25" xunits="fraction" yunits="fraction"/>
     <Icon>
       <href>%(legendUrl)s</href>
     </Icon>
   </ScreenOverlay>
   </Folder>
 """ % dict(legendUrl=legendUrl))



# def writeMapKmlForLayerDay(request, out, layerId, layerOpts, day, isToday):
#     if isToday:
#         dateStr = 'Today'
#     else:
#         dateStr = day.strftime('%Y-%m-%d')

#     initialTile = tile.getTileContainingBounds(settings.XGDS_PLOT_MAP_BBOX)
#     level, x, y = initialTile
#     dayCode = day.strftime('%Y%m%d')
#     initialTileUrl = (request.build_absolute_uri
#                       (reverse
#                        ('xgds_plot_mapTileKml',
#                         args=(layerId, dayCode, level, x, y))))

#     out.write("""
#   <NetworkLink>
#     <name>%(name)s</name>
#     <visibility>0</visibility>
#     <Style>
#       <ListStyle>
#         <listItemType>checkHideChildren</listItemType>
#       </ListStyle>
#     </Style>
#     <Link>
#       <href>%(initialTileUrl)s</href>
#     </Link>
#   </NetworkLink>
# """ % dict(name=dateStr,
#            initialTileUrl=initialTileUrl))


# def writeMapKmlDataFolder(request, out, layerId, layerOpts):
#     out.write("""
#   <name>%(name)s</name>
#   <Folder>
#     <name>Data</name>
#     <open>1</open>
# """ % dict(name=layerOpts['valueName']))

#     queryClass = getClassByName(layerOpts['queryType'])
#     queryManager = queryClass(layerOpts)
#     dates = list(reversed(sorted(queryManager.getDatesWithData())))

#     nowTime = utcToTz(datetime.datetime.utcnow())
#     today = nowTime.date()

#     if len(dates) >= 4 and dates[0] == today:
#         # Put past days in a separate folder to avoid clutter. The user
#         # is most likely to be interested in today's data.
#         dates = [dates[0]] + ['pastDaysStart'] + dates[1:] + ['pastDaysEnd']

#     for day in dates:
#         if day == 'pastDaysStart':
#             out.write('<Folder><name>Past Days</name>\n')
#             continue
#         elif day == 'pastDaysEnd':
#             out.write('</Folder>\n')
#             continue

#         isToday = (day == today)
#         writeMapKmlForLayerDay(request, out, layerId, layerOpts, day, isToday)

#     out.write("""
#   </Folder>
# """)


# def mapKml(request, layerId):
#     layerOpts = meta.TIME_SERIES_LOOKUP[layerId]
#     legendUrl = request.build_absolute_uri('%s/%s/colorbar.png'
#                                            % (MAP_DATA_PATH,
#                                               layerId))

#     out = StringIO()
#     out.write("""<?xml version="1.0" encoding="UTF-8"?>
# <kml xmlns="http://www.opengis.net/kml/2.2"
#      xmlns:gx="http://www.google.com/kml/ext/2.2"
#      xmlns:kml="http://www.opengis.net/kml/2.2"
#      xmlns:atom="http://www.w3.org/2005/Atom">
# <Document>
#   <name>Tracks</name>
#   <open>1</open>
# """)

#     writeMapKmlDataFolder(request, out, layerId, layerOpts)

#     out.write("""
#   <ScreenOverlay>
#     <name>Legend</name>
#     <visibility>0</visibility>
#     <overlayXY x="0" y="1" xunits="fraction" yunits="fraction"/>
#     <screenXY x="0" y="0.25" xunits="fraction" yunits="fraction"/>
#     <Icon>
#       <href>%(legendUrl)s</href>
#     </Icon>
#   </ScreenOverlay>
# """ % dict(legendUrl=legendUrl))

#     out.write("""
# </Document>
# </kml>
# """)
#     return HttpResponse(out.getvalue(), content_type='application/vnd.google-earth.kml+xml')


def mapTileKml(request, layerId, dayCode, level, x, y):
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
                        args=[layerId, dayCode, subLevel, subX, subY])))
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
""" %
                            dict(box=tile.getLatLonAltBox(tile.getTileBounds(subLevel, subX, subY)),
                                 subUrl=subUrl,
                                 minLodPixels=settings.XGDS_PLOT_MAP_PIXELS_PER_TILE // 2))
        netLinks = '\n'.join(linkList)
    else:
        netLinks = ''

    #tileUrl = request.build_absolute_uri(reverse('mapTileImage', args=[level, x, y]))
    tileUrl = request.build_absolute_uri('%s/%s/%s/%d/%d/%d.png'
                                         % (MAP_DATA_PATH,
                                            layerId,
                                            dayCode,
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


def mapTileImage(request, dayCode, level, x, y):
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
                        content_type=mimetype)


def javaStyle(dt):
    return int(calendar.timegm(dt.timetuple()) * 1e+3)


def shortTime(dt):
    return dt.strftime('%Y-%m-%d %H:%M')


def profileRender(request, layerId):
    widthPix = int(request.GET.get('w', settings.XGDS_PLOT_PROFILE_TIME_PIX_RESOLUTION))
    heightPix = int(request.GET.get('h', settings.XGDS_PLOT_PROFILE_Z_PIX_RESOLUTION))
    offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
    minTime = parseTime(request.GET.get('start', '-72'), offset)
    maxTime = parseTime(request.GET.get('end', 'now'), offset)
    assert minTime <= maxTime, 'HTTP GET parameters: start, end: start time must be before end time'
    # submitted = request.GET.get('submit') is not None
    showSamplePoints = int(request.GET.get('pts', '1'))
    assert showSamplePoints in (0, 1), 'HTTP GET parameters: pts: specify either 0 or 1'
    imageData = (profiles.getProfileContourPlotImageDataMultiprocessing
                 (layerId,
                  widthPix=widthPix,
                  heightPix=heightPix,
                  minTime=minTime,
                  maxTime=maxTime,
                  showSamplePoints=showSamplePoints))
    django.db.reset_queries()  # clear query log to reduce memory usage
    return HttpResponse(imageData,
                        content_type='image/png')


def profileCsv(request, layerId):
    offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
    minTime = parseTime(request.GET.get('start', '-72'), offset)
    maxTime = parseTime(request.GET.get('end', 'now'), offset)
    assert minTime <= maxTime, 'HTTP GET parameters: start, end: start time must be before end time'
    fill = int(request.GET.get('fill', '1'))
    assert fill in (0, 1), 'HTTP GET parameters: fill: specify either 0 or 1'
    csvData = profiles.getProfileCsvData(layerId,
                                         minTime=minTime,
                                         maxTime=maxTime,
                                         fill=fill)
    django.db.reset_queries()  # clear query log to reduce memory usage
    return HttpResponse(csvData,
                        content_type='text/csv')


def profilesPage(request):
    offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
    minTime = parseTime(request.GET.get('start', '-72'), offset)
    maxTime = parseTime(request.GET.get('end', 'now'), offset)
    assert minTime <= maxTime, 'HTTP GET parameters: start, end: start time must be before end time'
    showSamplePoints = int(request.GET.get('pts', '1'))
    assert showSamplePoints in (0, 1), 'HTTP GET parameters: pts: specify either 0 or 1'
    return render_to_response('xgds_plot/profiles.html',
                              {'minTime': javaStyle(minTime),
                               'maxTime': javaStyle(maxTime),
                               'showSamplePoints': showSamplePoints,
                               'minDisplayTime': shortTime(minTime + offset),
                               'maxDisplayTime': shortTime(maxTime + offset),
                               'displayTimeZone': settings.XGDS_PLOT_TIME_ZONE_NAME,
                               'profiles': profiles.PROFILES},
                              context_instance=RequestContext(request))


def getStaticPlot(request, seriesId):
    if seriesId not in meta.TIME_SERIES_LOOKUP:
        return HttpResponseNotFound('<h1>404 No time series named "%s"</h1>' % seriesId)

    offset = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
    minTime = parseTime(request.GET.get('start', '-72'), offset)
    maxTime = parseTime(request.GET.get('end', 'now'), offset)
    assert minTime <= maxTime, 'HTTP GET parameters: start, end: start time must be before end time'

    widthPix = int(request.GET.get('w', '800'))
    heightPix = int(request.GET.get('h', '120'))

    imgData = (staticPlot.getPlotDataMultiprocessing
               (seriesId,
                widthPix,
                heightPix,
                javaStyle(minTime),
                javaStyle(maxTime)))
    django.db.reset_queries()  # clear query log to reduce memory usage
    return HttpResponse(imgData,
                        content_type='image/png')
