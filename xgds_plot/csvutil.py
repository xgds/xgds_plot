
import datetime
import calendar

from xgds_plot import settings

try:
    datetime.timedelta().total_seconds
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
             'timestampEpoch',
             ],
            ['Timestamp (UTC)',
             'Timestamp (%s)' % settings.XGDS_PLOT_TIME_ZONE_NAME,
             'Timestamp (seconds since Unix epoch)',
            ])


def getTimeVals(localizedDt):
    utcDt = localizedDt - TIME_OFFSET
    epochTime = calendar.timegm(utcDt.timetuple())
    return [q(str(utcDt)),
            q(str(localizedDt)),
            epochTime]


def writerow(out, vals):
    out.write(','.join(vals) + '\n')
