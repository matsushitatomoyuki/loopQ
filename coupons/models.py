import uuid
from django.db import models
from stores.models import Client, Store
from surveys.models import SurveyResponse


class RouletteConfig(models.Model):
    """
    ルーレット設定。store=NULL はシステムデフォルト設定。
    store 指定で店舗別カスタムも可能（Phase 2 以降）。
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store      = models.ForeignKey(Store, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='roulette_configs')
    name       = models.CharField(max_length=64)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roulette_config'

    def __str__(self):
        return self.name


class RoulettePrize(models.Model):
    """
    賞品マスタ。確率は basis point（10000 = 100%）で管理。
    同一 config の合計が 10000 になることをアプリ側で検証する。
    """

    RARITY_CHOICES = [
        ('normal',     'ノーマル'),
        ('rare',       'レア'),
        ('super_rare', '超レア'),
        ('legendary',  '伝説'),
    ]

    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    roulette_config    = models.ForeignKey(RouletteConfig, on_delete=models.CASCADE,
                                            related_name='prizes')
    points             = models.IntegerField()       # 100, 300, 500, 1000, 3000, 10000
    probability_bp     = models.IntegerField()       # 7000=70%, 2000=20%, 700=7%, 250=2.5%…
    expiry_days        = models.IntegerField(null=True, blank=True)  # 1000pt 以上は 30日
    rarity             = models.CharField(max_length=16, choices=RARITY_CHOICES)

    class Meta:
        db_table = 'roulette_prize'

    def __str__(self):
        return f"{self.points}pt ({self.probability_bp/100:.1f}%) [{self.rarity}]"


class RouletteSpin(models.Model):
    """
    ガチャ実行ログ。1アンケート回答につき1回転のみ（OneToOne で強制）。
    points_awarded は prize の値をデノーマライズして保持（賞品マスタ変更時も履歴が正確に残る）。
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(Client, on_delete=models.PROTECT,
                                         related_name='roulette_spins')
    store           = models.ForeignKey(Store, on_delete=models.PROTECT,
                                         related_name='roulette_spins')
    survey_response = models.OneToOneField(SurveyResponse, on_delete=models.PROTECT,
                                            related_name='roulette_spin')
    prize           = models.ForeignKey(RoulettePrize, on_delete=models.PROTECT,
                                         related_name='spins')
    points_awarded  = models.IntegerField()   # デノーマライズ
    spun_at         = models.DateTimeField()

    class Meta:
        db_table = 'roulette_spin'

    def __str__(self):
        return f"{self.client} → {self.points_awarded}pt @ {self.store.name}"


class Coupon(models.Model):
    """
    クーポン発行・状態管理。
    status 遷移：issued → activated → used / expired

    issued    : ガチャで発行
    activated : 客が「使う」ボタンを押した（5分カウントダウン開始）
    used      : 店主確認完了 or 5分経過後に自動消化
    expired   : 期限切れ（未使用のまま expiry を過ぎた）
    """

    STATUS_CHOICES = [
        ('issued',    'issued'),
        ('activated', 'activated'),
        ('used',      'used'),
        ('expired',   'expired'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='coupons')
    store           = models.ForeignKey(Store,  on_delete=models.PROTECT, related_name='coupons')
    roulette_spin   = models.OneToOneField(RouletteSpin, on_delete=models.PROTECT,
                                            related_name='coupon')
    points          = models.IntegerField()
    status          = models.CharField(max_length=16, choices=STATUS_CHOICES, default='issued')
    issued_at       = models.DateTimeField()
    expires_at      = models.DateTimeField(null=True, blank=True)  # NULL = 無期限
    activated_at    = models.DateTimeField(null=True, blank=True)  # 「使う」押下時刻
    used_at         = models.DateTimeField(null=True, blank=True)  # 確認完了時刻

    class Meta:
        db_table = 'coupon'
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['store',  'status']),
            models.Index(fields=['status', 'expires_at']),  # 期限切れバッチ用
        ]

    def __str__(self):
        return f"{self.client} {self.points}pt [{self.status}]"


class CouponUsage(models.Model):
    """
    クーポン使用時の詳細記録。
    coupon 本体とは分離して履歴性を確保。
    confirmed_at が NULL で countdown_completed=True なら 5分タイムアウト消化。
    """

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon              = models.OneToOneField(Coupon, on_delete=models.PROTECT,
                                               related_name='usage')
    activated_at        = models.DateTimeField()
    confirmed_at        = models.DateTimeField(null=True, blank=True)  # 店主確認完了
    countdown_completed = models.BooleanField()                        # 5分経過したか

    class Meta:
        db_table = 'coupon_usage'

    def __str__(self):
        return f"Usage: {self.coupon}"
