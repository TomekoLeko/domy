from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fieldsets = (
        (None, {
            'fields': ('is_contributor', 'is_beneficiary')
        }),
        ('Contact Information', {
            'fields': ('name', 'phone', 'address', 'city', 'postal')
        }),
    )

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'get_name', 'get_phone', 'is_staff', 'get_is_contributor', 'get_is_beneficiary')
    list_filter = ('is_staff', 'is_superuser', 'profile__is_contributor', 'profile__is_beneficiary')
    search_fields = ('username', 'email', 'profile__name', 'profile__phone')

    def get_is_contributor(self, obj):
        return obj.profile.is_contributor
    get_is_contributor.short_description = 'Contributor'
    get_is_contributor.boolean = True
    
    def get_is_beneficiary(self, obj):
        return obj.profile.is_beneficiary
    get_is_beneficiary.short_description = 'Beneficiary'
    get_is_beneficiary.boolean = True

    def get_name(self, obj):
        return obj.profile.name
    get_name.short_description = 'Name'

    def get_phone(self, obj):
        return obj.profile.phone
    get_phone.short_description = 'Phone'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
