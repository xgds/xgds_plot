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

from django.conf.urls import url, include
from django.core.urlresolvers import reverse_lazy

from django.views.generic.base import RedirectView
from xgds_plot import views

urlpatterns = [url(r'^$', RedirectView.as_view(url=reverse_lazy('xgds_plot_plots'), permanent=False), {}, name='xgds_plot_home'),
               url(r'^plots/$', views.plots, {}, name='xgds_plot_plots'),
               url(r'^profiles/', views.profilesPage, {}, 'xgds_plot_profiles'),
               
               # Including these in this order ensures that reverse will return the non-rest urls for use in our server
               url(r'^rest/', include('xgds_plot.restUrls')),
               url('', include('xgds_plot.restUrls')),
               ]
