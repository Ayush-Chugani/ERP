from decimal import Decimal as D
import pytest
from apps.assessments_results import validators as v
from .test_domain import RULES,BANDS
@pytest.mark.parametrize('score,grade',[('0','F'),('49.999','F'),('50','P'),('99.999','P'),('100','P')])
def test_boundaries(score,grade):assert v.resolve_grade(BANDS,D(score))['grade_letter']==grade
@pytest.mark.parametrize('value',[float('nan'),float('inf'),'NaN','Infinity',True,-float('inf')])
def test_bad_numbers(value):
    with pytest.raises(ValueError):v.number(value)
def test_policy_requires_explicit_fields():
    with pytest.raises(ValueError):v.validate_policy({})
    assert v.validate_policy(RULES)==RULES
def test_zero_credit_gpa():assert v.TermGpaPolicy.calculate([{'credits':'0','grade_point':'10','result_status':'PASS'}],RULES) is None
def test_grade_gap():
    with pytest.raises(ValueError):v.validate_bands([{**BANDS[0],'maximum_percentage':D('49')},BANDS[1]])
def test_best_of_n():
    rules={**RULES,'aggregation':'BEST_N','best_n':1}
    assert v.InternalAssessmentPolicy.calculate([{'id':1,'mandatory':True,'weight':'100'}],{1:[{'attendance_status':'PRESENT','maximum':'100','value':'80'},{'attendance_status':'PRESENT','maximum':'100','value':'20'}]},rules)==80

@pytest.mark.parametrize('status,expected',[('ABSENT',D('0')),('EXEMPTED',None),('MALPRACTICE',None)])
def test_special_attendance(status,expected):
    args=([{'id':1,'mandatory':True,'weight':'100'}],{1:[{'attendance_status':status,'maximum':'100','value':None}]},RULES)
    if expected is None:
        with pytest.raises(ValueError):v.InternalAssessmentPolicy.calculate(*args)
    else:assert v.InternalAssessmentPolicy.calculate(*args)==expected

def test_threshold_not_bypassed_by_grace():
    total,passed=v.CourseResultPolicy.calculate('90','0',{**RULES,'minimum_external':'40','grace':'10'})
    assert total==100 and not passed
