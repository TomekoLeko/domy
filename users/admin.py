from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_is_contributor', 'get_is_beneficiary')

    def get_is_contributor(self, obj):
        return obj.profile.is_contributor
    get_is_contributor.short_description = 'Contributor'
    get_is_contributor.boolean = True
    
    def get_is_beneficiary(self, obj):
        return obj.profile.is_beneficiary
    get_is_beneficiary.short_description = 'Beneficiary'
    get_is_beneficiary.boolean = True

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
