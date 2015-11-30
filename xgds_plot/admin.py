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

import datetime

from django.contrib import admin

from xgds_plot.models import TimeSeries
from xgds_plot import forms as plotForms


class TimeSeriesAdmin(admin.ModelAdmin):
    form = plotForms.TimeSeriesFormWithVersionOption

    def save_model(self, request, obj, form, change):
        if obj.pk is not None and form.cleaned_data['saveAsNewVersion']:
            obj.pk = None
            obj.version += 1
        if form.cleaned_data['startIndexingAtCurrentTime']:
            obj.startTime = datetime.datetime.utcnow()
        obj.save()


admin.site.register(TimeSeries, TimeSeriesAdmin)
