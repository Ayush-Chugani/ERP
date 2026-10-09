"""SQLAlchemy models for the feedback domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class FeedbackChoice(Base):
    __tablename__ = 'feedback_choice'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    feedback_choice_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    choice_text = mapped_column(String(250), nullable=False)
    score = mapped_column(Numeric(6, 2))
    display_order = mapped_column(Integer)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    feedback_question_id = mapped_column(Integer, ForeignKey('feedback_question.feedback_question_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('feedback_question_id', 'choice_text', name='uq_feedback_choice_feedback_question_id_choice_text'),
        Index('ix_feedback_choice_actor_id', 'actor_id'),
        CheckConstraint('(version >= 0)', name='ck_feedback_choice_feedback_choice_chk_1'),
        CheckConstraint('(display_order >= 0)', name='ck_feedback_choice_feedback_choice_chk_2'),
    )


class FeedbackCycle(Base):
    __tablename__ = 'feedback_cycle'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    feedback_cycle_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cycle_name = mapped_column(String(150), nullable=False)
    start_at = mapped_column(DateTime(timezone=True), nullable=False)
    end_at = mapped_column(DateTime(timezone=True), nullable=False)
    result_visibility = mapped_column(String(10), nullable=False, server_default=text("'HIDDEN'"))
    status = mapped_column(String(9), nullable=False, server_default=text("'SCHEDULED'"))
    minimum_cohort = mapped_column(Integer, nullable=False)
    allow_text_review = mapped_column(Boolean, nullable=False, server_default=text("false"))
    target_policy = mapped_column(String(20), nullable=False)
    explicit_registrations = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    frozen = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    key_fingerprint = mapped_column(String(64), nullable=False, server_default=text("''"))
    academic_term_id = mapped_column(Integer, ForeignKey('academic_term.academic_term_id'), nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'))
    questionnaire_id = mapped_column(Integer, ForeignKey('feedback_questionnaire.questionnaire_id'), nullable=False)
    __table_args__ = (
        Index('ix_feedback_cycle_actor_id', 'actor_id'),
        Index('ix_feedback_cycle_programme_id', 'programme_id'),
        Index('ix_feedback_cycle_questionnaire_id', 'questionnaire_id'),
        Index('ix_feedback_cycle_academic_term_id_status_start_at_end_at', 'academic_term_id', 'status', 'start_at', 'end_at'),
        CheckConstraint('(end_at > start_at)', name='ck_feedback_cycle_feedback_cycle_dates'),
        CheckConstraint('(minimum_cohort >= 2)', name='ck_feedback_cycle_m11_cohort'),
        CheckConstraint("(status in ('SCHEDULED','OPEN','CLOSED','CANCELLED'))", name='ck_feedback_cycle_m11_cycle_state'),
        CheckConstraint("(result_visibility in ('HIDDEN','ADMIN_ONLY','FACULTY','PUBLIC'))", name='ck_feedback_cycle_m11_visibility'),
        CheckConstraint('(version >= 0)', name='ck_feedback_cycle_feedback_cycle_chk_1'),
        CheckConstraint('(minimum_cohort >= 0)', name='ck_feedback_cycle_feedback_cycle_chk_2'),
    )


class FeedbackQuestion(Base):
    __tablename__ = 'feedback_question'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    feedback_question_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_text = mapped_column(String(1000), nullable=False)
    response_type = mapped_column(String(15), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    rating_min = mapped_column(Numeric(6, 2))
    rating_max = mapped_column(Numeric(6, 2))
    rating_step = mapped_column(Numeric(6, 2))
    text_limit = mapped_column(Integer)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    feedback_category_id = mapped_column(Integer, ForeignKey('feedback_question_category.feedback_category_id'), nullable=False)
    __table_args__ = (
        Index('ix_feedback_question_actor_id', 'actor_id'),
        Index('ix_feedback_question_feedback_category_id', 'feedback_category_id'),
        CheckConstraint("(response_type in ('SINGLE_CHOICE','MULTIPLE_CHOICE','RATING','TEXT'))", name='ck_feedback_question_m11_response_type'),
        CheckConstraint('(version >= 0)', name='ck_feedback_question_feedback_question_chk_1'),
        CheckConstraint('(text_limit >= 0)', name='ck_feedback_question_feedback_question_chk_2'),
    )


class FeedbackQuestionCategory(Base):
    __tablename__ = 'feedback_question_category'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    feedback_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(30), nullable=False)
    category_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_feedback_question_category_category_code'),
        UniqueConstraint('category_name', name='uq_feedback_question_category_category_name'),
        Index('ix_feedback_question_category_actor_id', 'actor_id'),
        Index('ix_feedback_question_category_institution_id', 'institution_id'),
        CheckConstraint('(version >= 0)', name='ck_feedback_question_category_feedback_question_categ_6da334'),
    )


class FeedbackQuestionnaire(Base):
    __tablename__ = 'feedback_questionnaire'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    questionnaire_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    questionnaire_code = mapped_column(String(30), nullable=False)
    questionnaire_name = mapped_column(String(150), nullable=False)
    questionnaire_type = mapped_column(String(11), nullable=False)
    is_anonymous = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status = mapped_column(String(7), nullable=False, server_default=text("'DRAFT'"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('questionnaire_code', name='uq_feedback_questionnaire_questionnaire_code'),
        Index('ix_feedback_questionnaire_institution_id', 'institution_id'),
        Index('ix_feedback_questionnaire_actor_id', 'actor_id'),
        CheckConstraint("(status in ('DRAFT','ACTIVE','RETIRED'))", name='ck_feedback_questionnaire_m11_questionnaire_state'),
        CheckConstraint("(questionnaire_type in ('COURSE','FACULTY','PROGRAMME','INSTITUTION','EXIT','OTHER'))", name='ck_feedback_questionnaire_m11_questionnaire_type'),
        CheckConstraint('(version >= 0)', name='ck_feedback_questionnaire_feedback_questionnaire_chk_1'),
    )


class FeedbackQuestionnaireItem(Base):
    __tablename__ = 'feedback_questionnaire_item'
    questionnaire_item_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    weightage = mapped_column(Numeric(6, 2))
    display_order = mapped_column(Integer, nullable=False)
    is_required = mapped_column(Boolean, nullable=False, server_default=text("false"))
    feedback_question_id = mapped_column(Integer, ForeignKey('feedback_question.feedback_question_id'), nullable=False)
    questionnaire_id = mapped_column(Integer, ForeignKey('feedback_questionnaire.questionnaire_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('questionnaire_id', 'display_order', name='uq_feedback_questionnaire_item_questionnaire_id_displ_271b6c'),
        UniqueConstraint('questionnaire_id', 'feedback_question_id', name='uq_feedback_questionnaire_item_questionnaire_id_feedb_00ec9a'),
        Index('ix_feedback_questionnaire_item_feedback_question_id', 'feedback_question_id'),
        CheckConstraint('((weightage is null) or (weightage >= 0))', name='ck_feedback_questionnaire_item_m11_weight'),
        CheckConstraint('(display_order >= 0)', name='ck_feedback_questionnaire_item_feedback_questionnaire_da74bc'),
    )


class FeedbackResponse(Base):
    __tablename__ = 'feedback_response'
    feedback_response_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_key = mapped_column(String(80), nullable=False)
    submitted_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    response_token = mapped_column(String(36), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'))
    faculty_assignment_id = mapped_column(BigInteger, ForeignKey('faculty_course_assignment.faculty_assignment_id'))
    feedback_cycle_id = mapped_column(BigInteger, ForeignKey('feedback_cycle.feedback_cycle_id'), nullable=False)
    term_registration_id = mapped_column(BigInteger, ForeignKey('student_term_registration.term_registration_id'))
    __table_args__ = (
        UniqueConstraint('response_token', name='uq_feedback_response_response_token'),
        Index('ix_feedback_response_course_offering_id', 'course_offering_id'),
        Index('ix_feedback_response_faculty_assignment_id', 'faculty_assignment_id'),
        Index('ix_feedback_response_term_registration_id', 'term_registration_id'),
        Index('ix_feedback_response_feedback_cycle_id_target_key', 'feedback_cycle_id', 'target_key'),
    )


class FeedbackResponseItem(Base):
    __tablename__ = 'feedback_response_item'
    feedback_response_item_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    numeric_score = mapped_column(Numeric(6, 2))
    text_response = mapped_column(Text)
    feedback_choice_id = mapped_column(Integer, ForeignKey('feedback_choice.feedback_choice_id'))
    feedback_response_id = mapped_column(BigInteger, ForeignKey('feedback_response.feedback_response_id'), nullable=False)
    questionnaire_item_id = mapped_column(BigInteger, ForeignKey('feedback_questionnaire_item.questionnaire_item_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('feedback_response_id', 'questionnaire_item_id', name='uq_feedback_response_item_feedback_response_id_questi_9291c4'),
        Index('ix_feedback_response_item_feedback_choice_id', 'feedback_choice_id'),
        Index('ix_feedback_response_item_questionnaire_item_id', 'questionnaire_item_id'),
    )


class FeedbackResponseItemChoice(Base):
    __tablename__ = 'feedback_response_item_choice'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feedback_choice_id = mapped_column(Integer, ForeignKey('feedback_choice.feedback_choice_id'), nullable=False)
    feedback_response_item_id = mapped_column(BigInteger, ForeignKey('feedback_response_item.feedback_response_item_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('feedback_response_item_id', 'feedback_choice_id', name='uq_feedback_response_item_choice_feedback_response_it_a6afa3'),
        Index('ix_feedback_response_item_choice_feedback_choice_id', 'feedback_choice_id'),
    )


class FeedbackLedger(Base):
    __tablename__ = 'feedback_ledger'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fingerprint = mapped_column(String(64), nullable=False)
    request_digest = mapped_column(String(64), nullable=False)
    receipt = mapped_column(String(36), nullable=False)
    cycle_id = mapped_column(BigInteger, ForeignKey('feedback_cycle.feedback_cycle_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('receipt', name='uq_feedback_ledger_receipt'),
        UniqueConstraint('cycle_id', 'fingerprint', name='uq_feedback_ledger_cycle_id_fingerprint'),
    )
