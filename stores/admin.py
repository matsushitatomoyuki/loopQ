from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BusinessCategory, Owner, Store, Client, ClientVisit, PwaInstall, EventLog


@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name_ja', 'frequency_type', 'active_metric', 'created_at']
    search_fields = ['code', 'name_ja']


@admin.register(Owner)
class OwnerAdmin(UserAdmin):
    model = Owner
    list_display = ['email', 'is_active', 'is_staff', 'sms_2fa_enabled', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'sms_2fa_enabled']
    search_fields = ['email']
    ordering = ['-date_joined']
    fieldsets = (
        (None,          {'fields': ('email', 'password')}),
        ('連絡先',       {'fields': ('phone',)}),
        ('セキュリティ', {'fields': ('sms_2fa_enabled',)}),
        ('権限',         {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('日時',         {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'business_category', 'is_active', 'created_at']
    list_filter = ['is_active', 'business_category']
    search_fields = ['name', 'owner__email', 'address']
    raw_id_fields = ['owner']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['id', 'total_points', 'available_points', 'first_seen_at', 'last_seen_at']
    search_fields = ['id']
    readonly_fields = ['id', 'created_at']


@admin.register(ClientVisit)
class ClientVisitAdmin(admin.ModelAdmin):
    list_display = ['client', 'store', 'visit_number', 'referral_source', 'visited_at']
    list_filter = ['referral_source', 'store']
    raw_id_fields = ['client', 'store']


@admin.register(PwaInstall)
class PwaInstallAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'installed_at', 'uninstalled_at']
    list_filter = ['platform']
    raw_id_fields = ['client']


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'store', 'client', 'occurred_at']
    list_filter = ['event_type']
    search_fields = ['event_type', 'store__name']
    raw_id_fields = ['client', 'store']
    readonly_fields = ['event_type', 'client', 'store', 'occurred_at', 'payload',
                       'user_agent', 'ip_address', 'created_at']

    def has_add_permission(self, request):
        return False  # イベントログはコードからのみ作成

    def has_delete_permission(self, request, obj=None):
        return False  # 絶対削除禁止
