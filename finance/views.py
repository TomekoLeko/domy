from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def finance_main(request):
    return render(request, 'finance/main.html')
