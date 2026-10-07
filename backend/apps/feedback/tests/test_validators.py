import pytest
from rest_framework.exceptions import ValidationError
from apps.feedback.validators import answer
BASE={'choices':[{'id':'1'},{'id':'2'}],'rating_min':'1','rating_max':'5','rating_step':'0.5','text_limit':20}
@pytest.mark.parametrize('kind,data',[('SINGLE_CHOICE',{'choice_id':1}),('MULTIPLE_CHOICE',{'choice_ids':[1,2]}),('RATING',{'numeric_score':'3.5'}),('TEXT',{'text_response':'<b>plain</b>'})])
def test_each_answer_type(kind,data):assert answer({**BASE,'response_type':kind},data)
@pytest.mark.parametrize('kind,data',[('SINGLE_CHOICE',{'choice_id':3}),('SINGLE_CHOICE',{'choice_id':1,'text_response':'extra'}),('MULTIPLE_CHOICE',{'choice_ids':[1,1]}),('MULTIPLE_CHOICE',{'choice_ids':[]}),('RATING',{'numeric_score':'3.3'}),('RATING',{'numeric_score':'NaN'}),('TEXT',{'text_response':'x'*21})])
def test_reject_forged_or_ambiguous_answers(kind,data):
    with pytest.raises(ValidationError):answer({**BASE,'response_type':kind},data)
