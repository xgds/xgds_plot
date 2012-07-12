# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.conf.urls.defaults import url, patterns

from xgds_plot import tile

urlpatterns = patterns(
    'xgds_plot.views',

    url(r'^plots/$',
        'plots', {},
        name='xgds_plot_plots'),

    url(r'^meta.json$',
        'meta', {},
        name='xgds_plot_meta'),

    url(r'^now/$',
        'now', {},
        name='xgds_plot_now'),

    url(r'^mapIndex\.kml$',
        tile.mapIndexKml, {},
        'xgds_plot_mapIndexKml'),

    url(r'^mapLayer_(?P<layerId>[^\.]+)\.kml$',
        tile.mapKml, {},
        'xgds_plot_mapKml'),

    url(r'^mapTile/(?P<layerId>[^/]+)/(?P<level>\d+)/(?P<x>\d+)/(?P<y>\d+)\.kml$',
        tile.mapTileKml, {},
        'xgds_plot_mapTileKml'),
)
