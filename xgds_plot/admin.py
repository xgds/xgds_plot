# __BEGIN_LICENSE__
# Copyright (C) 2008-2010 United States Government as represented by
# the Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# __END_LICENSE__

from django.contrib import admin

from xgds_plot.models import TimeSeries


class TimeSeriesAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.preSaveVersionIncrementIfNeeded()
        obj.save()


admin.site.register(TimeSeries, TimeSeriesAdmin)
