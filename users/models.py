from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import PriceList

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_contributor = models.BooleanField(default=False)
    is_beneficiary = models.BooleanField(default=False)
    name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal = models.CharField(max_length=6, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    price_list = models.ForeignKey(PriceList, on_delete=models.SET_NULL, null=True, blank=True)
    monthly_limit = models.IntegerField(null=True, blank=True, help_text="Miesięczny limit dla beneficjenta")

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_or_create_monthly_usage(self, year, month):
        """
        Get or create MonthlyContributionUsage for the given month.
        If creating new, copies the current monthly_limit.
        """
        from finance.models import MonthlyContributionUsage
        
        if not self.is_beneficiary or not self.monthly_limit:
            return None
            
        usage, created = MonthlyContributionUsage.objects.get_or_create(
            profile=self,
            year=year,
            month=month,
            defaults={'limit': self.monthly_limit}
        )
        return usage

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        Profile.objects.create(user=instance)
    instance.profile.save()
