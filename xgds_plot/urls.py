# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.conf.urls import url, patterns
from django.core.urlresolvers import reverse_lazy

from django.views.generic.base import RedirectView

urlpatterns = patterns(
    'xgds_plot.views',

    url(r'^$',
        RedirectView.as_view(url=reverse_lazy('xgds_plot_plots'), permanent=False), {},
        name='xgds_plot_home'),

    url(r'^plots/$',
        'plots', {},
        name='xgds_plot_plots'),

    url(r'^meta.json$',
        'getMeta', {},
        name='xgds_plot_meta'),

    url(r'^now/$',
        'now', {},
        name='xgds_plot_now'),

    url(r'^mapIndex\.kml$',
        'mapIndexKml', {'loginRequired': False},
        'xgds_plot_mapIndexKml'),

    url(r'^mapLayer_(?P<layerId>[^\.]+)\.kml$',
        'mapKml', {'loginRequired': False},
        'xgds_plot_mapKml'),

    url(r'^mapTile/(?P<layerId>[^/]+)/(?P<level>\d+)/(?P<x>\d+)/(?P<y>\d+)\.kml$',
        'mapTileKml', {'loginRequired': False},
        'xgds_plot_mapTileKml'),

    url(r'^profile/(?P<layerId>[^\.]*)\.png$',
        'profileRender', {},
        'xgds_plot_profileRender'),

    url(r'^profile/(?P<layerId>[^\.]*)\.csv$',
        'profileCsv', {},
        'xgds_plot_profileCsv'),

    url(r'^profiles/',
        'profilesPage', {},
        'xgds_plot_profiles'),

    url(r'staticPlot/(?P<seriesId>[^\.]+)\.png',
        'getStaticPlot', {},
        'xgds_plot_staticPlot'),
)
