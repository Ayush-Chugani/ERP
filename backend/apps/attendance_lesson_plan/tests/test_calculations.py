from decimal import Decimal
import pytest
from apps.attendance_lesson_plan.calculations import validate_rules, contribution, summarize


def test_excluded_status_has_no_denominator():
    assert contribution(rule={'credit':0,'denominator':0},basis='DURATION',duration_minutes=60)==(0,0)
    assert summarize([{'credit':0,'denominator':0}],75)['percentage'] is None


def test_weighted_duration_and_exact_threshold():
    present=contribution(rule={'credit':1,'denominator':1},basis='DURATION',duration_minutes=45)
    late=contribution(rule={'credit':'.5','denominator':1},basis='DURATION',duration_minutes=60)
    result=summarize([dict(zip(('credit','denominator'),row)) for row in (present,late)],75)
    assert result['percentage']=='71.43'
    assert result['shortage'] is True
    assert summarize([{'credit':'74.999','denominator':100}],75)['shortage'] is True


@pytest.mark.parametrize('credit,denominator', [(-1,1),(2,1),(1,0),('NaN',1),(0,'Infinity')])
def test_invalid_weights_rejected(credit,denominator):
    with pytest.raises(ValueError):
        validate_rules({'P':{'credit':credit,'denominator':denominator}})


@pytest.mark.parametrize('duration', [1,15,30,45,60,90,120])
def test_full_credit_is_one_hundred_for_every_positive_duration(duration):
    credit,denominator=contribution(rule={'credit':1,'denominator':1},basis='DURATION',duration_minutes=duration)
    assert summarize([{'credit':credit,'denominator':denominator}],100)['percentage']=='100.00'
