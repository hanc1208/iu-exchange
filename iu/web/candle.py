import datetime

from flask.blueprints import Blueprint
from flask.globals import request
from flask.json import jsonify

from ..candle import Candle, CandleUnitType
from ..context import session
from ..serializer import serialize

bp_candle = Blueprint('candle', __name__, url_prefix='/candles')


@bp_candle.route(
    '/<base_currency>/<quote_currency>/<unit_type>/<int:unit>/'
)
def fetch_candles(
    base_currency: str, quote_currency: str, unit_type: str, unit: int,
):
    assert unit_type == 'minutes'
    pair = f'{base_currency}/{quote_currency}'
    count = request.values.get('count', 200)
    offset = request.values.get('offset', type=int)
    created_at = None
    unit_key = (unit, CandleUnitType(unit_type))
    if offset:
        created_at = datetime.datetime.utcfromtimestamp(offset // 1000)
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    candles = session.query(Candle).filter(
        Candle.pair == pair,
        Candle.unit_type == CandleUnitType(unit_type),
        Candle.unit == unit,
        Candle.timestamp <= created_at if created_at else True,
    ).order_by(
        Candle.timestamp.desc()
    ).limit(count).all()
    Candle.interpolate(
        session=session, candles=candles, pair=pair, unit_key=unit_key,
    )
    result = sorted(
        [
            {
                'timestamp': int(r.timestamp.timestamp() * 1000),
                'open': r.open,
                'close': r.close,
                'low': r.low,
                'high': r.high,
                'volume': r.volume,
                'quoteVolume': r.quote_volume,
                'unitType': unit_type,
                'unit': unit,
            }
            for r in candles
        ],
        key=lambda r: r['timestamp'],
        reverse=True,
    )
    return jsonify(serialize(result))


@bp_candle.route(
    '/validate/<base_currency>/<quote_currency>/<unit_type>/<int:unit>/'
)
def validate_candles(
    base_currency: str, quote_currency: str, unit_type: str, unit: int,
):
    assert unit_type == 'minutes'
    interpolated = bool(request.args.get('interpolated'))
    pair = f'{base_currency}/{quote_currency}'
    created_at = (
        datetime.datetime.now(datetime.timezone.utc) -
        datetime.timedelta(minutes=unit * 100)
    )
    unit_key = (unit, CandleUnitType(unit_type))
    expected_candles = {
        c.timestamp: c
        for c in Candle.query(
            session=session,
            pair=pair,
            unit_key=unit_key,
            created_at=created_at,
        )
    }
    actual_candles = session.query(Candle).filter(
        Candle.pair == pair,
        Candle.unit_type == CandleUnitType(unit_type),
        Candle.unit == unit,
        Candle.timestamp >= created_at,
    ).order_by(
        Candle.timestamp.desc()
    ).all()
    if interpolated:
        if actual_candles:
            Candle.interpolate(
                session=session,
                candles=actual_candles,
                pair=pair,
                unit_key=unit_key,
            )
    actual_candles = {c.timestamp: c for c in actual_candles}

    timestamps = set(expected_candles) & set(actual_candles)

    def _serialize(r):
        return {
            'timestamp': r.timestamp.isoformat(),
            'updated_at': r.updated_at.isoformat(),
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
            'quoteVolume': r.quote_volume,
            'unitType': unit_type,
            'unit': unit,
        }

    differences = []
    for t in timestamps:
        e = expected_candles[t]
        a = actual_candles[t]
        if (
            e.open != a.open or
            e.high != e.high or
            e.low != e.low or
            e.close != a.close or
            e.volume != a.volume or
            e.quote_volume != a.quote_volume
        ):
            differences.append({
                'expected': _serialize(e), 'actual': _serialize(a),
            })
    return jsonify({
        'interpolated': interpolated,
        'timestamps': sorted(
            [t.isoformat() for t in timestamps], reverse=True,
        ),
        'differences': serialize(differences),
        'expected_candles': len([
            e for e in expected_candles if e in timestamps
        ]),
        'actual_candles': len([
            a for a in actual_candles if a in timestamps
        ]),
    })
