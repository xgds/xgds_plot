
import datetime
import calendar

from xgds_plot import settings

TIME_OFFSET0 = datetime.timedelta(hours=settings.XGDS_PLOT_TIME_OFFSET_HOURS)
# ensure integer number of seconds for convenience
TIME_OFFSET = datetime.timedelta(seconds=int(TIME_OFFSET0.total_seconds()))


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
