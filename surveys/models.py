import uuid
from django.db import models
from stores.models import Client, Store, ClientVisit


class SurveyTemplate(models.Model):
    """
    店舗別のアンケート定義。
    設問を変更するたびに version を上げ、古い回答と紐付けを保持する。
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store      = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='survey_templates')
    version    = models.IntegerField()
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'survey_template'
        unique_together = [('store', 'version')]

    def __str__(self):
        return f"{self.store.name} v{self.version}"


class Question(models.Model):
    """
    設問マスタ。
    phase 1：着席直後の2問（choice）
    phase 2：料理待ち中の4問（slider × 3, choice × 1）
    """

    QUESTION_TYPES = [
        ('choice',  'choice'),   # 選択肢タップ
        ('slider',  'slider'),   # 1〜5 スライダー
        ('boolean', 'boolean'),  # Yes / No
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_template  = models.ForeignKey(SurveyTemplate, on_delete=models.CASCADE,
                                          related_name='questions')
    phase            = models.SmallIntegerField()    # 1 or 2
    order_no         = models.SmallIntegerField()    # フェーズ内の表示順
    question_type    = models.CharField(max_length=16, choices=QUESTION_TYPES)
    body_i18n        = models.JSONField()            # {"ja": "今日、何で来ましたか？", "en": "..."}
    options_i18n     = models.JSONField(null=True, blank=True)
    # 例: {"ja": [{"code":"map","label":"地図"},{"code":"referral","label":"紹介"}], "en":[...]}
    is_required      = models.BooleanField(default=True)

    class Meta:
        db_table = 'question'
        unique_together = [('survey_template', 'phase', 'order_no')]
        ordering = ['phase', 'order_no']

    def __str__(self):
        return f"Phase{self.phase}-Q{self.order_no} ({self.question_type})"


class SurveyResponse(models.Model):
    """
    アンケート回答のヘッダ。
    phase1 → phase2 の完了タイムスタンプを別々に持つ（離脱分析に使う）。
    """

    id                   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client               = models.ForeignKey(Client, on_delete=models.PROTECT,
                                              related_name='survey_responses')
    store                = models.ForeignKey(Store, on_delete=models.PROTECT,
                                              related_name='survey_responses')
    survey_template      = models.ForeignKey(SurveyTemplate, on_delete=models.PROTECT,
                                              related_name='responses')
    visit                = models.ForeignKey(ClientVisit, on_delete=models.SET_NULL,
                                              null=True, blank=True,
                                              related_name='survey_responses')
    phase1_completed_at  = models.DateTimeField(null=True, blank=True)
    phase2_completed_at  = models.DateTimeField(null=True, blank=True)  # NULL = 未完了
    total_duration_sec   = models.IntegerField(null=True, blank=True)   # 開始〜完了の秒数
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'survey_response'
        indexes = [
            models.Index(fields=['store', 'created_at']),
        ]

    def __str__(self):
        return f"{self.client} @ {self.store.name} ({self.created_at:%Y-%m-%d})"


class Answer(models.Model):
    """
    設問単位の回答。
    スライダーは value_int（1〜5）、選択肢は value_text（コード文字列）に保存。
    """

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_response  = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE,
                                          related_name='answers')
    question         = models.ForeignKey(Question, on_delete=models.PROTECT,
                                          related_name='answers')
    value_int        = models.SmallIntegerField(null=True, blank=True)  # スライダー 1〜5
    value_text       = models.CharField(max_length=64, blank=True)      # 選択肢コード
    answered_at      = models.DateTimeField()

    class Meta:
        db_table = 'answer'
        unique_together = [('survey_response', 'question')]

    def __str__(self):
        val = self.value_int if self.value_int is not None else self.value_text
        return f"{self.question} → {val}"
