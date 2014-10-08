# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.contrib import admin

from xgds_plot.models import TimeSeries
from xgds_plot import forms as plotForms


class TimeSeriesAdmin(admin.ModelAdmin):
    form = plotForms.TimeSeriesFormWithVersionOption

    def save_model(self, request, obj, form, change):
        if obj.pk is not None and form.cleaned_data['saveAsNewVersion']:
            obj.pk = None
            obj.version += 1
        obj.save()


admin.site.register(TimeSeries, TimeSeriesAdmin)
