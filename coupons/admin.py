from django.contrib import admin
from .models import RouletteConfig, RoulettePrize, RouletteSpin, Coupon, CouponUsage


class RoulettePrizeInline(admin.TabularInline):
    model = RoulettePrize
    extra = 0
    fields = ['points', 'probability_bp', 'rarity', 'expiry_days']


@admin.register(RouletteConfig)
class RouletteConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'is_active', 'created_at']
    list_filter = ['is_active']
    inlines = [RoulettePrizeInline]


@admin.register(RoulettePrize)
class RoulettePrizeAdmin(admin.ModelAdmin):
    list_display = ['roulette_config', 'points', 'probability_bp', 'rarity', 'expiry_days']
    list_filter = ['rarity']


@admin.register(RouletteSpin)
class RouletteSpinAdmin(admin.ModelAdmin):
    list_display = ['client', 'store', 'points_awarded', 'spun_at']
    list_filter = ['store']
    raw_id_fields = ['client', 'store', 'survey_response', 'prize']
    readonly_fields = ['client', 'store', 'survey_response', 'prize',
                       'points_awarded', 'spun_at']

    def has_add_permission(self, request):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['client', 'store', 'points', 'status', 'issued_at', 'expires_at']
    list_filter = ['status', 'store']
    search_fields = ['client__id', 'store__name']
    raw_id_fields = ['client', 'store', 'roulette_spin']


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'activated_at', 'confirmed_at', 'countdown_completed']
    raw_id_fields = ['coupon']
    readonly_fields = ['coupon', 'activated_at', 'confirmed_at', 'countdown_completed']

    def has_add_permission(self, request):
        return False
