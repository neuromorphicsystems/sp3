from __future__ import annotations
import astropy.time
import astropy.units
import datetime
import enum


def time_with_utc_tzinfo(time: datetime.datetime):
    return datetime.datetime(
        year=time.year,
        month=time.month,
        day=time.day,
        hour=time.hour,
        minute=time.minute,
        second=time.second,
        microsecond=time.microsecond,
        tzinfo=datetime.timezone.utc,
    )


class TimeSystem(enum.Enum):
    GPS = b"GPS"
    GLONASS = b"GLO"
    GALILEO = b"GAL"
    BEIDOU = b"BDT"
    TAI = b"TAI"
    UTC = b"UTC"
    IRNSS = b"IRN"
    QZSS = b"QZS"

    def time_to_utc(self, time: datetime.datetime) -> datetime.datetime:
        if (
            self == TimeSystem.GPS
            or self == TimeSystem.IRNSS
            or self == TimeSystem.QZSS
        ):
            return (
                astropy.time.Time(time, scale="tai")
                + astropy.time.TimeDelta(19.0 * astropy.units.s)
            ).utc.to_datetime(timezone=datetime.timezone.utc)
        if self == TimeSystem.GLONASS:
            return time - datetime.timedelta(hours=3)
        if self == TimeSystem.GALILEO or self == TimeSystem.TAI:
            return astropy.time.Time(time, scale="tai").utc.to_datetime(
                timezone=datetime.timezone.utc
            )
        if self == TimeSystem.BEIDOU or self == TimeSystem.UTC:
            return time
        raise Exception("unsupported time system")

    def time_from_utc(self, time: datetime.datetime) -> datetime.datetime:
        if (
            self == TimeSystem.GPS
            or self == TimeSystem.IRNSS
            or self == TimeSystem.QZSS
        ):
            return time_with_utc_tzinfo(
                (
                    astropy.time.Time(time, scale="utc").tai
                    - astropy.time.TimeDelta(19.0 * astropy.units.s)
                ).datetime
            )
        if self == TimeSystem.GLONASS:
            return time + datetime.timedelta(hours=3)
        if self == TimeSystem.GALILEO or self == TimeSystem.TAI:
            return time_with_utc_tzinfo(
                astropy.time.Time(time, scale="utc").tai.datetime
            )
        if self == TimeSystem.BEIDOU or self == TimeSystem.UTC:
            return time
        raise Exception("unsupported time system")

    def offset_seconds(self, time: datetime.datetime, offset: float):
        if (
            self == TimeSystem.GPS
            or self == TimeSystem.IRNSS
            or self == TimeSystem.QZSS
            or self == TimeSystem.GALILEO
            or self == TimeSystem.TAI
        ):
            return time_with_utc_tzinfo(
                (
                    astropy.time.Time(time, scale="utc").tai
                    + astropy.time.TimeDelta(offset * astropy.units.s)
                ).datetime
            )
        elif (
            self == TimeSystem.GLONASS
            or self == TimeSystem.BEIDOU
            or self == TimeSystem.UTC
        ):
            return time + datetime.timedelta(seconds=offset)
        raise Exception("unsupported time system")
