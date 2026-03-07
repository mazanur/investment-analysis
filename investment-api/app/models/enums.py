import enum


class SentimentEnum(str, enum.Enum):
    bullish = "bullish"
    neutral = "neutral"
    bearish = "bearish"


class PositionEnum(str, enum.Enum):
    buy = "buy"
    hold = "hold"
    sell = "sell"
    watch = "watch"
    avoid = "avoid"


class PeriodTypeEnum(str, enum.Enum):
    quarterly = "quarterly"
    yearly = "yearly"
    ltm = "ltm"


class DividendStatusEnum(str, enum.Enum):
    announced = "announced"
    confirmed = "confirmed"
    paid = "paid"


class CatalystTypeEnum(str, enum.Enum):
    opportunity = "opportunity"
    risk = "risk"
    cb_meeting = "cb_meeting"
    event = "event"


class ImpactEnum(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    mixed = "mixed"
    neutral = "neutral"


class MagnitudeEnum(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class SignalEnum(str, enum.Enum):
    buy = "buy"
    skip = "skip"


class DirectionEnum(str, enum.Enum):
    long_positive = "long-positive"
    long_oversold = "long-oversold"
    skip = "skip"


class PositionSizeEnum(str, enum.Enum):
    full = "full"
    half = "half"
    skip = "skip"


class SignalStatusEnum(str, enum.Enum):
    active = "active"
    closed = "closed"
    expired = "expired"


class StrengthEnum(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ActionEnum(str, enum.Enum):
    buy = "buy"
    hold = "hold"
    sell = "sell"


class JobStatusEnum(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
