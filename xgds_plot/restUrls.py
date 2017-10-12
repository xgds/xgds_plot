#__BEGIN_LICENSE__
# Copyright (c) 2015, United States Government, as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All rights reserved.
#
# The xGDS platform is licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#__END_LICENSE__

# pylint: disable=E1120

from django.conf.urls import url
from django.core.urlresolvers import reverse_lazy

from django.views.generic.base import RedirectView
from xgds_plot import views

urlpatterns = [url(r'^now/$', views.now, {}, name='xgds_plot_now'),
               url(r'^meta.json$', views.getMeta, {}, name='xgds_plot_meta'),
               url(r'^mapIndex\.kml$', views.mapIndexKml, {},'xgds_plot_mapIndexKml'),
              #url(r'^mapLayer_(?P<layerId>[^\.]+)\.kml$', views.mapKml, {}, 'xgds_plot_mapKml'),
               url(r'^mapTile/(?P<layerId>[^/]+)/(?P<dayCode>\d+)/(?P<level>\d+)/(?P<x>\d+)/(?P<y>\d+)\.kml$', views.mapTileKml, {}, 'xgds_plot_mapTileKml'),
               url(r'^profile/(?P<layerId>[^\.]*)\.png$', views.profileRender, {}, 'xgds_plot_profileRender'),
               url(r'^profile/(?P<layerId>[^\.]*)\.csv$', views.profileCsv, {}, 'xgds_plot_profileCsv'),
               url(r'staticPlot/(?P<seriesId>[^\.]+)\.png', views.getStaticPlot, {}, 'xgds_plot_staticPlot'),
               ]
