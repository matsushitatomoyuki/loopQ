from django.contrib import admin
from .models import SurveyTemplate, Question, SurveyResponse, Answer


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ['phase', 'order_no', 'question_type', 'body_i18n', 'is_required']


@admin.register(SurveyTemplate)
class SurveyTemplateAdmin(admin.ModelAdmin):
    list_display = ['store', 'version', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['store__name']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['survey_template', 'phase', 'order_no', 'question_type', 'is_required']
    list_filter = ['phase', 'question_type']


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'value_int', 'value_text', 'answered_at']
    can_delete = False


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ['client', 'store', 'phase1_completed_at', 'phase2_completed_at', 'created_at']
    list_filter = ['store']
    search_fields = ['store__name', 'client__id']
    raw_id_fields = ['client', 'store', 'survey_template', 'visit']
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['survey_response', 'question', 'value_int', 'value_text', 'answered_at']
    raw_id_fields = ['survey_response', 'question']
