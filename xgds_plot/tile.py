# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

import os
import math
import sys
import tempfile
from cStringIO import StringIO

from django.core.urlresolvers import reverse
from django.http import HttpResponse

from geocamUtil import KmlUtil

from xgds_plot import settings
from xgds_plot import meta

EARTH_RADIUS_METERS = 6371 * 1000
METERS_PER_DEGREE = 2 * math.pi * EARTH_RADIUS_METERS / 360
DATA_PATH = os.path.join(settings.DATA_DIR,
                         settings.XGDS_PLOT_DATA_SUBDIR,
                         'map')


def dosys(cmd):
    ret = os.system(cmd)
    if ret != 0:
        print >> sys.stderr, 'warning: command exited with non-zero return value %d' % ret
        print >> sys.stderr, '  command was: %s' % cmd
    return ret


def getTileBounds(level, x, y):
    tileSize = 360.0 / 2 ** level
    west = -180 + x * tileSize
    south = -90 + y * tileSize
    east = west + tileSize
    north = south + tileSize
    return west, south, east, north


def getTileContainingPoint(level, lon, lat):
    tileSize = 360.0 / 2 ** level
    x = int((lon - (-180) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize)
    y = int((lat - (-90) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize)
    return x, y


def getPixelOfLonLat(level, lon, lat):
    tileSize = 360.0 / 2 ** level
    xf = (lon - (-180) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize
    x = int(xf)
    i = int(settings.XGDS_PLOT_MAP_PIXELS_PER_TILE * (xf - x))
    yf = (lat - (-90) + settings.XGDS_PLOT_MAP_TILE_EPS) / tileSize
    y = int(yf)
    j = int(settings.XGDS_PLOT_MAP_PIXELS_PER_TILE * (1.0 - (yf - y)))
    return x, y, i, j


def getTileContainingBounds(bounds):
    west, south, east, north = bounds
    diam = max(east - west, south - north) - settings.XGDS_PLOT_MAP_TILE_EPS
    level = int(math.floor(math.log(360.0 / diam, 2)))
    while 1:
        x, y = getTileContainingPoint(level, west, south)
        _tileWest, _tileSouth, tileEast, tileNorth = getTileBounds(level, x, y)
        if (east <= tileEast + settings.XGDS_PLOT_MAP_TILE_EPS
            and north <= tileNorth + settings.XGDS_PLOT_MAP_TILE_EPS):
            break
        level -= 1
    return level, x, y


def getTilesOverlappingBounds(bounds, levels=None):
    zoomMin, zoomMax = settings.XGDS_PLOT_MAP_ZOOM_RANGE
    if levels == None:
        levels = xrange(zoomMin, zoomMax)
    west, south, east, north = bounds
    for level in levels:
        xmin, ymin = getTileContainingPoint(level, west, south)
        xmax, ymax = getTileContainingPoint(level, east, north)
        for x in xrange(xmin, xmax + 1):
            for y in xrange(ymin, ymax + 1):
                yield level, x, y


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
    initialTile = getTileContainingBounds(settings.XGDS_PLOT_MAP_BBOX)
    level, x, y = initialTile
    initialTileUrl = (request.build_absolute_uri
                      (reverse
                       ('xgds_plot_mapTileKml',
                        args=(layerId, level, x, y))))
    legendUrl = request.build_absolute_uri('%s/%s/colorbar.png'
                                           % (DATA_PATH,
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


def getLatLonBox(bounds):
    return ("""
<LatLonBox>
  <west>%s</west>
  <south>%s</south>
  <east>%s</east>
  <north>%s</north>
</LatLonBox>
""" % bounds)


def getLatLonAltBox(bounds):
    return ("""
<LatLonAltBox>
  <west>%s</west>
  <south>%s</south>
  <east>%s</east>
  <north>%s</north>
</LatLonAltBox>
""" % bounds)


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
""" % dict(box=getLatLonAltBox(getTileBounds(subLevel, subX, subY)),
           subUrl=subUrl,
           minLodPixels=settings.XGDS_PLOT_MAP_PIXELS_PER_TILE // 2))
        netLinks = '\n'.join(linkList)
    else:
        netLinks = ''

    #tileUrl = request.build_absolute_uri(reverse('mapTileImage', args=[level, x, y]))
    tileUrl = request.build_absolute_uri('%s/%s/%d/%d/%d.png'
                                         % (DATA_PATH,
                                            layerId,
                                            level, x, y))
    bounds = getTileBounds(level, x, y)
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
           llBox=getLatLonBox(bounds),
           llaBox=getLatLonAltBox(bounds),
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
                 % getTileBounds(level, x, y))
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


def getMetersPerPixel(level):
    radiansPerTile = 2 * math.pi / 2 ** level
    metersPerTile = radiansPerTile * EARTH_RADIUS_METERS
    return metersPerTile / settings.XGDS_PLOT_MAP_PIXELS_PER_TILE
