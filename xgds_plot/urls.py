# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.conf.urls.defaults import url, patterns

urlpatterns = patterns(
    'xgds_plot.views',

    url(r'^plots/$',
        'plots', {},
        name='xgds_plot_plots'),

    url(r'^meta.json$',
        'meta', {},
        name='xgds_plot_meta'),

    url(r'^tile/(?P<datasetCode>[^/]+)/(?P<level>\d+)/(?P<index>\d+)\.json$',
        'tile', {},
        name='xgds_plot_tile'),

    url(r'^now/$',
        'now', {},
        name='xgds_plot_now'),

)
