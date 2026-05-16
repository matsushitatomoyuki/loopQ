import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


# ─────────────────────────────────────────
# マスタ系
# ─────────────────────────────────────────

class BusinessCategory(models.Model):
    """業態マスタ（飲食・カフェ・美容院等）"""

    FREQUENCY_CHOICES = [
        ('high', 'high'),  # カフェ・ラーメン → WAU
        ('mid',  'mid'),   # 居酒屋・レストラン → MAU
        ('low',  'low'),   # 美容院・高級店 → QAU
    ]
    METRIC_CHOICES = [
        ('WAU', 'WAU'),
        ('MAU', 'MAU'),
        ('QAU', 'QAU'),
    ]

    code           = models.CharField(max_length=32, unique=True)   # restaurant_ramen, cafe …
    name_ja        = models.CharField(max_length=64)
    name_en        = models.CharField(max_length=64, blank=True)
    frequency_type = models.CharField(max_length=16, choices=FREQUENCY_CHOICES)
    active_metric  = models.CharField(max_length=8,  choices=METRIC_CHOICES)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'business_category'

    def __str__(self):
        return self.name_ja


# ─────────────────────────────────────────
# 店主（Owner）— AbstractUser 拡張
# ─────────────────────────────────────────

class Owner(AbstractUser):
    """
    店主アカウント。
    Django デフォルトの username を廃止し、email をログインIDにする。
    AUTH_USER_MODEL = 'stores.Owner' を settings.py に設定すること。
    """

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username         = None  # username フィールドを削除
    email            = models.EmailField(unique=True)
    phone            = models.CharField(max_length=32, blank=True)
    sms_2fa_enabled  = models.BooleanField(default=False)

    USERNAME_FIELD   = 'email'
    REQUIRED_FIELDS  = []   # createsuperuser で email 以外は要求しない

    class Meta:
        db_table = 'owner'

    def __str__(self):
        return self.email


# ─────────────────────────────────────────
# 店舗
# ─────────────────────────────────────────

class Store(models.Model):
    """
    店舗。id（UUID）が QR コードの URL に埋め込まれる。
    """

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner               = models.ForeignKey(Owner, on_delete=models.PROTECT, related_name='stores')
    name                = models.CharField(max_length=128)
    business_category   = models.ForeignKey(BusinessCategory, on_delete=models.PROTECT,
                                             related_name='stores')
    postal_code         = models.CharField(max_length=16, blank=True)
    address             = models.CharField(max_length=255, blank=True)
    latitude            = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude           = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    currency_code       = models.CharField(max_length=3, default='JPY')
    locale_code         = models.CharField(max_length=8, default='ja_JP')
    logo_url            = models.CharField(max_length=512, blank=True)
    brand_color         = models.CharField(max_length=7, blank=True)   # #RRGGBB
    google_place_id     = models.CharField(max_length=128, blank=True)
    instagram_handle    = models.CharField(max_length=64, blank=True)
    line_official_id    = models.CharField(max_length=64, blank=True)
    is_active           = models.BooleanField(default=True)
    deleted_at          = models.DateTimeField(null=True, blank=True)  # 論理削除
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'store'
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['business_category']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# 来店客
# ─────────────────────────────────────────

class Client(models.Model):
    """
    来店客（認証なし）。
    MVP では UUID のみ。localStorage と同期。
    Phase 2 以降で連絡先連携（ClientIdentity）を追加予定。
    """

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_seen_at    = models.DateTimeField()          # 初回QRスキャン日時
    last_seen_at     = models.DateTimeField()
    total_points     = models.IntegerField(default=0)  # 累計獲得pt
    available_points = models.IntegerField(default=0)  # 未使用残高
    locale_code      = models.CharField(max_length=8, blank=True)  # ブラウザから推定
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client'

    def __str__(self):
        return str(self.id)


class ClientVisit(models.Model):
    """来店記録。1来店 = 1レコード。"""

    REFERRAL_CHOICES = [
        ('map',      '地図'),
        ('referral', '紹介'),
        ('regular',  '常連'),
        ('passerby', '通りかかり'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='visits')
    store           = models.ForeignKey(Store,  on_delete=models.PROTECT, related_name='visits')
    visited_at      = models.DateTimeField()
    visit_number    = models.IntegerField()          # この店舗での通算来店回数
    companions      = models.SmallIntegerField(null=True, blank=True)  # 同伴人数（Q2の回答から）
    referral_source = models.CharField(max_length=16, choices=REFERRAL_CHOICES, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client_visit'
        indexes = [
            models.Index(fields=['client', 'store']),
            models.Index(fields=['store', 'visited_at']),
        ]

    def __str__(self):
        return f"{self.client} @ {self.store} #{self.visit_number}"


# ─────────────────────────────────────────
# PWA インストール記録
# ─────────────────────────────────────────

class PwaInstall(models.Model):
    """
    PWA ホーム画面追加の記録。
    uninstalled_at が NULL のものが現役インストール。
    """

    PLATFORM_CHOICES = [
        ('ios',     'iOS'),
        ('android', 'Android'),
        ('desktop', 'Desktop'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client         = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='pwa_installs')
    platform       = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    installed_at   = models.DateTimeField()
    push_token     = models.CharField(max_length=512, blank=True)  # Web Push 用
    uninstalled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pwa_install'
        indexes = [
            models.Index(fields=['client', 'uninstalled_at']),
        ]

    def __str__(self):
        return f"{self.client} [{self.platform}]"


# ─────────────────────────────────────────
# イベントログ（最重要・絶対削除禁止）
# ─────────────────────────────────────────

class EventLog(models.Model):
    """
    全イベントを記録する。削除・更新禁止。分析の原資。
    PK は BigAutoField（BIGSERIAL）— settings の DEFAULT_AUTO_FIELD = BigAutoField に従う。
    """

    EVENT_TYPES = [
        ('qr_scanned',              'qr_scanned'),
        ('survey_started',          'survey_started'),
        ('question_answered',       'question_answered'),
        ('survey_phase1_completed', 'survey_phase1_completed'),
        ('survey_completed',        'survey_completed'),
        ('roulette_spun',           'roulette_spun'),
        ('pwa_install_prompted',    'pwa_install_prompted'),
        ('pwa_installed',           'pwa_installed'),
        ('coupon_issued',           'coupon_issued'),
        ('coupon_activated',        'coupon_activated'),
        ('coupon_used_start',       'coupon_used_start'),
        ('coupon_used_confirmed',   'coupon_used_confirmed'),
        ('coupon_expired',          'coupon_expired'),
        ('notification_sent',       'notification_sent'),
        ('notification_opened',     'notification_opened'),
        ('revisit',                 'revisit'),
    ]

    # id は BigAutoField（DEFAULT_AUTO_FIELD = BigAutoField）に任せる
    event_type  = models.CharField(max_length=32, choices=EVENT_TYPES)
    client      = models.ForeignKey(Client, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='events')
    store       = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='events')
    occurred_at = models.DateTimeField()
    payload     = models.JSONField(default=dict)       # イベント固有データ
    user_agent  = models.CharField(max_length=255, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'event_log'
        indexes = [
            models.Index(fields=['store',      'occurred_at']),
            models.Index(fields=['event_type', 'occurred_at']),
            models.Index(fields=['client',     'occurred_at']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.occurred_at}"
