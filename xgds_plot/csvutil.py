# __BEGIN_LICENSE__
#Copyright © 2015, United States Government, as represented by the 
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

import datetime
import calendar

from xgds_plot import settings

try:
    def total_seconds(delta):
        return delta.total_seconds()
except AttributeError:
    def total_seconds(delta):
        return delta.days * 24 * 60 * 60 + delta.seconds + delta.microseconds * 1e-6


TIME_OFFSET0 = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
# ensure integer number of seconds for convenience
TIME_OFFSET = datetime.timedelta(seconds=int(total_seconds(TIME_OFFSET0)))


def q(s):
    return '"' + s + '"'


def getTimeHeaders():
    return (['timestamp',
             'timestampLocalized',
             'timestampEpoch'],
            ['Timestamp (UTC)',
             'Timestamp (%s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
             'Timestamp (seconds since Unix epoch)'])


def getTimeVals(localizedDt):
    utcDt = localizedDt - TIME_OFFSET
    epochTime = calendar.timegm(utcDt.timetuple())
    return [q(str(utcDt)),
            q(str(localizedDt)),
            epochTime]


def writerow(out, vals):
    out.write(','.join(vals) + '\n')
